from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class VerdictEnum(str, Enum):
    SUPPORTED = "SUPPORTED"
    REFUTED = "REFUTED"
    MISLEADING = "MISLEADING"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    NOT_VERIFIABLE = "NOT_VERIFIABLE"


VERDICT_LABELS_VI: Dict[VerdictEnum, str] = {
    VerdictEnum.SUPPORTED: "Có bằng chứng hỗ trợ",
    VerdictEnum.REFUTED: "Có bằng chứng đáng tin cậy bác bỏ",
    VerdictEnum.MISLEADING: "Thiếu ngữ cảnh / Dễ gây hiểu nhầm",
    VerdictEnum.INSUFFICIENT_EVIDENCE: "Chưa đủ bằng chứng",
    VerdictEnum.CONFLICTING_EVIDENCE: "Bằng chứng mâu thuẫn",
    VerdictEnum.NOT_VERIFIABLE: "Không thể kiểm chứng khách quan",
}


class ClaimTypeEnum(str, Enum):
    FACTUAL_CLAIM = "FACTUAL_CLAIM"
    OPINION = "OPINION"
    PREDICTION = "PREDICTION"
    SATIRE = "SATIRE"
    UNVERIFIABLE = "UNVERIFIABLE"


CLAIM_TYPE_LABELS_VI: Dict[ClaimTypeEnum, str] = {
    ClaimTypeEnum.FACTUAL_CLAIM: "Mệnh đề thực tế (Có thể kiểm chứng)",
    ClaimTypeEnum.OPINION: "Quan điểm / Nhận định cá nhân",
    ClaimTypeEnum.PREDICTION: "Dự đoán tương lai",
    ClaimTypeEnum.SATIRE: "Nội dung châm biếm / Ẩn dụ",
    ClaimTypeEnum.UNVERIFIABLE: "Thiếu điều kiện xác minh khách quan",
}


class ManipulationTypeEnum(str, Enum):
    CLICKBAIT = "CLICKBAIT"
    EMOTIONAL_MANIPULATION = "EMOTIONAL_MANIPULATION"
    CHERRY_PICKING = "CHERRY_PICKING"
    MISLEADING_STATISTICS = "MISLEADING_STATISTICS"
    FALSE_AUTHORITY = "FALSE_AUTHORITY"
    MISSING_CONTEXT = "MISSING_CONTEXT"


MANIPULATION_LABELS_VI: Dict[ManipulationTypeEnum, str] = {
    ManipulationTypeEnum.CLICKBAIT: "Giật tít câu view (Clickbait)",
    ManipulationTypeEnum.EMOTIONAL_MANIPULATION: "Kích động cảm xúc (Emotional Manipulation)",
    ManipulationTypeEnum.CHERRY_PICKING: "Chọn lọc dữ liệu có lợi (Cherry Picking)",
    ManipulationTypeEnum.MISLEADING_STATISTICS: "Số liệu thiếu mẫu số / Ngữ cảnh (Misleading Statistics)",
    ManipulationTypeEnum.FALSE_AUTHORITY: "Viện dẫn chuyên gia mơ hồ (False Authority)",
    ManipulationTypeEnum.MISSING_CONTEXT: "Tách rời ngữ cảnh / Thời điểm (Missing Context)",
}


class EvidenceStanceEnum(str, Enum):
    SUPPORTING = "SUPPORTING"
    REFUTING = "REFUTING"
    CONTEXTUAL = "CONTEXTUAL"


class EvidenceEvaluationScores(BaseModel):
    relevance: float = Field(default=0.0, ge=0.0, le=1.0, description="Mức độ liên quan trực tiếp")
    credibility: float = Field(default=0.0, ge=0.0, le=1.0, description="Độ tin cậy & quy trình biên tập")
    timeliness: float = Field(default=0.0, ge=0.0, le=1.0, description="Tính cập nhật theo mốc thời gian")
    context: float = Field(default=0.0, ge=0.0, le=1.0, description="Đúng ngữ cảnh gốc")
    consistency: float = Field(default=0.0, ge=0.0, le=1.0, description="Mức độ nhất quán giữa các nguồn")
    traceability: float = Field(default=1.0, ge=0.0, le=1.0, description="Khả năng truy xuất bởi người dùng")


class EvidenceItem(BaseModel):
    id: str
    title: str
    url: str
    domain: str
    publisher: str
    published_date: Optional[str] = None
    tier: int = Field(ge=1, le=5, description="Cấp độ ưu tiên nguồn (1 cao nhất -> 5 thấp nhất)")
    tier_label: str
    stance: EvidenceStanceEnum = EvidenceStanceEnum.CONTEXTUAL
    snippet: str
    scores: EvidenceEvaluationScores
    citation_validated: bool = Field(
        default=False,
        description="Đã xác thực nội dung trong nguồn thực sự đề cập trực tiếp mệnh đề",
    )
    validation_note: str = ""


