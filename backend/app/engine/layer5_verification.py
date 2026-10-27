import re
from dataclasses import dataclass
from typing import List, Optional
from pydantic import BaseModel, Field

from app.engine.gemini_client import gemini_client
from app.engine.layer2_claim_extraction import ExtractedClaimCandidate
from app.schemas.verification import (
    VERDICT_LABELS_VI,
    ClaimTypeEnum,
    EvidenceItem,
    EvidenceStanceEnum,
    SuggestedCorrection,
    VerdictEnum,
)


class LLMVerdictDraft(BaseModel):
    verdict: VerdictEnum
    evidence_completeness: float = Field(ge=0.0, le=1.0)
    explanation_vi: str = Field(
        description="Giải thích khách quan, trung lập, nêu rõ bằng chứng nào ủng hộ/bác bỏ hoặc vì sao chưa đủ bằng chứng"
    )
    missing_information: List[str] = Field(default_factory=list)
    limitations_vi: str = Field(
        description="Giới hạn của kết luận hiện tại (thời điểm tra cứu, phạm vi nguồn công khai)"
    )
    cautious_rewrite_vi: Optional[str] = Field(
        default=None,
        description="Gợi ý viết lại câu theo hướng chính xác hoặc thận trọng hơn (nếu câu gốc sai, thiếu ngữ cảnh hoặc khái quát quá mức)",
    )
    rewrite_rationale_vi: Optional[str] = None


VERIFICATION_SYSTEM_PROMPT = """Bạn là Lớp 5 & Lớp 6 (Verification Decision Engine & Explanation Generator) của TrueCheck AI.
Nguyên tắc cốt lõi bắt buộc:
1. KHÔNG dùng tư duy nhị phân Đúng/Sai đơn giản. Sử dụng đúng 6 nhãn:
   - SUPPORTED: Có bằng chứng đáng tin cậy (Cấp 1–3 đã xác thực trích dẫn) hỗ trợ rõ ràng.
   - REFUTED: Có bằng chứng đáng tin cậy (Cấp 1–4 đã xác thực trích dẫn) bác bỏ trực tiếp.
   - MISLEADING: Đúng một phần nhưng thiếu ngữ cảnh quan trọng, khái quát hóa tuyệt đối ("mọi", "100%") hoặc cắt ghép gây hiểu nhầm.
   - INSUFFICIENT_EVIDENCE: Chưa đủ bằng chứng xác thực để kết luận. LƯU Ý: Chưa đủ bằng chứng KHÔNG đồng nghĩa với thông tin sai!
   - CONFLICTING_EVIDENCE: Các nguồn đáng tin cậy đang đưa ra số liệu/kết luận trái ngược nhau.
   - NOT_VERIFIABLE: Quan điểm cá nhân, dự đoán tương lai, nội dung châm biếm hoặc không thể kiểm chứng khách quan.
2. CHỐNG ẢO GIÁC (Anti-Hallucination): Chỉ dựa trên danh sách bằng chứng đã cung cấp. Nếu không có bằng chứng citation_validated=true từ nguồn Cấp 1–4, BẮT BUỘC trả về INSUFFICIENT_EVIDENCE (hoặc NOT_VERIFIABLE).
3. Nếu mệnh đề cần chỉnh sửa (REFUTED, MISLEADING, INSUFFICIENT_EVIDENCE do khái quát quá mức), hãy đề xuất cautious_rewrite_vi diễn đạt thận trọng, trung thực, không tự bịa số liệu mới."""


@dataclass
class VerificationDecision:
    verdict: VerdictEnum
    verdict_label_vi: str
    evidence_completeness: float
    explanation: str
    missing_information: List[str]
    limitations: str
    suggested_correction: Optional[SuggestedCorrection]


def _enforce_anti_hallucination_guardrail(
    draft_verdict: VerdictEnum,
    claim: ExtractedClaimCandidate,
    evidences: List[EvidenceItem],
) -> VerdictEnum:
    """
    Deterministic guardrail (Phần IV.6 & Phần X):
    Prevents false accusations (<5% target) and ungrounded SUPPORTED verdicts.
    """
    if claim.claim_type in (ClaimTypeEnum.OPINION, ClaimTypeEnum.PREDICTION, ClaimTypeEnum.SATIRE):
        return VerdictEnum.NOT_VERIFIABLE

    validated_credible = [
        e for e in evidences if e.citation_validated and e.tier <= 4
    ]
    supporting = [e for e in validated_credible if e.stance == EvidenceStanceEnum.SUPPORTING]
    refuting = [e for e in validated_credible if e.stance == EvidenceStanceEnum.REFUTING]

    # Never allow SUPPORTED or REFUTED without at least one citation-validated Tier 1-4 source
    if draft_verdict == VerdictEnum.SUPPORTED and not supporting:
        return VerdictEnum.INSUFFICIENT_EVIDENCE
    if draft_verdict == VerdictEnum.REFUTED and not refuting:
        return VerdictEnum.INSUFFICIENT_EVIDENCE

    if supporting and refuting and draft_verdict in (VerdictEnum.SUPPORTED, VerdictEnum.REFUTED):
        return VerdictEnum.CONFLICTING_EVIDENCE

    return draft_verdict


