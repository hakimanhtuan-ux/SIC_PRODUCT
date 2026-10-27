import re
from typing import List
from pydantic import BaseModel, Field

from app.core.security import wrap_untrusted_data
from app.engine.gemini_client import gemini_client
from app.engine.layer2_claim_extraction import ExtractedClaimCandidate
from app.engine.layer3_evidence_retrieval import RawCandidateEvidence
from app.schemas.verification import (
    EvidenceEvaluationScores,
    EvidenceItem,
    EvidenceStanceEnum,
)


class SingleEvidenceAssessment(BaseModel):
    evidence_id: str
    stance: EvidenceStanceEnum = Field(
        description="SUPPORTING nếu nguồn xác nhận trực tiếp mệnh đề; REFUTING nếu nguồn bác bỏ trực tiếp; CONTEXTUAL nếu chỉ cung cấp ngữ cảnh nền"
    )
    relevance: float = Field(ge=0.0, le=1.0)
    timeliness: float = Field(ge=0.0, le=1.0)
    context_accuracy: float = Field(ge=0.0, le=1.0)
    consistency: float = Field(ge=0.0, le=1.0)
    citation_validated: bool = Field(
        description="TRUE chỉ khi đoạn trích trong nguồn thực sự chứa dữ kiện/con số trả lời trực tiếp cho mệnh đề, KHÔNG phải chỉ nhắc từ khóa chung chung"
    )
    validation_note: str = Field(
        description="Giải thích ngắn gọn vì sao nguồn này được xác thực trích dẫn hoặc chỉ mang tính ngữ cảnh"
    )


class EvidenceBatchAssessment(BaseModel):
    assessments: List[SingleEvidenceAssessment]


EVALUATION_SYSTEM_PROMPT = """Bạn là Lớp 4 (Evidence Evaluation & Citation Validation) của TrueCheck AI.
Quy tắc bắt buộc (Nguyên tắc IFCN & Chống ảo giác trích dẫn):
1. Kiểm tra nghiêm ngặt từng bằng chứng ứng viên so với mệnh đề cần xác minh.
2. CITATION VALIDATION: Chỉ đặt citation_validated = true khi đoạn trích thực sự chứa dữ kiện cụ thể ủng hộ (SUPPORTING) hoặc bác bỏ (REFUTING) trực tiếp mệnh đề đó.
   - Ví dụ: Nếu mệnh đề nói "Nhiệt độ tăng 3 độ C trong 1 năm", một bài báo chỉ nhắc chung chung "biến đổi khí hậu đang diễn ra" PHẢI có citation_validated = false và stance = CONTEXTUAL.
3. Tuyệt đối không suy diễn quá nội dung đoạn trích của nguồn."""