class SuggestedCorrection(BaseModel):
    original_span: str
    cautious_rewrite: str = Field(
        description="Cách diễn đạt chính xác hoặc thận trọng hơn dựa trên bằng chứng hiện có"
    )
    rationale: str = Field(description="Lý do đề xuất chỉnh sửa")
    distinction_note: str = Field(
        default="Đây là gợi ý diễn đạt thận trọng để tránh khẳng định quá mức, chỉ áp dụng khi người biên tập xác nhận."
    )


class ManipulationSignal(BaseModel):
    signal_type: ManipulationTypeEnum
    label_vi: str
    severity: str = Field(default="LOW", description="LOW | MEDIUM | HIGH")
    trigger_phrase: str = Field(description="Cụm từ / câu trong văn bản có dấu hiệu")
    explanation: str = Field(description="Giải thích vì sao cụm từ này cần lưu ý về mặt trình bày")


class DocumentSegment(BaseModel):
    segment_id: str
    text: str
    start_char: int
    end_char: int
    page_number: Optional[int] = None
    block_type: str = "paragraph"


class ClaimVerificationResult(BaseModel):
    claim_id: str
    original_text: str
    normalized_claim: str
    claim_type: ClaimTypeEnum
    claim_type_label_vi: str
    check_category: str = Field(
        default="Thông tin thực tế",
        description="Ví dụ: Số liệu thống kê, Ngày ban hành văn bản, Trích dẫn nghiên cứu, Sự kiện, Nhận định cá nhân",
    )
    topic_category: str = "Tổng hợp"
    start_char: int = 0
    end_char: int = 0
    page_number: Optional[int] = None

    verdict: VerdictEnum
    verdict_label_vi: str
    evidence_completeness: float = Field(ge=0.0, le=1.0)
    explanation: str
    missing_information: List[str] = Field(default_factory=list)
    limitations: str = ""

    supporting_evidence: List[EvidenceItem] = Field(default_factory=list)
    refuting_evidence: List[EvidenceItem] = Field(default_factory=list)
    contextual_evidence: List[EvidenceItem] = Field(default_factory=list)

    suggested_correction: Optional[SuggestedCorrection] = None

    from_claim_memory: bool = False
    memory_version: int = 1
    verified_at: str


class PrivacyScanInfo(BaseModel):
    has_pii: bool = False
    pii_types: List[str] = Field(default_factory=list)
    privacy_notice: Optional[str] = None
    prompt_injection_detected: bool = False
    injection_warnings: List[str] = Field(default_factory=list)
    ocr_required_pages: List[int] = Field(default_factory=list)


class ImageAuthenticityEnum(str, Enum):
    AUTHENTIC_LIKELY = "AUTHENTIC_LIKELY"
    EDITED_COLOR_OR_RETOUCH = "EDITED_COLOR_OR_RETOUCH"
    EDITED_OR_SPLICED = "EDITED_OR_SPLICED"
    FACE_SWAP_OR_DEEPFAKE = "FACE_SWAP_OR_DEEPFAKE"
    AI_GENERATED = "AI_GENERATED"
    SCREENSHOT_OR_MEME = "SCREENSHOT_OR_MEME"
    INCONCLUSIVE_LOW_QUALITY = "INCONCLUSIVE_LOW_QUALITY"


IMAGE_AUTHENTICITY_LABELS_VI: Dict[ImageAuthenticityEnum, str] = {
    ImageAuthenticityEnum.AUTHENTIC_LIKELY: "Ảnh Thật / Nguyên bản (Chưa phát hiện dấu hiệu giả mạo hay chỉnh sửa)",
    ImageAuthenticityEnum.EDITED_COLOR_OR_RETOUCH: "Ảnh Chụp Thật — Đã qua chỉnh màu / bộ lọc hậu kỳ",
    ImageAuthenticityEnum.EDITED_OR_SPLICED: "Không nguyên bản — Ảnh đã qua cắt ghép / chỉnh sửa chi tiết",
    ImageAuthenticityEnum.FACE_SWAP_OR_DEEPFAKE: "Cảnh báo Giả mạo — Ảnh thay / ghép khuôn mặt bằng AI (Deepfake)",
    ImageAuthenticityEnum.AI_GENERATED: "Không phải ảnh thật — Ảnh / Ấn phẩm do AI tạo sinh (GenAI)",
    ImageAuthenticityEnum.SCREENSHOT_OR_MEME: "Ấn phẩm Thiết kế Đồ họa bằng Ứng dụng (Canva / Photoshop) hoặc Ảnh chụp màn hình",
    ImageAuthenticityEnum.INCONCLUSIVE_LOW_QUALITY: "Ảnh mờ vỡ / Nén nhiều lần — Chưa đủ chi tiết kết luận",
}


class ForensicRegionBox(BaseModel):
    region_id: str
    label_vi: str = Field(description="Tên vùng nghi vấn, ví dụ: Khuôn mặt trung tâm, Vùng biển báo bị ghép...")
    category: str = Field(
        default="FACE_ANOMALY",
        description="FACE_ANOMALY | SPLICING | LIGHTING | AI_ARTIFACT | EDITED_TEXT",
    )
    severity: str = Field(default="MEDIUM", description="LOW | MEDIUM | HIGH")
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    box_2d: List[int] = Field(
        default_factory=lambda: [0, 0, 1000, 1000],
        description="[ymin, xmin, ymax, xmax] chuẩn hóa trên thang 0-1000",
    )
    explanation_vi: str = Field(description="Giải thích chi tiết dấu hiệu bất thường tại vùng này")