def _heuristic_decision(
    claim: ExtractedClaimCandidate,
    evidences: List[EvidenceItem],
    used_live_search: bool,
) -> VerificationDecision:
    """Transparent deterministic fallback when Gemini API key is not configured."""
    if claim.claim_type in (ClaimTypeEnum.OPINION, ClaimTypeEnum.PREDICTION, ClaimTypeEnum.SATIRE):
        return VerificationDecision(
            verdict=VerdictEnum.NOT_VERIFIABLE,
            verdict_label_vi=VERDICT_LABELS_VI[VerdictEnum.NOT_VERIFIABLE],
            evidence_completeness=0.0,
            explanation=(
                f"Nội dung này thuộc nhóm '{claim.claim_type_label_vi}'. "
                "Theo nguyên tắc của TrueCheck AI, hệ thống không đánh giá đúng/sai đối với quan điểm cá nhân hoặc dự đoán tương lai như một sự kiện thực tế."
            ),
            missing_information=[],
            limitations="Chỉ kiểm chứng các tuyên bố sự kiện, số liệu và trích dẫn khách quan.",
            suggested_correction=None,
        )

    validated_supp = [e for e in evidences if e.citation_validated and e.stance == EvidenceStanceEnum.SUPPORTING and e.tier <= 4]
    validated_ref = [e for e in evidences if e.citation_validated and e.stance == EvidenceStanceEnum.REFUTING and e.tier <= 4]

    low = claim.original_text.lower()
    is_absolute_generalization = bool(
        re.search(r"\b(mọi|tất cả|100%|ai cũng|hoàn toàn mọi)\b", low)
    )

    if validated_supp and validated_ref:
        verdict = VerdictEnum.CONFLICTING_EVIDENCE
        explanation = "Các nguồn đáng tin cậy hiện có đưa ra dữ liệu chưa thống nhất về mệnh đề này."
        completeness = 0.65
    elif validated_ref:
        verdict = VerdictEnum.REFUTED
        explanation = f"Tìm thấy {len(validated_ref)} nguồn kiểm chứng/chính thống bác bỏ trực tiếp tuyên bố này."
        completeness = 0.85
    elif validated_supp:
        verdict = VerdictEnum.MISLEADING if is_absolute_generalization else VerdictEnum.SUPPORTED
        explanation = f"Tìm thấy {len(validated_supp)} nguồn đáng tin cậy xác nhận dữ kiện chính."
        completeness = 0.85
    elif is_absolute_generalization:
        verdict = VerdictEnum.MISLEADING
        explanation = (
            "Câu viết sử dụng cách khái quát hóa tuyệt đối ('mọi', 'tất cả', '100%') nhưng chưa kèm dữ liệu khảo sát đại diện cho toàn bộ nhóm đối tượng."
        )
        completeness = 0.25
    else:
        verdict = VerdictEnum.INSUFFICIENT_EVIDENCE
        explanation = (
            "Chưa đủ bằng chứng đã xác thực để khẳng định hoặc bác bỏ mệnh đề này. "
            + (
                "Cần làm rõ thêm các thông tin điều kiện và đối chiếu trực tiếp với nguồn sơ cấp."
                if used_live_search
                else "Hệ thống đang chạy ở chế độ chưa kết nối API tìm kiếm thời gian thực; vui lòng cấu hình GEMINI_API_KEY và TAVILY_API_KEY / GOOGLE_FACTCHECK_API_KEY để tự động truy xuất đoạn trích."
            )
        )
        completeness = 0.20

    # Suggest Correction (Phần III.2)
    suggestion: Optional[SuggestedCorrection] = None
    if is_absolute_generalization:
        rewritten = re.sub(
            r"\b[Mm]ọi\s+sinh\s+viên\s+đều\b",
            "Nhiều sinh viên hiện đang",
            claim.original_text,
        )
        if rewritten == claim.original_text:
            rewritten = (
                f"Nhiều trường hợp ghi nhận rằng {claim.original_text[:1].lower() + claim.original_text[1:].rstrip('.')} "
                "(tuy nhiên cần dữ liệu khảo sát đại diện để xác định tỷ lệ cụ thể)."
            )
        else:
            rewritten = (
                rewritten.rstrip(".")
                + ". Tuy nhiên, cần có dữ liệu khảo sát đại diện để xác định tỷ lệ sử dụng cụ thể."
            )
        suggestion = SuggestedCorrection(
            original_span=claim.original_text,
            cautious_rewrite=rewritten,
            rationale="Tránh khái quát hóa tuyệt đối khi chưa có thống kê toàn diện.",
        )
    elif verdict == VerdictEnum.INSUFFICIENT_EVIDENCE and claim.missing_context_questions:
        suggestion = SuggestedCorrection(
            original_span=claim.original_text,
            cautious_rewrite=(
                f"Theo thông tin đang được đề cập (cần xác minh thêm nguồn gốc và thời điểm cụ thể): "
                f"\"{claim.original_text}\""
            ),
            rationale="Bổ sung lưu ý thận trọng và nêu rõ nguồn/thời điểm trước khi xuất bản.",
        )

    return VerificationDecision(
        verdict=verdict,
        verdict_label_vi=VERDICT_LABELS_VI[verdict],
        evidence_completeness=completeness,
        explanation=explanation,
        missing_information=claim.missing_context_questions,
        limitations=(
            "Một thông tin 'Chưa đủ bằng chứng' không đồng nghĩa với thông tin sai. "
            "Kết luận phụ thuộc vào dữ liệu công khai truy xuất được tại thời điểm kiểm tra."
        ),
        suggested_correction=suggestion,
    )


