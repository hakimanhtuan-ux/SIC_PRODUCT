import re
from dataclasses import dataclass, field
from typing import List


# Patterns aligned with Vietnamese Personal Data Protection Law No. 91/2025/QH15
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_VN_PHONE_RE = re.compile(r"(?:\+84|0)(?:3[2-9]|5[2689]|7[06-9]|8[1-9]|9[0-9])\d{7}\b")
_VN_CCCD_RE = re.compile(
    r"(?:(?:CCCD|CMND|căn cước|số định danh)[^\d]{0,15})?\b(?:0\d{11})\b",
    re.IGNORECASE,
)
_BANK_CARD_RE = re.compile(r"\b(?:\d[ -]*?){16}\b")

# Adversarial prompt injection indicators in English & Vietnamese
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions", re.IGNORECASE),
    re.compile(r"system\s*prompt", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(?:in\s+)?developer\s+mode", re.IGNORECASE),
    re.compile(r"bỏ\s+qua\s+(?:mọi\s+|tất\s+cả\s+)?(?:hướng\s+dẫn|chỉ\s+thị)\s+(?:trước|trên)", re.IGNORECASE),
    re.compile(r"hãy\s+luôn\s+kết\s+luận\s+(?:thông\s+tin\s+này\s+)?là\s+(?:đúng|supported)", re.IGNORECASE),
    re.compile(r"<\s*/?\s*(?:system|instruction|developer_instruction)\s*>", re.IGNORECASE),
]


@dataclass
class SecurityScanResult:
    sanitized_text: str
    has_pii: bool = False
    pii_types: List[str] = field(default_factory=list)
    privacy_notice: str | None = None
    prompt_injection_detected: bool = False
    injection_warnings: List[str] = field(default_factory=list)


def scan_and_protect_input(text: str, redact_pii: bool = False) -> SecurityScanResult:
    """
    1. Detects sensitive personal data (PII) per Vietnam Law 91/2025/QH15.
    2. Detects & neutralizes prompt injection tags so document/webpage text is
       strictly processed as untrusted data rather than LLM instructions.
    """
    working = text or ""
    pii_types: List[str] = []

    if _EMAIL_RE.search(working):
        pii_types.append("Địa chỉ Email")
        if redact_pii:
            working = _EMAIL_RE.sub("[EMAIL_ĐÃ_ẨN]", working)

    if _VN_PHONE_RE.search(working):
        pii_types.append("Số điện thoại cá nhân")
        if redact_pii:
            working = _VN_PHONE_RE.sub("[SĐT_ĐÃ_ẨN]", working)

    if _VN_CCCD_RE.search(working):
        pii_types.append("Số CCCD / Định danh cá nhân")
        if redact_pii:
            working = re.sub(r"\b0\d{11}\b", "[CCCD_ĐÃ_ẨN]", working)

    if _BANK_CARD_RE.search(working):
        pii_types.append("Số thẻ / Tài khoản")
        if redact_pii:
            working = _BANK_CARD_RE.sub("[SỐ_THẺ_ĐÃ_ẨN]", working)

    injection_warnings: List[str] = []
    for pat in _INJECTION_PATTERNS:
        if pat.search(working):
            injection_warnings.append(
                f"Phát hiện mẫu chuỗi có dấu hiệu can thiệp chỉ thị AI (Prompt Injection): '{pat.pattern[:40]}...'"
            )

    # Neutralize delimiter breakout attempts
    working = working.replace("</untrusted_content>", "[/untrusted_content]")
    working = working.replace("<untrusted_content>", "[untrusted_content]")

    privacy_notice = None
    if pii_types:
        joined = ", ".join(pii_types)
        privacy_notice = (
            f"Cảnh báo bảo vệ dữ liệu cá nhân (Luật 91/2025/QH15): Phát hiện {joined} trong nội dung. "
            + ("Hệ thống đã tự động ẩn thông tin định danh trước khi gửi tới mô hình AI." if redact_pii
               else "Bạn có thể bật chế độ 'Ẩn dữ liệu cá nhân (PII)' nếu đây là tài liệu nội bộ nhạy cảm.")
        )

    return SecurityScanResult(
        sanitized_text=working,
        has_pii=bool(pii_types),
        pii_types=pii_types,
        privacy_notice=privacy_notice,
        prompt_injection_detected=bool(injection_warnings),
        injection_warnings=injection_warnings,
    )


def wrap_untrusted_data(text: str) -> str:
    """Wraps user/web/document content in explicit XML boundaries for safe LLM prompting."""
    safe = text.replace("</untrusted_content>", "[/untrusted_content]")
    return f"<untrusted_content>\n{safe}\n</untrusted_content>"