class ImageOriginProbabilityBreakdown(BaseModel):
    authentic_pct: float = Field(default=25.0, ge=0.0, le=100.0, description="% Khả năng ảnh gốc tự nhiên")
    edited_spliced_pct: float = Field(default=25.0, ge=0.0, le=100.0, description="% Khả năng cắt ghép / chỉnh sửa hậu kỳ")
    face_swap_deepfake_pct: float = Field(default=25.0, ge=0.0, le=100.0, description="% Khả năng ghép giả khuôn mặt / Deepfake")
    ai_generated_pct: float = Field(default=25.0, ge=0.0, le=100.0, description="% Khả năng tạo sinh hoàn toàn bằng AI")


class TechnicalForensicsInfo(BaseModel):
    format: str = "JPEG"
    width: int = 0
    height: int = 0
    file_size_kb: float = 0.0
    has_exif: bool = False
    camera_info: Optional[str] = None
    software_traces: List[str] = Field(default_factory=list)
    c2pa_or_ai_watermark: Optional[str] = None
    ela_mean_error: float = 0.0
    ela_regional_inconsistency: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Độ lệch chuẩn mức nén ELA giữa các vùng (cao gợi ý vùng ảnh ghép mới)",
    )
    ela_heatmap_data_url: Optional[str] = None
    preview_data_url: Optional[str] = None


class ImageForensicsReport(BaseModel):
    authenticity_verdict: ImageAuthenticityEnum
    authenticity_label_vi: str
    tamper_confidence_pct: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Mức độ rõ ràng của bằng chứng kỹ thuật (0-100%)",
    )
    faces_detected: int = 0
    face_swap_risk_pct: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Mức độ rủi ro ghép giả khuôn mặt / Deepfake (0-100%)",
    )
    face_analysis_vi: str = ""
    lighting_and_blend_vi: str = ""
    summary_explanation_vi: str = ""
    origin_probabilities: ImageOriginProbabilityBreakdown
    suspicious_regions: List[ForensicRegionBox] = Field(default_factory=list)
    forensic_signals: List[str] = Field(default_factory=list)
    extracted_ocr_text: str = ""
    limitations_vi: str = (
        "Phân tích giám định ảnh số kết hợp ELA, siêu dữ liệu EXIF/C2PA và thị giác đa phương thức AI. "
        "Ảnh bị nén lại qua mạng xã hội (Facebook, Zalo) có thể làm mờ dấu vết EXIF gốc."
    )
    technical: TechnicalForensicsInfo


class VerificationResponse(BaseModel):
    request_id: str
    document_id: str
    source_type: str = Field(description="TEXT | DOCUMENT | URL | IMAGE")
    source_title: str = "Văn bản kiểm chứng"
    source_url: Optional[str] = None

    full_text: str
    segments: List[DocumentSegment] = Field(default_factory=list)
    claims: List[ClaimVerificationResult] = Field(default_factory=list)
    image_forensics: Optional[ImageForensicsReport] = None

    # Manipulation Analysis Engine (kept strictly independent from Fact Accuracy per Phần V)
    manipulation_signals: List[ManipulationSignal] = Field(default_factory=list)
    manipulation_summary: str = ""

    privacy_scan: PrivacyScanInfo
    summary_counts: Dict[str, int] = Field(default_factory=dict)
    engine_mode: str = Field(default="LIVE_AI", description="LIVE_AI | HYBRID | DEMO_FALLBACK")
    processing_time_ms: int
    verified_at: str


# --- API Request Models ---

class TextVerifyRequest(BaseModel):
    text: str = Field(..., min_length=5, max_length=30000, description="Đoạn văn bản cần kiểm chứng")
    context_url: Optional[str] = Field(default=None, description="URL trang web nơi đoạn văn bản xuất hiện (từ Extension)")
    context_title: Optional[str] = Field(default=None, description="Tiêu đề bài viết nguồn")
    redact_pii: bool = Field(default=False, description="Tự động ẩn thông tin định danh cá nhân (Luật 91/2025/QH15)")
    use_claim_memory: bool = Field(default=True, description="Tái sử dụng kết quả còn hiệu lực trong Claim Memory")


class UrlVerifyRequest(BaseModel):
    url: str = Field(..., min_length=8, max_length=2048, description="Đường dẫn bài báo / trang web cần kiểm chứng")
    redact_pii: bool = False
    use_claim_memory: bool = True


class FeedbackCreateRequest(BaseModel):
    document_id: Optional[str] = None
    claim_text: str = Field(..., min_length=5)
    reported_verdict: VerdictEnum
    suggested_verdict: Optional[VerdictEnum] = None
    reason: str = Field(..., min_length=10, max_length=2000)
    evidence_url: Optional[str] = None


class JobStatusResponse(BaseModel):
    job_id: str
    status: str = Field(description="PENDING | PROCESSING | COMPLETED | FAILED")
    error_message: Optional[str] = None
    result: Optional[VerificationResponse] = None