async def decide_verdict_and_explain(
    claim: ExtractedClaimCandidate,
    evidences: List[EvidenceItem],
    used_live_search: bool,
) -> VerificationDecision:
    """Runs Layer 5 Decision Logic + Anti-Hallucination Guardrails + Suggest Correction."""
    if claim.claim_type in (ClaimTypeEnum.OPINION, ClaimTypeEnum.PREDICTION, ClaimTypeEnum.SATIRE):
        return _heuristic_decision(claim, evidences, used_live_search)

    if not gemini_client.is_live or not used_live_search:
        return _heuristic_decision(claim, evidences, used_live_search)

    ev_summary = "\n\n".join(
        f"- [{e.id}] Tier {e.tier} ({e.publisher}, {e.domain}) | Stance={e.stance.value} | "
        f"CitationValidated={e.citation_validated}\n  Trích đoạn: {e.snippet}\n  Ghi chú: {e.validation_note}"
        for e in evidences
    ) or "Không tìm thấy bằng chứng trực tiếp nào."

    prompt = (
        f"Mệnh đề gốc: {claim.original_text}\n"
        f"Mệnh đề chuẩn hóa: {claim.normalized_claim}\n"
        f"Gợi ý thông tin thiếu ban đầu: {', '.join(claim.missing_context_questions) or 'Không có'}\n\n"
        f"Bằng chứng đã qua Lớp 4 kiểm định:\n{ev_summary}"
    )

    draft = await gemini_client.generate_structured(
        system_instruction=VERIFICATION_SYSTEM_PROMPT,
        prompt=prompt,
        schema=LLMVerdictDraft,
        temperature=0.1,
    )

    if draft is None:
        return _heuristic_decision(claim, evidences, used_live_search)

    safe_verdict = _enforce_anti_hallucination_guardrail(draft.verdict, claim, evidences)
    explanation = draft.explanation_vi
    if safe_verdict != draft.verdict:
        explanation = (
            f"[Cơ chế chống ảo giác đã điều chỉnh kết luận về '{VERDICT_LABELS_VI[safe_verdict]}' "
            f"do chưa có nguồn Cấp 1–4 xác thực trực tiếp trích dẫn]. {explanation}"
        )

    suggestion = None
    if draft.cautious_rewrite_vi and draft.cautious_rewrite_vi.strip():
        suggestion = SuggestedCorrection(
            original_span=claim.original_text,
            cautious_rewrite=draft.cautious_rewrite_vi.strip(),
            rationale=draft.rewrite_rationale_vi or "Diễn đạt chính xác và thận trọng hơn theo bằng chứng hiện có.",
        )

    return VerificationDecision(
        verdict=safe_verdict,
        verdict_label_vi=VERDICT_LABELS_VI[safe_verdict],
        evidence_completeness=round(draft.evidence_completeness, 2),
        explanation=explanation,
        missing_information=draft.missing_information or claim.missing_context_questions,
        limitations=draft.limitations_vi,
        suggested_correction=suggestion,
    )

