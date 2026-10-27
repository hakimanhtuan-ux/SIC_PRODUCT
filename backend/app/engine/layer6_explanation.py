import re
from typing import List
from pydantic import BaseModel, Field

from app.core.security import wrap_untrusted_data
from app.engine.gemini_client import gemini_client
from app.schemas.verification import (
    MANIPULATION_LABELS_VI,
    ManipulationSignal,
    ManipulationTypeEnum,
)


class RawManipulationSignal(BaseModel):
    signal_type: ManipulationTypeEnum
    severity: str = Field(description="LOW | MEDIUM | HIGH")
    trigger_phrase: str = Field(description="Cụm từ nguyên văn trong văn bản có dấu hiệu")
    explanation_vi: str = Field(
        description="Giải thích khách quan vì sao cách trình bày này có thể gây hiểu nhầm (không quy chụp động cơ người viết)"
    )


class ManipulationBatchOutput(BaseModel):
    signals: List[RawManipulationSignal] = Field(default_factory=list)
    summary_vi: str = Field(
        description="Nhận xét tổng quan ngắn gọn về cách trình bày ngôn từ (tách biệt hoàn toàn với độ chính xác dữ kiện)"
    )


MANIPULATION_SYSTEM_PROMPT = """Bạn là Manipulation Analysis Engine (Phần V) của TrueCheck AI.
Nhiệm vụ: Phân tích CÁCH TRÌNH BÀY NGÔN TỪ độc lập hoàn toàn với độ chính xác sự thật (Fact Accuracy).
Một văn bản có thể dùng số liệu đúng nhưng cách giật tít/chọn lọc ngữ cảnh gây hiểu nhầm, hoặc ngược lại.
Chỉ phát hiện khi có dấu hiệu rõ ràng thuộc 6 nhóm:
- CLICKBAIT: Giật tít gây sốc, che giấu thông tin cốt lõi để câu tương tác.
- EMOTIONAL_MANIPULATION: Ngôn từ kích động sợ hãi, phẫn nộ hoặc thúc giục chia sẻ khẩn cấp.
- CHERRY_PICKING: Chỉ trích một lát cắt dữ liệu thuận lợi, bỏ qua bức tranh tổng thể.
- MISLEADING_STATISTICS: Nêu tỷ lệ % lớn nhưng thiếu mẫu số, quy mô mẫu hoặc mốc cơ sở so sánh.
- FALSE_AUTHORITY: Viện dẫn "một nghiên cứu cho thấy", "các chuyên gia khẳng định" nhưng không nêu tên tổ chức/tác giả cụ thể.
- MISSING_CONTEXT: Đưa thông tin tách rời thời điểm, địa điểm hoặc điều kiện áp dụng.
Lưu ý bắt buộc: Trình bày trung lập rằng đây là dấu hiệu ngôn ngữ cần lưu ý, KHÔNG khẳng định tác giả cố tình thao túng."""


def _heuristic_manipulation_scan(text: str) -> tuple[List[ManipulationSignal], str]:
    signals: List[ManipulationSignal] = []

    rules: list[tuple[re.Pattern, ManipulationTypeEnum, str, str]] = [
        (
            re.compile(
                r"(sự thật kinh hoàng|không ai muốn bạn biết|chấn động|gây sốc|bí mật động trời)",
                re.IGNORECASE,
            ),
            ManipulationTypeEnum.CLICKBAIT,
            "HIGH",
            "Sử dụng cụm từ giật gân kích thích tò mò quá mức, dễ làm lệch trọng tâm thông tin thực tế.",
        ),
        (
            re.compile(
                r"(chia sẻ ngay kẻo xóa|cực kỳ nguy hiểm|cảnh báo khẩn cấp|đừng để bị lừa|phẫn nộ tột cùng)",
                re.IGNORECASE,
            ),
            ManipulationTypeEnum.EMOTIONAL_MANIPULATION,
            "MEDIUM",
            "Ngôn từ tạo áp lực cảm xúc (lo sợ/tức giận) hoặc thúc giục hành động lan truyền trước khi kiểm chứng.",
        ),
        (
            re.compile(
                r"(một nghiên cứu cho thấy|các chuyên gia khẳng định|nhiều nhà khoa học cảnh báo|nghiên cứu mới tiết lộ)",
                re.IGNORECASE,
            ),
            ManipulationTypeEnum.FALSE_AUTHORITY,
            "MEDIUM",
            "Viện dẫn uy tín học thuật/chuyên gia nhưng chưa nêu rõ tên tổ chức thực hiện, năm công bố và nguồn gốc.",
        ),
        (
            re.compile(r"\b\d+(?:[.,]\d+)?\s*%", re.IGNORECASE),
            ManipulationTypeEnum.MISLEADING_STATISTICS,
            "LOW",
            "Có sử dụng tỷ lệ phần trăm; người đọc cần kiểm tra rõ quy mô mẫu khảo sát, mẫu số và mốc thời gian đối chiếu.",
        ),
    ]

    for pattern, sig_type, sev, expl in rules:
        match = pattern.search(text)
        if match:
            # Skip MISLEADING_STATISTICS if sample size or specific organization is explicitly cited nearby
            if sig_type == ManipulationTypeEnum.MISLEADING_STATISTICS and re.search(
                r"(mẫu khảo sát|n\s*=\s*\d+|tổng cục thống kê|theo quyết định số)",
                text,
                re.IGNORECASE,
            ):
                continue
            signals.append(
                ManipulationSignal(
                    signal_type=sig_type,
                    label_vi=MANIPULATION_LABELS_VI[sig_type],
                    severity=sev,
                    trigger_phrase=match.group(0),
                    explanation=expl,
                )
            )

    if not signals:
        summary = "Không phát hiện dấu hiệu giật tít hoặc dẫn dắt cảm xúc bất thường trong cách diễn đạt."
    else:
        summary = (
            f"Phát hiện {len(signals)} tín hiệu ngôn ngữ cần lưu ý về cách trình bày. "
            "Lưu ý: Đánh giá này hoàn toàn độc lập với kết luận kiểm chứng dữ kiện (Fact Accuracy)."
        )
    return signals, summary


async def analyze_manipulation_signals(full_text: str) -> tuple[List[ManipulationSignal], str]:
    """Runs Manipulation Analysis Engine independently from Fact Accuracy."""
    if not full_text.strip():
        return [], "Không có nội dung để phân tích ngôn từ."

    if not gemini_client.is_live:
        return _heuristic_manipulation_scan(full_text)

    excerpt = full_text[:12000]
    output = await gemini_client.generate_structured(
        system_instruction=MANIPULATION_SYSTEM_PROMPT,
        prompt=f"Phân tích tín hiệu trình bày ngôn từ của văn bản sau:\n{wrap_untrusted_data(excerpt)}",
        schema=ManipulationBatchOutput,
        temperature=0.1,
    )

    if output is None:
        return _heuristic_manipulation_scan(full_text)

    mapped = [
        ManipulationSignal(
            signal_type=s.signal_type,
            label_vi=MANIPULATION_LABELS_VI[s.signal_type],
            severity=s.severity if s.severity in ("LOW", "MEDIUM", "HIGH") else "LOW",
            trigger_phrase=s.trigger_phrase,
            explanation=s.explanation_vi,
        )
        for s in output.signals
    ]
    return mapped, output.summary_vi