def _lexical_citation_sanity_check(claim_text: str, snippet: str) -> bool:
    """Secondary deterministic check ensuring snippet isn't a generic demo placeholder."""
    if "Chế độ Demo:" in snippet or len(snippet.strip()) < 25:
        return False
    tokens = [
        t for t in re.findall(r"\w+", claim_text.lower())
        if len(t) >= 3 and t not in {"trong", "những", "được", "rằng", "theo", "một", "các", "của", "cho", "thấy"}
    ]
    if not tokens:
        return True
    snip_low = snippet.lower()
    matched = sum(1 for t in set(tokens) if t in snip_low)
    return matched >= max(1, min(2, len(set(tokens)) // 3))


async def evaluate_and_validate_evidences(
    claim: ExtractedClaimCandidate,
    candidates: List[RawCandidateEvidence],
    used_live_search: bool,
) -> List[EvidenceItem]:
    """
    Layer 4 (Phần IV.5): Scores each candidate source on 6 criteria and runs Citation Validation.
    """
    if not candidates:
        return []

    if not used_live_search:
        # Offline reference portals are strictly contextual & unvalidated (honest transparency)
        return [
            EvidenceItem(
                id=c.id,
                title=c.title,
                url=c.url,
                domain=c.domain,
                publisher=c.publisher,
                published_date=c.published_date,
                tier=c.tier,
                tier_label=c.tier_label,
                stance=EvidenceStanceEnum.CONTEXTUAL,
                snippet=c.snippet,
                scores=EvidenceEvaluationScores(
                    relevance=0.55,
                    credibility=c.base_credibility,
                    timeliness=0.70,
                    context=0.60,
                    consistency=0.50,
                    traceability=1.0 if c.url.startswith("http") else 0.0,
                ),
                citation_validated=False,
                validation_note="Nguồn cổng thông tin gốc gợi ý để tra cứu trực tiếp (chưa cấu hình Search API thời gian thực).",
            )
            for c in candidates
        ]

    evidence_block = "\n\n".join(
        f"[ID={c.id}] Tier={c.tier} | Nguồn={c.publisher} ({c.domain}) | Ngày={c.published_date or 'N/A'}\n"
        f"Tiêu đề: {c.title}\n"
        f"Đoạn trích: {c.snippet}"
        for c in candidates
    )
    prompt = (
        f"Mệnh đề cần kiểm chứng: {claim.normalized_claim}\n\n"
        f"Danh sách bằng chứng thu thập được:\n{wrap_untrusted_data(evidence_block)}"
    )

    batch = await gemini_client.generate_structured(
        system_instruction=EVALUATION_SYSTEM_PROMPT,
        prompt=prompt,
        schema=EvidenceBatchAssessment,
        temperature=0.05,
    )

    assessment_map = {a.evidence_id: a for a in (batch.assessments if batch else [])}
    evaluated: List[EvidenceItem] = []

    for c in candidates:
        assessed = assessment_map.get(c.id)
        sanity_ok = _lexical_citation_sanity_check(claim.normalized_claim, c.snippet)

        if assessed is not None:
            validated = bool(assessed.citation_validated and sanity_ok)
            stance = assessed.stance if validated else EvidenceStanceEnum.CONTEXTUAL
            scores = EvidenceEvaluationScores(
                relevance=round(assessed.relevance, 2),
                credibility=round(c.base_credibility, 2),
                timeliness=round(assessed.timeliness, 2),
                context=round(assessed.context_accuracy, 2),
                consistency=round(assessed.consistency, 2),
                traceability=1.0 if c.url.startswith("http") else 0.0,
            )
            note = assessed.validation_note
        else:
            # Heuristic fallback when Search API is active but LLM is temporarily overloaded
            stance = EvidenceStanceEnum.CONTEXTUAL
            validated = False
            snip_low = (c.title + " " + c.snippet).lower()
            refute_markers = ["sai sự thật", "tin giả", "bác bỏ", "không có chuyện", "đính chính", "bịa đặt", "lừa đảo"]

            if c.from_factcheck_api and c.factcheck_textual_rating:
                rating_low = c.factcheck_textual_rating.lower()
                if any(w in rating_low for w in ["false", "sai", "giả", "bác bỏ", "fake", "pants on fire"]):
                    stance = EvidenceStanceEnum.REFUTING
                    validated = sanity_ok
                elif any(w in rating_low for w in ["true", "đúng", "chính xác", "accurate"]):
                    stance = EvidenceStanceEnum.SUPPORTING
                    validated = sanity_ok
            elif sanity_ok and c.tier <= 3:
                if any(rm in snip_low for rm in refute_markers):
                    stance = EvidenceStanceEnum.REFUTING
                    validated = True
                else:
                    # Check strong token/number overlap for Tier 1-3 authoritative sources
                    claim_nums = set(re.findall(r"\d+", claim.normalized_claim))
                    snip_nums = set(re.findall(r"\d+", snip_low))
                    if not claim_nums or (claim_nums & snip_nums):
                        stance = EvidenceStanceEnum.SUPPORTING
                        validated = True

            scores = EvidenceEvaluationScores(
                relevance=0.82 if validated else (0.65 if sanity_ok else 0.35),
                credibility=round(c.base_credibility, 2),
                timeliness=0.80,
                context=0.75 if validated else 0.60,
                consistency=0.75 if validated else 0.55,
                traceability=1.0,
            )
            note = (
                f"Đã đối chiếu khớp dữ kiện trực tiếp từ nguồn Cấp {c.tier} ({c.domain})."
                if validated
                else "Nguồn liên quan chủ đề, cung cấp ngữ cảnh tham khảo."
            )

        evaluated.append(
            EvidenceItem(
                id=c.id,
                title=c.title,
                url=c.url,
                domain=c.domain,
                publisher=c.publisher,
                published_date=c.published_date,
                tier=c.tier,
                tier_label=c.tier_label,
                stance=stance,
                snippet=c.snippet,
                scores=scores,
                citation_validated=validated,
                validation_note=note,
            )
        )

    return evaluated

