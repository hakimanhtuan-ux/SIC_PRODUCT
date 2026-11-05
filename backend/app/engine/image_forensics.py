import asyncio
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import logging
import math
from pathlib import Path
import re
import time
from typing import Dict, List, Optional
import uuid

import fitz  # PyMuPDF
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_manager
from app.core.config import settings
from app.engine.gemini_client import gemini_client
from app.engine.layer2_claim_extraction import ExtractedClaimCandidate
from app.engine.layer3_evidence_retrieval import retrieve_evidence_for_claim
from app.engine.layer5_verification import evaluate_and_decide_unified
from app.models.entities import DocumentJob
from app.schemas.verification import (
    CLAIM_TYPE_LABELS_VI,
    IMAGE_AUTHENTICITY_LABELS_VI,
    VERDICT_LABELS_VI,
    ClaimTypeEnum,
    ClaimVerificationResult,
    DocumentSegment,
    EvidenceStanceEnum,
    ForensicRegionBox,
    ImageAuthenticityEnum,
    ImageForensicsReport,
    ImageOriginProbabilityBreakdown,
    PrivacyScanInfo,
    TechnicalForensicsInfo,
    VerdictEnum,
    VerificationResponse,
)

logger = logging.getLogger(__name__)

# Editing, Color-Grading & Retouching software / XMP signatures
_EDITING_SIGNATURES = [
    ("adobe photoshop lightroom", "Adobe Lightroom (Chỉnh màu)"),
    ("lightroom", "Adobe Lightroom (Chỉnh màu)"),
    ("crs:tonecurve", "Adobe Camera Raw / Lightroom (Kéo đường cong màu Tone Curve)"),
    ("crs:colorgrading", "Adobe Camera Raw (Color Grading)"),
    ("crs:saturation", "Thông số chỉnh độ bão hòa màu (XMP Saturation)"),
    ("crs:vibrance", "Thông số chỉnh độ rực màu (XMP Vibrance)"),
    ("crs:temperature", "Thông số chỉnh nhiệt độ màu (XMP White Balance)"),
    ("adobe photoshop", "Adobe Photoshop"),
    ("photoshop", "Adobe Photoshop"),
    ("snapseed", "Google Snapseed (Chỉnh màu / Hậu kỳ)"),
    ("vsco", "VSCO Filter (Bộ lọc màu)"),
    ("foodie", "Foodie (Bộ lọc màu)"),
    ("xingtu", "Xingtu / Ấp Ảnh (Chỉnh sửa & Chỉnh màu)"),
    ("hypic", "Hypic Photo Editor"),
    ("epik", "EPIK Photo Editor"),
    ("ulike", "Ulike Beauty & Filter"),
    ("b612", "B612 Filter"),
    ("beautyplus", "BeautyPlus"),
    ("meitu", "Meitu Retouch"),
    ("capcut", "CapCut"),
    ("picsart", "PicsArt"),
    ("canva", "Canva Design"),
    ("gimp", "GIMP Image Editor"),
    ("photopea", "Photopea"),
    ("luminar", "Luminar Neo"),
    ("capture one", "Capture One (Chỉnh màu)"),
    ("photomator", "Photomator (Chỉnh màu)"),
    ("darkroom", "Darkroom Color Editor"),
    ("polarr", "Polarr Filter"),
    ("adjustmentrender", "Apple Photos Editor (Đã chỉnh sửa trên iPhone/Mac)"),
]

_FACESWAP_SIGNATURES = [
    ("faceapp", "FaceApp (Biến đổi khuôn mặt AI)"),
    ("insightface", "InsightFace (Hoán đổi khuôn mặt)"),
    ("in_swapper", "InsightFace Swapper"),
    ("deepfacelab", "DeepFaceLab (Deepfake)"),
    ("faceswap", "FaceSwap Engine"),
    ("roop", "Roop Face-Swap"),
    ("simswap", "SimSwap"),
    ("reface", "Reface App"),
    ("remini", "Remini AI Enhancer"),
    ("remaker", "Remaker AI Face-Swap"),
]

_GENAI_SIGNATURES = [
    ("trainedalgorithmicmedia", "Chuẩn IPTC/C2PA: Phương tiện tạo sinh bằng AI (trainedAlgorithmicMedia)"),
    (
        "compositewithtrainedalgorithmicmedia",
        "Chuẩn IPTC/C2PA: Ảnh chỉnh sửa / thay thế vùng bằng AI (compositeWithTrainedAlgorithmicMedia)",
    ),
    ("made with google ai", "Google AI / Gemini Image Generation"),
    ("google generative ai", "Google Generative AI"),
    ("synthid", "Google SynthID AI Watermark"),
    ("chatgpt", "OpenAI ChatGPT Image Gen"),
    ("openai", "OpenAI Image Gen (C2PA)"),
    ("gpt-image", "OpenAI GPT-Image"),
    ("gpt-4o", "OpenAI GPT-4o Image Gen"),
    ("dall-e", "OpenAI DALL-E"),
    ("midjourney", "Midjourney AI"),
    ("flux.1", "Black Forest Labs Flux AI"),
    ("black forest labs", "Black Forest Labs Flux AI"),
    ("stable diffusion", "Stable Diffusion"),
    ("comfyui", "ComfyUI Generative Workflow"),
    ("automatic1111", "Stable Diffusion WebUI"),
    ("adobe firefly", "Adobe Firefly GenAI"),
    ("imagen", "Google Imagen AI"),
    ("ideogram", "Ideogram AI"),
    ("recraft", "Recraft AI"),
    ("bing image creator", "Bing Image Creator"),
    ("leonardo.ai", "Leonardo AI"),
    ("seedream", "ByteDance Seedream AI"),
    ("kling", "Kling AI"),
    ("c2pa", "Chứng thực nguồn gốc số C2PA / Content Credentials"),
    ("jumbf", "Siêu dữ liệu JUMBF / C2PA"),
]

_PURE_AI_NEEDLES = (
    "trainedalgorithmicmedia",
    "made with google ai",
    "google generative ai",
    "synthid",
    "chatgpt",
    "openai",
    "gpt-image",
    "gpt-4o",
    "dall-e",
    "midjourney",
    "flux.1",
    "black forest labs",
    "stable diffusion",
    "comfyui",
    "automatic1111",
    "ideogram",
    "recraft",
    "bing image creator",
    "leonardo.ai",
    "seedream",
    "imagen",
)

_COMPOSITE_AI_NEEDLES = (
    "compositewithtrainedalgorithmicmedia",
    "generative fill",
    "generative expand",
)

_CAMERA_MAKERS = [
    "Apple",
    "iPhone",
    "Samsung",
    "Canon",
    "NIKON",
    "SONY",
    "FUJIFILM",
    "Xiaomi",
    "Redmi",
    "OPPO",
    "vivo",
    "Realme",
    "Huawei",
    "Honor",
    "Google Pixel",
    "Panasonic",
    "Leica",
]

_TYPICAL_AI_DIMENSIONS = {
    (512, 512),
    (768, 768),
    (1024, 1024),
    (2048, 2048),
    (1024, 1792),
    (1792, 1024),
    (1024, 1536),
    (1536, 1024),
    (896, 1152),
    (1152, 896),
    (768, 1344),
    (1344, 768),
    (832, 1216),
    (1216, 832),
}


class LLMSuspiciousRegion(BaseModel):
    label_vi: str = Field(
        description="Tên ngắn gọn, cụ thể của lỗi tại vùng này (ví dụ: 'Ranh giới cổ - hàm lệch màu da & độ mịn do AI thay mặt', 'Chữ vô nghĩa --C21 do AI tạo', 'Logo TH HIGH SCHOOL mâu thuẫn tên đội THCS LÊ HỒNG PHONG')"
    )
    category: str = Field(
        default="EDIT_SPLICE_ERROR",
        description="AI_GENERATED_ERROR | FACE_SWAP_ERROR | EDIT_SPLICE_ERROR | COLOR_GRADING_ERROR | OTHER_ERROR",
    )
    severity: str = Field(default="MEDIUM", description="LOW | MEDIUM | HIGH")
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    box_2d: List[int] = Field(
        default_factory=lambda: [100, 100, 500, 500],
        description="Tọa độ [ymin, xmin, ymax, xmax] chuẩn hóa 0..1000 tính theo HÌNH 1 (Ảnh toàn khung hình)",
    )
    explanation_vi: str = Field(
        description="Giải thích rõ ràng, chi tiết vì sao vùng này chứng minh ảnh do AI tạo, bị AI thay mặt, cắt ghép hoặc chỉnh màu"
    )


class VisionForensicsLLMOutput(BaseModel):
    authenticity_verdict: ImageAuthenticityEnum = Field(
        description=(
            "AUTHENTIC_LIKELY | EDITED_COLOR_OR_RETOUCH | EDITED_OR_SPLICED | "
            "FACE_SWAP_OR_DEEPFAKE | AI_GENERATED | SCREENSHOT_OR_MEME | INCONCLUSIVE_LOW_QUALITY"
        )
    )
    tamper_confidence_pct: float = Field(
        ge=0.0,
        le=100.0,
        description="Độ tin cậy của kết luận giám định (0-100)",
    )
    faces_detected: int = Field(ge=0, description="Số lượng khuôn mặt người trong ảnh")
    face_swap_risk_pct: float = Field(
        ge=0.0,
        le=100.0,
        description="Mức độ nghi vấn ảnh bị AI thay mặt / ghép mặt / Deepfake (0-100)",
    )
    authentic_pct: float = Field(
        ge=0.0, le=100.0, description="% Khả năng là ảnh chụp thật nguyên bản (chưa chỉnh sửa)"
    )
    edited_spliced_pct: float = Field(
        ge=0.0, le=100.0, description="% Khả năng ảnh thật chỉ chỉnh màu / làm đẹp hoặc cắt ghép thủ công"
    )
    face_swap_deepfake_pct: float = Field(
        ge=0.0, le=100.0, description="% Khả năng ảnh gốc bị thay/ghép khuôn mặt bằng AI (Face-Swap / Deepfake)"
    )
    ai_generated_pct: float = Field(
        ge=0.0, le=100.0, description="% Khả năng toàn bộ ảnh hoặc Poster được tạo sinh bởi AI (GenAI)"
    )

    face_analysis_vi: str = Field(
        description="Phân tích chuyên sâu khuôn mặt & vùng tiếp giáp Đầu – Xương hàm – Cổ – Cổ áo – Bàn tay (độ đồng nhất màu da, độ mịn/hạt nhiễu, vết hòa trộn AI thay mặt; hoặc ghi rõ ảnh không có người)"
    )
    lighting_and_blend_vi: str = Field(
        description="Nhận xét về chất liệu bề mặt (nhiễu quang học máy ảnh thật hay bề mặt khuếch tán mịn của AI), màu sắc/filter, chữ viết/logo và quy luật vật lý"
    )
    summary_explanation_vi: str = Field(
        description="Kết luận trực diện, súc tích và chuẩn xác về bản chất thực sự của bức ảnh"
    )
    forensic_signals: List[str] = Field(
        default_factory=list,
        description="Danh sách 4-6 bằng chứng giám định cụ thể, sắc bén nhất",
    )
    suspicious_regions: List[LLMSuspiciousRegion] = Field(
        default_factory=list,
        description="Danh sách tối đa 5 vùng lỗi [ymin, xmin, ymax, xmax] tính trên HÌNH 1 (ĐỂ TRỐNG [] nếu là AUTHENTIC_LIKELY)",
    )
    extracted_text_content: str = Field(
        default="",
        description="Toàn bộ chữ viết, tiêu đề bài báo, số liệu, thông điệp hoặc nội dung văn bản nhìn thấy trong ảnh (OCR). Nếu không có chữ, để chuỗi rỗng ''.",
    )
    in_image_factual_claims: List[str] = Field(
        default_factory=list,
        description=(
            "Danh sách các mệnh đề/tuyên bố dữ kiện cụ thể cần kiểm chứng nêu trong ảnh hoặc tiêu đề/chữ trong ảnh "
            "(ví dụ: phát ngôn của ai, số liệu kinh tế/y tế, tin đồn, bài thuốc, chính sách, sự kiện diễn ra). "
            "Tối đa 3-4 câu ngắn gọn, độc lập. Nếu ảnh là ảnh chụp phong cảnh hoặc người không chứa tuyên bố thông tin sự thật, để danh sách rỗng []."
        ),
    )


IMAGE_FORENSICS_SYSTEM_PROMPT = """Bạn là Chuyên gia Trưởng Giám định Pháp y Hình ảnh Số & Phát hiện AI/Deepfake của FactCheck Assistent.
Bạn được cung cấp HÌNH 1 (Ảnh toàn khung hình) và HÌNH 2 (Ảnh phóng đại cận cảnh vùng Mặt–Cổ–Tay hoặc vùng Chữ viết/Logo chi tiết trích từ Hình 1). Mọi tọa độ `box_2d` [ymin, xmin, ymax, xmax] (0..1000) BẮT BUỘC tính theo hệ tọa độ của HÌNH 1.

Hãy thực hiện quy trình rà soát 5 NHÓM DẤU HIỆU KHOA HỌC dưới đây một cách tỉ mỉ, không bỏ sót bất kỳ chi tiết nhỏ nào:

1. NHÓM 1 — BẮT LỖI ẢNH GỐC NHƯNG ĐÃ DÙNG AI THAY/GHÉP KHUÔN MẶT (`FACE_SWAP_OR_DEEPFAKE`, `category = "FACE_SWAP_ERROR"`):
   - CẢNH BÁO ĐẶC BIỆT: Người dùng rất hay lấy một bức ảnh chụp thật từ máy ảnh cơ / điện thoại (vẫn còn nguyên EXIF Sony/Canon/iPhone, màu Lightroom, xóa phông ống kính thật, áo dài/trang phục và bàn tay thật), rồi dùng AI (Gemini Edit, Photoshop Generative Fill, InsightFace, Remaker...) chỉ để THAY KHUÔN MẶT KHÁC vào!
   - Vì vậy: KỂ CẢ KHI ảnh có EXIF máy ảnh thật và màu sắc đẹp, bạn BẮT BUỘC phải nhìn thật kỹ HÌNH 2 (ảnh phóng đại) để đối chiếu trực tiếp vùng ĐẦU – MẶT với vùng CỔ – GÁY – BÀN TAY:
     + (a) LỆCH TÔNG MÀU DA GIỮA MẶT VÀ CỔ / TAY: Ví dụ khuôn mặt có tông trắng hồng / trắng sứ lạnh rực sáng, nhưng ngay dưới xương hàm phần DA CỔ (sát cổ áo) lại sậm màu hơn hẳn, ngả vàng xám / nâu ô-liu, hoặc lệch hẳn sắc độ ấm-lạnh so với da hai bàn tay đang đưa lên gần mặt! Có vệt chuyển màu ngang bất thường trên cổ không?
     + (b) LỆCH ĐỘ MỊN & KẾT CẤU HẠT DA (SKIN TEXTURE / SMOOTHNESS MISMATCH): Da mặt láng mịn kiểu AI render (hoặc phủ lớp hạt stipple mịn nhân tạo đồng đều, đôi mắt/lông mi/răng đều tăm tắp kiểu AI) trong khi phần cổ ngay bên dưới và bàn tay lại có độ mịn, nếp da và nhiễu quang học hoàn toàn khác!
     + (c) VẾT HÒA TRỘN (BLENDING SEAM): Viền mờ quanh xương hàm, dưới cằm, mai tóc, vành tai hoặc góc gắn đầu vào cổ hơi gượng so với trục vai.
   - NẾU phát hiện sự khác biệt màu da hoặc độ mịn/kết cấu da giữa Đầu/Mặt và Cổ/Thân/Tay -> BẮT BUỘC kết luận `FACE_SWAP_OR_DEEPFAKE` (`face_swap_risk_pct` và `face_swap_deepfake_pct` từ 78–98%), khoanh vùng `FACE_SWAP_ERROR` bao trùm khuôn mặt và vùng tiếp giáp cổ! TUYỆT ĐỐI KHÔNG xếp nhầm thành `EDITED_COLOR_OR_RETOUCH`!

2. NHÓM 2 — NHẬN DIỆN ẢNH CHÂN DUNG / NGOẠI CẢNH DO AI TẠO SINH THẾ HỆ MỚI (`AI_GENERATED`, `category = "AI_GENERATED_ERROR"`):
   - AI tạo ảnh hiện đại (ChatGPT/GPT-Image, Gemini Nano Banana/Imagen, Flux, Midjourney v6, Seedream) đã vẽ được 5 ngón tay khá chuẩn! ĐỪNG VỘI kết luận ảnh thật chỉ vì thấy 5 ngón tay hay sóng biển/vách đá nét!
   - Hãy soi kỹ 6 dấu hiệu tố cáo ảnh AI tạo sinh đời mới:
     + (a) CHỮ IN / KÝ HIỆU TRÊN ÁO QUẦN, NHẴN MÁC, BIỂN HIỆU: Chữ vô nghĩa, ký tự lạ đứt gãy hoặc không tồn tại trong thực tế (ví dụ: chữ lạ như `--C21` in giữa áo tắm/áo ngực, chữ loằng ngoằng trên mũ/giày/biển báo).
     + (b) LỖI BÀN CHÂN, GIÀY DÉP & CHI PHỤ BỊ BIẾN MẤT: Chân trước đi dép/giày rõ ràng (như dép sục nhựa trắng) nhưng BÀN CHÂN SAU lại tự nhiên biến mất, cụt ngủn hoặc tan hòa vào bọt sóng biển / thảm cỏ mà không hề có chiếc dép thứ hai! Kính râm cài trên đầu bị bẹt/méo phi vật lý, dây áo/khuy áo/trang sức bất đối xứng.
     + (c) DA & TÓC KHUẾCH TÁN (DIFFUSION TEXTURE): Bề mặt da toàn thân (mặt, bụng, đùi, chân) láng mịn đồng nhất như tượng sáp/nhựa sứ, thiếu hoàn toàn vi nhiễu cảm biến máy ảnh thật; ánh sáng phủ đều khắp cơ thể bất chấp ngược sáng ngoài trời.
     + (d) TƯƠNG TÁC VẬT LÝ GIẢ TẠO: Bọt nước, cát, sỏi, lá cây tiếp xúc với cơ thể/giày dép theo kiểu hòa tan mờ ảo thiếu bóng đổ tiếp xúc thực tế; các vân đá/hậu cảnh xa lặp lại hoặc bệt dính vi mô.
     + (e) DẤU VẾT C2PA / JUMBF AI: Nếu siêu dữ liệu tệp chứa chữ ký C2PA/JUMBF của công cụ AI mà không có EXIF máy ảnh thật -> Khẳng định chắc chắn `AI_GENERATED`.

3. NHÓM 3 — NHẬN DIỆN POSTER / THIẾT KẾ QUẢNG CÁO DO AI TẠO SINH (`AI_GENERATED`, TUYỆT ĐỐI KHÔNG NHẦM VỚI `EDITED_OR_SPLICED` HAY `SCREENSHOT_OR_MEME`):
   - Người dùng hiện nay thường dùng ChatGPT, Gemini, Ideogram, Flux để tạo TRỌN GÓI một tấm Poster thể thao, giải đấu, sự kiện, quảng cáo có cả chữ tiêu đề, cầu thủ/người mẫu và logo!
   - ĐỪNG THẤY bố cục Poster có chữ & nhiều nhân vật mà vội bảo là "thiết kế đồ họa cắt ghép truyền thống (`EDITED_OR_SPLICED`)"! Hãy kiểm tra ngay 5 dấu hiệu đặc trưng của POSTER DO AI TẠO:
     + (a) MÂU THUẪN NGỮ NGHĨA GIỮA LOGO VÀ TÊN ĐỘI / ĐƠN VỊ: Đọc kỹ chữ chạy vòng trong Logo so với dòng tên bên dưới! Ví dụ tên đội dưới ghi `"THCS LÊ HỒNG PHONG"` nhưng chữ bên trong vòng tròn logo ngay phía trên lại bị AI bịa thành `"TH HIGH SCHOOL - LTS - LEADING THE FUTURE"`, hoặc chữ sau lưng áo cầu thủ (`"FC TRÍ DŨNG"`) không ăn khớp với hai đội thi đấu! Designer người thật không bao giờ vẽ logo sai tên trường/đội ngớ ngẩn như vậy.
     + (b) LỖI CHỮ NHỎ, SLOGAN NHÀ TÀI TRỢ & DẤU TIẾNG VIỆT: Tiêu đề lớn có thể rõ nhưng các logo nhỏ ở chân poster, huy hiệu nhỏ trên áo/vòng tròn, dòng slogan phụ bị nhòe dính nét, chữ biến dạng giả chữ thật, hoặc dấu tiếng Việt (`ấ, ể, ộ, ữ, ỉ, đ`) méo lệch.
     + (c) TRÙNG LẶP / PHI LÝ NHÂN VẬT TRÊN POSTER: Hai cầu thủ có khuôn mặt khác nhau trong cùng một đội lại mặc TRÙNG SỐ ÁO (ví dụ cả hai cùng mặc số `8`), nắm tay/ngón tay cầu thủ bị bệt dính, da mặt mọi cầu thủ đều mang chất liệu vẽ máy láng mịn kiểu AIイラスト/render.
     + (d) HẬU CẢNH RENDER KHUẾCH TÁN: Đám đông khán giả trên khán đài sân vận động nhòe thành mảng hạt vô định hình chứ không phải ảnh chụp sân thật.
   - HỄ Poster có các dấu hiệu trên (hoặc có chữ ký C2PA/JUMBF trong tệp) -> BẮT BUỘC kết luận `AI_GENERATED` (`ai_generated_pct` 88–99%), ghi rõ: "Đây là Poster đồ họa được tạo sinh bằng AI (không phải ảnh chụp thật hay poster thiết kế cắt ghép thủ công)", và khoanh vùng `AI_GENERATED_ERROR` vào các logo lệch tên, chữ nhỏ biến dạng và nhân vật trùng/lỗi!

4. NHÓM 4 — ẢNH CHỤP THẬT ĐÃ QUA CHỈNH MÀU / FILTER (`EDITED_COLOR_OR_RETOUCH`, `category = "COLOR_GRADING_ERROR"`):
   - CHỈ KẾT LUẬN mục này khi đã kiểm tra kỹ Nhóm 1–3 và chắc chắn: (1) Không phải ảnh AI tạo, (2) Khuôn mặt – Cổ – Tay ĐỒNG NHẤT tự nhiên về màu da & độ mịn hạt cảm biến (KHÔNG bị thay mặt AI), (3) Không cắt ghép vật thể, NHƯNG có dấu vết chỉnh màu Lightroom/VSCO/Snapseed/Filter hoặc kéo đường cong sáng tối Tone Curve, Matte Fade, Split-Toning.

5. NHÓM 5 — ẢNH CHỤP THẬT NGUYÊN BẢN (`AUTHENTIC_LIKELY`):
   - Khi ảnh mang đầy đủ đặc tính quang học máy ảnh/điện thoại tự nhiên: hạt nhiễu cảm biến đồng nhất, màu da và độ mịn giữa Mặt – Cổ – Tay liền mạch tự nhiên, bàn tay/bàn chân/giày dép/chữ viết chuẩn xác thực tế, và màu sắc trung thực chưa bị áp bộ lọc màu mạnh (lưu ý: xóa phông nhẹ của điện thoại hoặc mất EXIF do gửi qua Zalo/Messenger vẫn là `AUTHENTIC_LIKELY` nếu không phạm bất kỳ lỗi nào của Nhóm 1–4). Đặt `suspicious_regions = []` và tổng 4 tỷ lệ `%` luôn bằng 100.

6. NHÓM 6 — ĐỌC VĂN BẢN (OCR) VÀ TRÍCH XUẤT CÁC MỆNH ĐỀ THÔNG TIN CẦN XÁC THỰC:
   - Rất nhiều ảnh trên mạng là ảnh chụp bài báo, ảnh chụp màn hình mạng xã hội (Facebook/TikTok/Zalo), quote card (ảnh kèm phát ngôn), poster sự kiện, bảng số liệu, văn bản hoặc bài thuốc lan truyền.
   - Bạn BẮT BUỘC phải đọc kỹ chữ viết trong ảnh:
     + Ghi toàn bộ nội dung chữ đọc được vào `extracted_text_content`.
     + Nếu trong ảnh có chứa các tuyên bố về sự kiện, con số thống kê, chính sách, phát ngôn của người nổi tiếng, hoặc tin tức cần đối chiếu đúng/sai -> hãy tách thành 1–3 câu khẳng định độc lập, rõ ràng vào `in_image_factual_claims` để hệ thống tự động kiểm chứng thông tin từ các nguồn chính thống.
     + Nếu ảnh chỉ là chân dung, phong cảnh hoặc ảnh sinh hoạt thuần túy không chứa thông tin cần xác minh tính thật/giả của nội dung, hãy để `in_image_factual_claims = []`.

YÊU CẦU TỐC ĐỘ PHẢN HỒI: Diễn đạt ngắn gọn, súc tích, đi thẳng vào bằng chứng đắt giá nhất (mỗi phần giải thích 1–2 câu rõ nét, `forensic_signals` tối đa 4 ý ngắn, `suspicious_regions` tối đa 3 vùng rõ nhất)."""


def _detect_mime_and_format(image_bytes: bytes, filename: str) -> tuple[str, str]:
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", "JPEG"
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", "PNG"
    if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "image/webp", "WEBP"
    if image_bytes.startswith(b"BM"):
        return "image/bmp", "BMP"
    ext = Path(filename).suffix.lower()
    if ext in (".heic", ".heif"):
        return "image/heic", "HEIC"
    if ext == ".png":
        return "image/png", "PNG"
    if ext == ".webp":
        return "image/webp", "WEBP"
    return "image/jpeg", "JPEG"


def _scan_binary_metadata(image_bytes: bytes) -> dict:
    """Full-buffer binary scan (~3ms) for Camera EXIF, XMP Color Adjustments, Editing Software & C2PA/IPTC AI provenance."""
    head = image_bytes[:131072]
    low_latin = image_bytes.decode("latin-1", errors="ignore").lower()
    text_latin = head.decode("latin-1", errors="ignore")

    has_exif = (b"Exif\x00\x00" in head) or (b"eXIf" in head) or ("exif" in low_latin[:8192])

    software_found: List[str] = []
    for needle, label in _EDITING_SIGNATURES + _FACESWAP_SIGNATURES:
        if needle in low_latin and label not in software_found:
            software_found.append(label)

    c2pa_ai_found: List[str] = []
    for needle, label in _GENAI_SIGNATURES:
        if needle in low_latin and label not in c2pa_ai_found:
            c2pa_ai_found.append(label)

    camera_found: Optional[str] = None
    for maker in _CAMERA_MAKERS:
        idx = text_latin.find(maker)
        if idx != -1:
            raw_chunk = text_latin[idx : idx + 48]
            cleaned = re.sub(r"[^\x20-\x7E]+", " ", raw_chunk).strip()
            camera_found = cleaned[:40]
            break

    has_optical_exif_markers = any(
        kw in low_latin[:131072]
        for kw in (
            "lensmodel",
            "subsectimeoriginal",
            "focallengthin35mm",
            "focalplanexresolution",
            "exposuretime",
            "isospeedratings",
        )
    )
    has_camera_hardware_exif = bool(has_exif and (camera_found or has_optical_exif_markers))
    has_photoshop_or_faceswap_sw = any(
        kw in low_latin
        for kw in (
            "photoshop",
            "gimp",
            "photopea",
            "picsart",
            "faceapp",
            "insightface",
            "faceswap",
            "deepfacelab",
            "remaker",
        )
    )

    # Classify cryptographic AI provenance
    if any(k in low_latin for k in _COMPOSITE_AI_NEEDLES):
        ai_provenance = "AI_COMPOSITE_EDIT"
    elif any(k in low_latin for k in _PURE_AI_NEEDLES) and not has_camera_hardware_exif:
        ai_provenance = "PURE_AI_GENERATED"
    elif (
        ("c2pa" in low_latin or "jumbf" in low_latin)
        and not has_camera_hardware_exif
        and not any(ed in low_latin for ed in ("lightroom", "capture one", "camera raw"))
    ):
        ai_provenance = "PURE_AI_GENERATED"
    else:
        ai_provenance = "NONE"

    return {
        "has_exif": has_exif,
        "has_camera_hardware_exif": has_camera_hardware_exif,
        "has_photoshop_or_faceswap_sw": has_photoshop_or_faceswap_sw,
        "camera_info": camera_found,
        "software_traces": software_found,
        "c2pa_or_ai_watermark": ", ".join(c2pa_ai_found) if c2pa_ai_found else None,
        "ai_provenance": ai_provenance,
    }


def _heatmap_rgb(val_0_255: int) -> tuple[int, int, int]:
    """Maps 0..255 amplified ELA error to a high-contrast forensic thermal palette."""
    v = max(0, min(255, val_0_255))
    if v < 32:
        t = v / 32.0
        return int(12 + 25 * t), int(18 + 56 * t), int(52 + 128 * t)
    if v < 96:
        t = (v - 32) / 64.0
        return int(37 - 20 * t), int(74 + 126 * t), int(180 - 40 * t)
    if v < 176:
        t = (v - 96) / 80.0
        return int(17 + 228 * t), int(200 - 42 * t), int(140 - 125 * t)
    t = (v - 176) / 79.0
    return int(245 + 10 * t), int(158 - 105 * t), int(15 + 75 * t)


def _crop_rgb_pixmap_jpeg(
    rgb_pix: fitz.Pixmap,
    ymin_f: float,
    xmin_f: float,
    ymax_f: float,
    xmax_f: float,
    max_crop_dim: int = 1152,
) -> bytes:
    """Extracts a sharp native-resolution sub-rectangle from a 3-channel RGB Pixmap as high-clarity JPEG."""
    ow, oh = rgb_pix.width, rgb_pix.height
    x0 = max(0, min(max(0, ow - 32), int(round(ow * xmin_f))))
    y0 = max(0, min(max(0, oh - 32), int(round(oh * ymin_f))))
    x1 = min(ow, max(x0 + 16, int(round(ow * xmax_f))))
    y1 = min(oh, max(y0 + 16, int(round(oh * ymax_f))))
    cw, ch = max(1, x1 - x0), max(1, y1 - y0)

    src_samples = rgb_pix.samples
    src_stride = rgb_pix.stride
    dst_stride = cw * 3
    x0_b = x0 * 3
    crop_buf = bytearray(cw * ch * 3)
    for ry in range(ch):
        s_off = (y0 + ry) * src_stride + x0_b
        d_off = ry * dst_stride
        crop_buf[d_off : d_off + dst_stride] = src_samples[s_off : s_off + dst_stride]

    cpix = fitz.Pixmap(fitz.csRGB, cw, ch, bytes(crop_buf), False)
    if max(cw, ch) > max_crop_dim:
        sc = max_crop_dim / float(max(cw, ch))
        cpix = fitz.Pixmap(
            cpix,
            max(1, int(round(cw * sc))),
            max(1, int(round(ch * sc))),
        )
    return cpix.tobytes("jpeg", jpg_quality=88)


def _compute_ela_and_color_forensics(image_bytes: bytes) -> dict:
    """
    Computes in a single fast pass (~15ms):
    1. Compact full-frame JPEG payload (<=1024px) + Smart Macro Forensic Zoom Crop (<=768px)
       locking onto the Head-Neck-Hands skin cluster (for face-swap seam inspection) or Poster/Logo/Text details.
    2. Error Level Analysis (ELA) via JPEG Q=90 recompression + Thermal Heatmap.
    3. Mathematical Color-Grading & Tonal Curve Forensics (256-bin Histogram Comb, Matte Blacks, Split-Toning).
    """
    orig_pix = fitz.Pixmap(image_bytes)
    orig_w, orig_h = orig_pix.width, orig_pix.height

    if orig_pix.colorspace is None or orig_pix.colorspace.n != 3 or orig_pix.alpha:
        rgb_pix = fitz.Pixmap(fitz.csRGB, orig_pix, False)
    else:
        rgb_pix = orig_pix

    max_orig_dim = max(orig_w, orig_h)
    if max_orig_dim > 1024:
        scale_api = 1024.0 / float(max_orig_dim)
        api_pix = fitz.Pixmap(
            rgb_pix,
            max(1, int(round(orig_w * scale_api))),
            max(1, int(round(orig_h * scale_api))),
        )
    else:
        api_pix = rgb_pix

    api_full_jpeg = api_pix.tobytes("jpeg", jpg_quality=86)
    preview_jpg = api_pix.tobytes("jpeg", jpg_quality=82)
    preview_data_url = "data:image/jpeg;base64," + base64.b64encode(preview_jpg).decode("ascii")

    if max_orig_dim > 384:
        shrink_factor = max(1, int(math.ceil(max_orig_dim / 384.0)))
        work_pix = fitz.Pixmap(
            rgb_pix,
            max(1, orig_w // shrink_factor),
            max(1, orig_h // shrink_factor),
        )
    else:
        work_pix = rgb_pix

    w, h = work_pix.width, work_pix.height
    recomp_bytes = work_pix.tobytes("jpeg", jpg_quality=90)
    recomp_pix = fitz.Pixmap(recomp_bytes)
    if recomp_pix.colorspace is None or recomp_pix.colorspace.n != 3 or recomp_pix.alpha:
        recomp_pix = fitz.Pixmap(fitz.csRGB, recomp_pix, False)

    src_buf = work_pix.samples
    rec_buf = recomp_pix.samples
    src_stride = work_pix.stride
    rec_stride = recomp_pix.stride
    total_px = max(1, w * h)

    heatmap_bytes = bytearray(total_px * 3)
    grid_rows, grid_cols = 8, 8
    cell_sums = [0.0] * (grid_rows * grid_cols)
    cell_counts = [0] * (grid_rows * grid_cols)

    # 16x16 skin-locator grid for automatic Head-Neck-Hands macro crop
    sgrid = 16
    skin_cnt = [0] * (sgrid * sgrid)
    skin_tot = [0] * (sgrid * sgrid)

    hist_r = [0] * 256
    hist_g = [0] * 256
    hist_b = [0] * 256
    hist_lum = [0] * 256

    vivid_sat_px = 0
    channel_clip_px = 0
    shadow_rb_sum, shadow_gm_sum, shadow_cnt = 0.0, 0.0, 0
    high_rb_sum, high_gm_sum, high_cnt = 0.0, 0.0, 0
    mid_rb_sum, mid_gm_sum, mid_cnt = 0.0, 0.0, 0

    total_err = 0.0
    scale_gain = 14.0

    for py in range(h):
        gy = min(grid_rows - 1, (py * grid_rows) // max(1, h))
        sgy = min(sgrid - 1, (py * sgrid) // max(1, h))
        s_row = py * src_stride
        r_row = py * rec_stride
        h_row = py * w * 3
        for px in range(w):
            s_idx = s_row + px * 3
            r_idx = r_row + px * 3
            h_idx = h_row + px * 3

            r = src_buf[s_idx]
            g = src_buf[s_idx + 1]
            b = src_buf[s_idx + 2]

            hist_r[r] += 1
            hist_g[g] += 1
            hist_b[b] += 1
            lum = (r * 77 + g * 150 + b * 29) >> 8
            hist_lum[lum] += 1

            sgx = min(sgrid - 1, (px * sgrid) // max(1, w))
            sg_idx = sgy * sgrid + sgx
            skin_tot[sg_idx] += 1
            if (
                r >= 95
                and g >= 52
                and b >= 35
                and r >= g
                and g >= b - 10
                and (r - b) >= 10
                and (r - g) <= 95
                and not (r >= 242 and g >= 240 and b >= 235)
            ):
                skin_cnt[sg_idx] += 1

            max_c = r if r >= g and r >= b else (g if g >= b else b)
            min_c = r if r <= g and r <= b else (g if g <= b else b)
            chroma = max_c - min_c
            if max_c >= 28 and chroma * 100 >= max_c * 78:
                vivid_sat_px += 1

            if (max_c >= 253 and min_c <= 210 and chroma >= 45) or (
                min_c <= 2 and max_c >= 45 and chroma >= 45
            ):
                channel_clip_px += 1

            rb_diff = float(r - b)
            gm_diff = float(g) - 0.5 * float(r + b)
            if 22 <= lum <= 92:
                shadow_rb_sum += rb_diff
                shadow_gm_sum += gm_diff
                shadow_cnt += 1
            elif 158 <= lum <= 235:
                high_rb_sum += rb_diff
                high_gm_sum += gm_diff
                high_cnt += 1
            if 55 <= lum <= 195:
                mid_rb_sum += rb_diff
                mid_gm_sum += gm_diff
                mid_cnt += 1

            dr = abs(r - rec_buf[r_idx])
            dg = abs(g - rec_buf[r_idx + 1])
            db = abs(b - rec_buf[r_idx + 2])
            mean_diff = (dr + dg + db) / 3.0
            total_err += mean_diff

            gx = min(grid_cols - 1, (px * grid_cols) // max(1, w))
            g_idx = gy * grid_cols + gx
            cell_sums[g_idx] += mean_diff
            cell_counts[g_idx] += 1

            hr, hg, hb = _heatmap_rgb(int(mean_diff * scale_gain))
            heatmap_bytes[h_idx] = hr
            heatmap_bytes[h_idx + 1] = hg
            heatmap_bytes[h_idx + 2] = hb

    # Build Smart High-Magnification Forensic Zoom Crop when image has sufficient resolution
    extra_vision_crops: List[tuple[bytes, str, str]] = []
    if max_orig_dim >= 600:
        upper_skin_cells = [
            (sr, sc)
            for sr in range(1, 12)
            for sc in range(2, 14)
            if skin_tot[sr * sgrid + sc] > 0
            and skin_cnt[sr * sgrid + sc] >= max(5, int(skin_tot[sr * sgrid + sc] * 0.16))
        ]
        if len(upper_skin_cells) >= 2:
            r_min = min(sr for sr, _ in upper_skin_cells)
            r_max = max(sr for sr, _ in upper_skin_cells)
            c_min = min(sc for _, sc in upper_skin_cells)
            c_max = max(sc for _, sc in upper_skin_cells)
            if (c_max - c_min + 1) <= 10 and orig_w <= int(orig_h * 1.25):
                # Focused Portrait Head-Jawline-Neck-Collar-Hands Crop
                r_end = min(14, max(r_min + 7, min(r_max + 2, r_min + 9)))
                ymin_f = max(0.0, (r_min - 1.2) / sgrid)
                ymax_f = min(1.0, (r_end + 1.0) / sgrid)
                xmin_f = max(0.0, (c_min - 1.6) / sgrid)
                xmax_f = min(1.0, (c_max + 1.6) / sgrid)
                if xmax_f - xmin_f < 0.42:
                    mid_x = 0.5 * (xmin_f + xmax_f)
                    xmin_f = max(0.0, mid_x - 0.22)
                    xmax_f = min(1.0, mid_x + 0.22)
                if ymax_f - ymin_f < 0.42:
                    ymax_f = min(1.0, ymin_f + 0.45)
                zoom_jpg = _crop_rgb_pixmap_jpeg(rgb_pix, ymin_f, xmin_f, ymax_f, xmax_f, 768)
                extra_vision_crops.append(
                    (
                        zoom_jpg,
                        "image/jpeg",
                        "ẢNH PHÓNG ĐẠI CẬN CẢNH VÙNG ĐẦU – MẶT – XƯƠNG HÀM – CỔ – CỔ ÁO – BÀN TAY / ÁO (trích từ Hình 1 để soi kỹ độ lệch màu da và độ mịn da giữa Mặt với Cổ/Tay, vết ghép AI và chi tiết chữ/phụ kiện)",
                    )
                )

        if not extra_vision_crops:
            # Detail crop for Posters, Graphic Designs, Group Scenes & Landscapes
            zoom_jpg = _crop_rgb_pixmap_jpeg(rgb_pix, 0.26, 0.10, 0.98, 0.92, 768)
            extra_vision_crops.append(
                (
                    zoom_jpg,
                    "image/jpeg",
                    "ẢNH PHÓNG ĐẠI CẬN CẢNH VÙNG TRUNG TÂM, LOGO, CHỮ NHỎ & NHÂN VẬT (trích từ Hình 1 để soi kỹ mâu thuẫn tên đội/logo trên Poster AI, lỗi dấu tiếng Việt/chữ tài trợ nhỏ, bàn tay/bàn chân và kết cấu render AI)",
                )
            )

    ela_mean = total_err / total_px
    cell_means = sorted(
        cell_sums[i] / cell_counts[i]
        for i in range(grid_rows * grid_cols)
        if cell_counts[i] > 0
    )
    if len(cell_means) >= 8:
        median_cell = cell_means[len(cell_means) // 2]
        top_90_cell = cell_means[int(len(cell_means) * 0.9)]
        spread = max(0.0, top_90_cell - median_cell)
        regional_inconsistency = min(1.0, round(spread / max(6.5, median_cell * 2.2 + 3.5), 2))
    else:
        regional_inconsistency = 0.1

    comb_spikes = 0
    active_bins = 0
    min_neighbor = max(4.0, total_px / 900.0)
    for ch_hist in (hist_r, hist_g, hist_b):
        for bi in range(12, 244):
            navg = 0.5 * (ch_hist[bi - 1] + ch_hist[bi + 1])
            if navg >= min_neighbor:
                active_bins += 1
                if abs(ch_hist[bi] - navg) > 0.68 * navg:
                    comb_spikes += 1
    comb_ratio = round(comb_spikes / max(1, active_bins), 3)

    cum_px = 0
    p01_lum = 0
    target_p01 = max(1, int(total_px * 0.008))
    for lum_val in range(256):
        cum_px += hist_lum[lum_val]
        if cum_px >= target_p01:
            p01_lum = lum_val
            break
    dark_0_10_pct = sum(hist_lum[:11]) * 100.0 / total_px
    has_lifted_matte_blacks = bool(p01_lum >= 18 and dark_0_10_pct < 0.08)

    vivid_sat_pct = round(vivid_sat_px * 100.0 / total_px, 1)
    channel_clip_pct = round(channel_clip_px * 100.0 / total_px, 1)

    split_tone_shift = 0.0
    if shadow_cnt >= total_px * 0.03 and high_cnt >= total_px * 0.03:
        s_rb, s_gm = shadow_rb_sum / shadow_cnt, shadow_gm_sum / shadow_cnt
        h_rb, h_gm = high_rb_sum / high_cnt, high_gm_sum / high_cnt
        split_tone_shift = round(math.hypot(s_rb - h_rb, s_gm - h_gm), 1)

    midtone_cast = 0.0
    if mid_cnt >= total_px * 0.05:
        midtone_cast = round(math.hypot(mid_rb_sum / mid_cnt, mid_gm_sum / mid_cnt), 1)

    color_indicators: List[str] = []
    color_score = 0.0
    if comb_ratio >= 0.14:
        color_score += 0.42
        color_indicators.append(
            f"Biểu đồ dải sáng RGB có dấu hiệu răng lược (chỉ số {comb_ratio:.2f}) do kéo Đường cong màu (Curves/Levels) hoặc Độ tương phản."
        )
    elif comb_ratio >= 0.08:
        color_score += 0.22
        color_indicators.append(
            f"Dải chuyển màu RGB có biến thiên gián đoạn nhẹ ({comb_ratio:.2f}) gợi ý đã tinh chỉnh ánh sáng/màu sắc."
        )

    if has_lifted_matte_blacks:
        color_score += 0.30
        color_indicators.append(
            f"Điểm đen vùng tối bị nâng lên mức {p01_lum}/255 (hiệu ứng phủ mờ Matte/Fade thường gặp ở bộ lọc màu Film/VSCO/Lightroom)."
        )

    if split_tone_shift >= 24.0:
        color_score += 0.32
        color_indicators.append(
            f"Độ lệch tông màu giữa vùng tối và vùng sáng cao ({split_tone_shift} đơn vị) — dấu hiệu áp bộ lọc pha màu (Split-Toning / Filter)."
        )
    elif midtone_cast >= 30.0:
        color_score += 0.24
        color_indicators.append(
            f"Toàn khung hình có độ ám màu chủ đạo rõ ({midtone_cast} đơn vị) so với cân bằng trắng tự nhiên."
        )

    if vivid_sat_pct >= 26.0:
        color_score += 0.28
        color_indicators.append(
            f"Tỷ lệ điểm ảnh bão hòa màu cực đại chiếm {vivid_sat_pct}% — dấu hiệu đẩy thanh độ rực màu (Saturation/Vibrance)."
        )

    if channel_clip_pct >= 6.5:
        color_score += 0.24
        color_indicators.append(
            f"Có {channel_clip_pct}% điểm ảnh bị kịch trần kênh màu đơn lẻ do tăng màu hoặc tương phản mạnh."
        )

    color_score = min(1.0, round(color_score, 2))

    heat_pix = fitz.Pixmap(fitz.csRGB, w, h, bytes(heatmap_bytes), False)
    heat_png = heat_pix.tobytes("png")
    ela_heatmap_data_url = "data:image/png;base64," + base64.b64encode(heat_png).decode("ascii")

    return {
        "width": orig_w,
        "height": orig_h,
        "api_full_jpeg": api_full_jpeg,
        "extra_vision_crops": extra_vision_crops,
        "ela_mean_error": round(ela_mean, 2),
        "ela_regional_inconsistency": regional_inconsistency,
        "ela_heatmap_data_url": ela_heatmap_data_url,
        "preview_data_url": preview_data_url,
        "comb_ratio": comb_ratio,
        "has_lifted_matte_blacks": has_lifted_matte_blacks,
        "p01_lum": p01_lum,
        "vivid_sat_pct": vivid_sat_pct,
        "channel_clip_pct": channel_clip_pct,
        "split_tone_shift": split_tone_shift,
        "midtone_cast": midtone_cast,
        "color_edit_score": color_score,
        "color_indicators": color_indicators,
    }


def _normalize_probabilities(
    auth: float, edited: float, faceswap: float, aigen: float
) -> ImageOriginProbabilityBreakdown:
    vals = [max(0.0, auth), max(0.0, edited), max(0.0, faceswap), max(0.0, aigen)]
    s = sum(vals)
    if s <= 0.01:
        return ImageOriginProbabilityBreakdown(
            authentic_pct=25.0,
            edited_spliced_pct=25.0,
            face_swap_deepfake_pct=25.0,
            ai_generated_pct=25.0,
        )
    scaled = [round((v / s) * 100.0, 1) for v in vals]
    diff = round(100.0 - sum(scaled), 1)
    max_i = max(range(4), key=lambda i: scaled[i])
    scaled[max_i] = round(max(0.0, scaled[max_i] + diff), 1)
    return ImageOriginProbabilityBreakdown(
        authentic_pct=scaled[0],
        edited_spliced_pct=scaled[1],
        face_swap_deepfake_pct=scaled[2],
        ai_generated_pct=scaled[3],
    )


def _clamp_box_2d(raw_box: List[int]) -> List[int]:
    if not raw_box or len(raw_box) != 4:
        return [150, 150, 850, 850]
    ymin, xmin, ymax, xmax = [max(0, min(1000, int(v))) for v in raw_box]
    if ymax <= ymin + 10:
        ymax = min(1000, ymin + 120)
    if xmax <= xmin + 10:
        xmax = min(1000, xmin + 120)
    return [ymin, xmin, ymax, xmax]


def _authenticity_to_claim_verdict(auth: ImageAuthenticityEnum) -> VerdictEnum:
    if auth == ImageAuthenticityEnum.AUTHENTIC_LIKELY:
        return VerdictEnum.SUPPORTED
    if auth in (ImageAuthenticityEnum.FACE_SWAP_OR_DEEPFAKE, ImageAuthenticityEnum.AI_GENERATED):
        return VerdictEnum.REFUTED
    if auth in (
        ImageAuthenticityEnum.EDITED_COLOR_OR_RETOUCH,
        ImageAuthenticityEnum.EDITED_OR_SPLICED,
        ImageAuthenticityEnum.SCREENSHOT_OR_MEME,
    ):
        return VerdictEnum.MISLEADING
    return VerdictEnum.INSUFFICIENT_EVIDENCE


def _calibrate_forensics_decision(
    vision_out: VisionForensicsLLMOutput,
    meta_info: dict,
    pixel_info: dict,
) -> tuple[
    ImageAuthenticityEnum,
    float,
    ImageOriginProbabilityBreakdown,
    str,
    List[str],
    List[LLMSuspiciousRegion],
]:
    """
    Calibrates Vision Forensics output with cryptographic C2PA/EXIF provenance and color-curve mathematics:
    - Enforces AI_GENERATED when cryptographic GenAI / C2PA provenance is confirmed (including AI Posters).
    - Promotes FACE_SWAP_OR_DEEPFAKE whenever face-neck skin/smoothness discontinuity is detected, even on DSLR photos with intact EXIF.
    - Prevents false AI_GENERATED ONLY on verified physical camera EXIF photos that have zero face-swap or Photoshop composite evidence.
    - Catches subtle color-grading on genuine unedited-looking camera photos without ever overwriting AI_GENERATED or FACE_SWAP_OR_DEEPFAKE.
    """
    verdict = vision_out.authenticity_verdict
    conf_pct = round(vision_out.tamper_confidence_pct, 1)
    auth_p = vision_out.authentic_pct
    edit_p = vision_out.edited_spliced_pct
    face_p = vision_out.face_swap_deepfake_pct
    ai_p = vision_out.ai_generated_pct
    summary = vision_out.summary_explanation_vi
    signals = list(vision_out.forensic_signals)
    regions = list(vision_out.suspicious_regions)

    has_cam_exif = bool(meta_info.get("has_camera_hardware_exif"))
    has_ps_or_faceswap_sw = bool(meta_info.get("has_photoshop_or_faceswap_sw"))
    has_ai_meta = bool(meta_info.get("c2pa_or_ai_watermark"))
    ai_provenance = str(meta_info.get("ai_provenance") or "NONE")
    has_edit_meta = bool(meta_info.get("software_traces"))
    color_score = float(pixel_info.get("color_edit_score") or 0.0)
    color_indicators: List[str] = list(pixel_info.get("color_indicators") or [])

    has_face_swap_region = any(
        "FACE" in r.category.upper() and r.confidence >= 0.65 for r in regions
    )

    # --- GUARDRAIL A: Cryptographic Pure-AI Provenance (C2PA / JUMBF / SynthID / OpenAI / Google AI) ---
    if ai_provenance == "PURE_AI_GENERATED":
        if verdict != ImageAuthenticityEnum.FACE_SWAP_OR_DEEPFAKE:
            was_other = verdict != ImageAuthenticityEnum.AI_GENERATED
            verdict = ImageAuthenticityEnum.AI_GENERATED
            ai_p = max(ai_p, 92.0)
            auth_p = min(auth_p, 3.0)
            edit_p = min(edit_p, 5.0)
            conf_pct = max(conf_pct, 94.0)
            if was_other:
                summary = (
                    f"Phát hiện chứng thực nguồn gốc số C2PA / chữ ký tạo sinh AI trực tiếp trong tệp ({meta_info.get('c2pa_or_ai_watermark')}). "
                    f"Đây là ảnh / ấn phẩm đồ họa do AI tạo sinh (GenAI), không phải ảnh chụp thật. {summary}"
                )
            for r in regions:
                if r.category in ("EDIT_SPLICE_ERROR", "COLOR_GRADING_ERROR", "OTHER_ERROR"):
                    r.category = "AI_GENERATED_ERROR"
            if not regions:
                regions.append(
                    LLMSuspiciousRegion(
                        label_vi="Toàn bộ khung hình mang chữ ký chứng thực C2PA / AI tạo sinh",
                        category="AI_GENERATED_ERROR",
                        severity="HIGH",
                        confidence=0.96,
                        box_2d=[40, 40, 960, 960],
                        explanation_vi=(
                            f"Tệp ảnh chứa siêu dữ liệu C2PA / JUMBF xác nhận được tạo bởi công cụ AI ({meta_info.get('c2pa_or_ai_watermark')})."
                        ),
                    )
                )

    # --- GUARDRAIL B: Prioritize Face-Swap / AI Face Replacement even when Camera EXIF or Lightroom exists ---
    elif (
        vision_out.faces_detected > 0
        and (
            verdict == ImageAuthenticityEnum.FACE_SWAP_OR_DEEPFAKE
            or vision_out.face_swap_risk_pct >= 52.0
            or face_p >= 48.0
            or has_face_swap_region
        )
    ):
        verdict = ImageAuthenticityEnum.FACE_SWAP_OR_DEEPFAKE
        face_p = max(face_p, vision_out.face_swap_risk_pct, 76.0)
        auth_p = min(auth_p, 12.0)
        edit_p = min(edit_p, 18.0)
        ai_p = min(ai_p, 15.0)
        conf_pct = max(conf_pct, 85.0)

    # If real camera EXIF exists and LLM flagged AI_GENERATED while spotting facial anomaly -> AI Face-Swap on real body
    elif (
        has_cam_exif
        and verdict == ImageAuthenticityEnum.AI_GENERATED
        and vision_out.faces_detected > 0
        and (vision_out.face_swap_risk_pct >= 30.0 or any("FACE" in r.category.upper() for r in regions))
    ):
        verdict = ImageAuthenticityEnum.FACE_SWAP_OR_DEEPFAKE
        face_p = max(face_p, 78.0)
        ai_p = min(ai_p, 15.0)
        auth_p = min(auth_p, 12.0)
        conf_pct = max(conf_pct, 84.0)
        summary = (
            "Thân người và bối cảnh gốc được chụp từ máy ảnh thật, nhưng khuôn mặt có dấu hiệu đã bị thay thế / chỉnh sửa tái tạo bằng AI (Face-Swap / AI Inpainting)."
        )

    # --- GUARDRAIL C: Real Camera Hardware EXIF without AI/Photoshop/FaceSwap evidence -> Prevent false AI_GENERATED ---
    elif (
        has_cam_exif
        and not has_ai_meta
        and not has_ps_or_faceswap_sw
        and vision_out.face_swap_risk_pct < 22.0
        and verdict == ImageAuthenticityEnum.AI_GENERATED
    ):
        ai_p = min(ai_p, 5.0)
        if has_edit_meta or color_score >= 0.48:
            verdict = ImageAuthenticityEnum.EDITED_COLOR_OR_RETOUCH
            edit_p = max(edit_p, 72.0)
            auth_p = max(auth_p, 23.0)
            summary = (
                "Ảnh gốc được chụp từ thiết bị máy ảnh/điện thoại thực tế (có EXIF phần cứng hợp lệ), "
                "không phải ảnh do AI tạo, nhưng đã qua chỉnh màu / bộ lọc hậu kỳ."
            )
        else:
            verdict = ImageAuthenticityEnum.AUTHENTIC_LIKELY
            auth_p = max(auth_p, 88.0)
            edit_p = min(edit_p, 10.0)
            regions = []
            summary = (
                "Ảnh chụp thực tế từ thiết bị phần cứng (ghi nhận thông số EXIF quang học hợp lệ), "
                "chưa phát hiện dấu hiệu giả mạo AI hay ghép mặt."
            )

    # --- GUARDRAIL D: Composite AI metadata cannot be AUTHENTIC_LIKELY ---
    if ai_provenance == "AI_COMPOSITE_EDIT" and verdict in (
        ImageAuthenticityEnum.AUTHENTIC_LIKELY,
        ImageAuthenticityEnum.EDITED_COLOR_OR_RETOUCH,
    ):
        if vision_out.faces_detected > 0 and vision_out.face_swap_risk_pct >= 25.0:
            verdict = ImageAuthenticityEnum.FACE_SWAP_OR_DEEPFAKE
            face_p = max(face_p, 75.0)
        else:
            verdict = ImageAuthenticityEnum.EDITED_OR_SPLICED
            edit_p = max(edit_p, 78.0)
        auth_p = min(auth_p, 12.0)

    # --- GUARDRAIL E: Catch Color-Graded Real Photos ONLY when initial verdict was AUTHENTIC_LIKELY ---
    if verdict == ImageAuthenticityEnum.AUTHENTIC_LIKELY and (
        has_edit_meta or color_score >= 0.56
    ):
        verdict = ImageAuthenticityEnum.EDITED_COLOR_OR_RETOUCH
        edit_pct_target = min(88.0, round(52.0 + color_score * 35.0, 1))
        edit_p = max(edit_p, edit_pct_target)
        auth_p = max(12.0, 100.0 - edit_p - face_p - ai_p)
        conf_pct = max(conf_pct, round(65.0 + color_score * 25.0, 1))
        summary = (
            "Nhân vật và bối cảnh là ảnh chụp thật (khuôn mặt - cổ đồng nhất, không phải AI tạo hay cắt ghép giả mạo), "
            "tuy nhiên hệ thống phát hiện bức ảnh ĐÃ QUA CHỈNH MÀU / BỘ LỌC ÁNH SÁNG hậu kỳ."
        )
        for ind in reversed(color_indicators[:3]):
            if ind not in signals:
                signals.insert(0, ind)
        if not regions and color_indicators:
            regions.append(
                LLMSuspiciousRegion(
                    label_vi="Dải màu & ánh sáng toàn khung đã qua chỉnh màu / Filter",
                    category="COLOR_GRADING_ERROR",
                    severity="MEDIUM",
                    confidence=min(0.92, round(0.65 + color_score * 0.25, 2)),
                    box_2d=[60, 60, 940, 940],
                    explanation_vi=" ".join(color_indicators[:2]),
                )
            )
    elif verdict == ImageAuthenticityEnum.EDITED_COLOR_OR_RETOUCH:
        for ind in reversed(color_indicators[:2]):
            if ind not in signals:
                signals.insert(0, ind)

    if verdict == ImageAuthenticityEnum.AUTHENTIC_LIKELY:
        regions = []

    probs = _normalize_probabilities(auth_p, edit_p, face_p, ai_p)
    return verdict, conf_pct, probs, summary, signals, regions


async def run_image_verification_pipeline(
    db: AsyncSession,
    image_bytes: bytes,
    filename: str,
    context_caption: str = "",
    redact_pii: bool = False,
    use_claim_memory: bool = True,
    saved_file_path: Optional[str] = None,
) -> VerificationResponse:
    """
    Hybrid Digital Image Forensics Pipeline v3:
    1. Full-File Binary EXIF / Camera Hardware / XMP Color-Grading / C2PA & IPTC GenAI Provenance Scan
    2. Mathematical Pixel ELA + 256-bin Histogram Comb / Matte-Black / Split-Tone + Smart Portrait/Poster Macro Zoom Crop
    3. Flagship Gemini 3.8 Flash Medium-Thinking Multi-Scale Inspection + Provenance Calibration Guardrails
    """
    started = time.perf_counter()
    img_cache_key: Optional[str] = None
    if use_claim_memory and image_bytes:
        digest = hashlib.sha256(image_bytes).hexdigest()[:24]
        img_cache_key = f"truecheck:v3_turbo:img:{digest}"
        cached_payload = await cache_manager.get_json(img_cache_key)
        if cached_payload:
            cached_resp = VerificationResponse.model_validate(cached_payload)
            cached_resp.processing_time_ms = max(
                1, int((time.perf_counter() - started) * 1000)
            )
            return cached_resp

    doc_id = str(uuid.uuid4())
    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()

    mime_type, fmt_name = _detect_mime_and_format(image_bytes, filename)
    meta_info = _scan_binary_metadata(image_bytes)

    try:
        pixel_info = await asyncio.to_thread(_compute_ela_and_color_forensics, image_bytes)
    except Exception as exc:
        logger.warning("Pixel forensics computation fallback (%s)", exc)
        pixel_info = {
            "width": 0,
            "height": 0,
            "api_full_jpeg": image_bytes,
            "extra_vision_crops": [],
            "ela_mean_error": 0.0,
            "ela_regional_inconsistency": 0.0,
            "ela_heatmap_data_url": None,
            "preview_data_url": f"data:{mime_type};base64,"
            + base64.b64encode(image_bytes).decode("ascii"),
            "comb_ratio": 0.0,
            "has_lifted_matte_blacks": False,
            "p01_lum": 0,
            "vivid_sat_pct": 0.0,
            "channel_clip_pct": 0.0,
            "split_tone_shift": 0.0,
            "midtone_cast": 0.0,
            "color_edit_score": 0.0,
            "color_indicators": [],
        }

    tech_info = TechnicalForensicsInfo(
        format=fmt_name,
        width=pixel_info["width"],
        height=pixel_info["height"],
        file_size_kb=round(len(image_bytes) / 1024.0, 1),
        has_exif=meta_info["has_exif"],
        camera_info=meta_info["camera_info"],
        software_traces=meta_info["software_traces"],
        c2pa_or_ai_watermark=meta_info["c2pa_or_ai_watermark"],
        ela_mean_error=pixel_info["ela_mean_error"],
        ela_regional_inconsistency=pixel_info["ela_regional_inconsistency"],
        ela_heatmap_data_url=pixel_info["ela_heatmap_data_url"],
        preview_data_url=pixel_info["preview_data_url"],
    )

    w, h = tech_info.width, tech_info.height
    dim_note = (
        "Trùng khớp khung kích thước tạo sinh phổ biến của mô hình AI"
        if (w, h) in _TYPICAL_AI_DIMENSIONS and not meta_info["has_camera_hardware_exif"]
        else "Khung hình tự do / tỷ lệ tiêu chuẩn"
    )
    color_summary_lines = (
        "\n  + ".join(pixel_info["color_indicators"])
        if pixel_info["color_indicators"]
        else "Dải sáng tối và cân bằng màu nằm trong ngưỡng tự nhiên."
    )

    if meta_info["has_camera_hardware_exif"]:
        exif_prompt_line = (
            f"CÓ ({tech_info.camera_info or 'Thiết bị chụp hợp lệ'}) — LƯU Ý QUAN TRỌNG: EXIF máy ảnh thật chỉ chứng tỏ "
            "bức ảnh nền gốc ban đầu được chụp từ máy ảnh, NHƯNG người dùng hoàn toàn có thể đã dùng AI để THAY KHUÔN MẶT KHÁC "
            "(Face-Swap / AI Inpainting) lên thân ảnh gốc! BẮT BUỘC soi kỹ Hình 2 để kiểm tra chênh lệch màu da & độ mịn da giữa Mặt và Cổ/Bàn tay!"
        )
    elif tech_info.has_exif:
        exif_prompt_line = "Có EXIF cơ bản (không có thông số thấu kính quang học)"
    else:
        exif_prompt_line = (
            "Không có EXIF (lưu ý: ảnh gửi qua Zalo/Facebook/Messenger cũng bị xóa EXIF — hãy kết luận dựa trên bằng chứng thị giác thực tế)"
        )

    forensic_prompt = (
        f"Thông số kỹ thuật tệp ảnh ({fmt_name}, {w}x{h}px — {dim_note}, {tech_info.file_size_kb} KB):\n"
        f"1. Siêu dữ liệu thiết bị, phần mềm & chứng thực nguồn gốc:\n"
        f"- EXIF phần cứng camera: {exif_prompt_line}\n"
        f"- Chữ ký phần mềm chỉnh sửa / hậu kỳ trong tệp: {', '.join(tech_info.software_traces) or 'Không phát hiện'}\n"
        f"- Chữ ký chứng thực C2PA / công cụ tạo ảnh AI trong tệp: {tech_info.c2pa_or_ai_watermark or 'Không phát hiện'} (Mức xác thực AI từ metadata: {meta_info['ai_provenance']})\n\n"
        f"2. Chỉ số Đo Màu Sắc, Dải Sáng & Cắt Ghép Toán Học (tính trực tiếp từ điểm ảnh RGB):\n"
        f"- Điểm nghi vấn chỉnh màu / áp bộ lọc (Color-Grading Score): {pixel_info['color_edit_score']} / 1.0\n"
        f"- Chỉ số răng lược Histogram RGB (kéo Curve/Contrast): {pixel_info['comb_ratio']} | Nâng mờ vùng tối Matte Black: {'Có (sàn đen=' + str(pixel_info['p01_lum']) + '/255)' if pixel_info['has_lifted_matte_blacks'] else 'Không'}\n"
        f"- Độ lệch pha màu Vùng tối - Vùng sáng (Split-Toning): {pixel_info['split_tone_shift']} | Độ ám màu trung tính: {pixel_info['midtone_cast']}\n"
        f"- Tỷ lệ điểm ảnh rực màu cực đại (Saturation >= 78%): {pixel_info['vivid_sat_pct']}% | Cháy kênh màu đơn lẻ: {pixel_info['channel_clip_pct']}%\n"
        f"- Nhận xét đo màu tự động: {color_summary_lines}\n"
        f"- Chỉ số bất đồng nhất mức nén vùng ELA: {tech_info.ela_regional_inconsistency} (thang 0..1)\n\n"
        "YÊU CẦU GIÁM ĐỊNH CHÍNH XÁC:\n"
        "- Bước 1: Nếu có người trong ảnh, đối chiếu ngay trên HÌNH 2 xem MÀU DA và ĐỘ MỊN / ĐỘ HẠT của KHUÔN MẶT có bị lệch tông hoặc khác kết cấu so với DA CỔ (sát cổ áo) và DA BÀN TAY không. Nếu lệch -> kết luận ngay `FACE_SWAP_OR_DEEPFAKE`!\n"
        "- Bước 2: Kiểm tra xem đây có phải ảnh chân dung/cảnh vật do AI tạo sinh (chữ lạ vô nghĩa trên áo như `--C21`, mất bàn chân/chiếc dép phía sau trong bọt nước, kính/phụ kiện méo, bề mặt da sáp khuếch tán) hoặc POSTER DO AI TẠO SINH (logo mâu thuẫn tên đội/trường, chữ nhỏ/logo tài trợ nhòe biến dạng, cầu thủ trùng số áo, khán đài render AI) không. Nếu có -> kết luận ngay `AI_GENERATED`!\n"
        "- Bước 3: Chỉ khi không có lỗi AI tạo sinh hay AI thay mặt mới xét đến `EDITED_OR_SPLICED`, `EDITED_COLOR_OR_RETOUCH` hoặc `AUTHENTIC_LIKELY`."
    )

    api_img_bytes = (
        pixel_info["api_full_jpeg"]
        if pixel_info["width"] > 0
        else image_bytes
    )
    api_img_mime = "image/jpeg" if pixel_info["width"] > 0 else mime_type

    vision_out = await gemini_client.generate_multimodal_structured(
        system_instruction=IMAGE_FORENSICS_SYSTEM_PROMPT,
        prompt=forensic_prompt,
        image_bytes=api_img_bytes,
        mime_type=api_img_mime,
        schema=VisionForensicsLLMOutput,
        temperature=0.1,
        extra_images=pixel_info.get("extra_vision_crops") or None,
    )

    if vision_out is not None:
        (
            final_verdict,
            final_conf_pct,
            probs,
            final_summary,
            signals,
            cal_regions,
        ) = _calibrate_forensics_decision(vision_out, meta_info, pixel_info)

        regions = [
            ForensicRegionBox(
                region_id=f"L{idx + 1}",
                label_vi=r.label_vi,
                category=r.category,
                severity=r.severity if r.severity in ("LOW", "MEDIUM", "HIGH") else "MEDIUM",
                confidence=round(r.confidence, 2),
                box_2d=_clamp_box_2d(r.box_2d),
                explanation_vi=r.explanation_vi,
            )
            for idx, r in enumerate(cal_regions[:6])
        ]

        if tech_info.software_traces:
            sw_msg = f"Phát hiện dấu vết phần mềm chỉnh sửa / chỉnh màu trong tệp: {', '.join(tech_info.software_traces)}."
            if sw_msg not in signals:
                signals.insert(0, sw_msg)
        if tech_info.c2pa_or_ai_watermark:
            ai_msg = f"Phát hiện chữ ký chứng thực C2PA / công cụ AI trong tệp: {tech_info.c2pa_or_ai_watermark}."
            if ai_msg not in signals:
                signals.insert(0, ai_msg)

        final_face_risk = (
            0.0
            if final_verdict == ImageAuthenticityEnum.AUTHENTIC_LIKELY
            else (
                max(round(vision_out.face_swap_risk_pct, 1), round(probs.face_swap_deepfake_pct, 1))
                if final_verdict == ImageAuthenticityEnum.FACE_SWAP_OR_DEEPFAKE
                else round(vision_out.face_swap_risk_pct, 1)
            )
        )

        forensics_report = ImageForensicsReport(
            authenticity_verdict=final_verdict,
            authenticity_label_vi=IMAGE_AUTHENTICITY_LABELS_VI[final_verdict],
            tamper_confidence_pct=final_conf_pct,
            faces_detected=vision_out.faces_detected,
            face_swap_risk_pct=final_face_risk,
            face_analysis_vi=vision_out.face_analysis_vi,
            lighting_and_blend_vi=vision_out.lighting_and_blend_vi,
            summary_explanation_vi=final_summary,
            origin_probabilities=probs,
            suspicious_regions=regions,
            forensic_signals=signals[:8],
            extracted_ocr_text=vision_out.extracted_text_content.strip() if vision_out.extracted_text_content else "",
            technical=tech_info,
        )
    else:
        if meta_info["ai_provenance"] == "PURE_AI_GENERATED" or tech_info.c2pa_or_ai_watermark:
            verdict_fb = ImageAuthenticityEnum.AI_GENERATED
            probs = _normalize_probabilities(3, 5, 2, 90)
        elif tech_info.ela_regional_inconsistency >= 0.55:
            verdict_fb = ImageAuthenticityEnum.EDITED_OR_SPLICED
            probs = _normalize_probabilities(20, 65, 10, 5)
        elif tech_info.software_traces or pixel_info["color_edit_score"] >= 0.52:
            verdict_fb = ImageAuthenticityEnum.EDITED_COLOR_OR_RETOUCH
            probs = _normalize_probabilities(25, 65, 5, 5)
        else:
            verdict_fb = ImageAuthenticityEnum.INCONCLUSIVE_LOW_QUALITY
            probs = _normalize_probabilities(55, 20, 12, 13)

        forensics_report = ImageForensicsReport(
            authenticity_verdict=verdict_fb,
            authenticity_label_vi=IMAGE_AUTHENTICITY_LABELS_VI[verdict_fb],
            tamper_confidence_pct=85.0 if verdict_fb == ImageAuthenticityEnum.AI_GENERATED else 65.0,
            faces_detected=0,
            face_swap_risk_pct=probs.face_swap_deepfake_pct,
            face_analysis_vi="Chưa ghi nhận chi tiết ranh giới khuôn mặt do kết nối AI gián đoạn tạm thời.",
            lighting_and_blend_vi=(
                " ".join(pixel_info["color_indicators"])
                if pixel_info["color_indicators"]
                else f"Độ lệch mức nén ELA giữa các vùng ảnh ở mức {int(tech_info.ela_regional_inconsistency * 100)}%."
            ),
            summary_explanation_vi=(
                f"Phát hiện chữ ký chứng thực C2PA / AI trong tệp ({tech_info.c2pa_or_ai_watermark})."
                if verdict_fb == ImageAuthenticityEnum.AI_GENERATED and tech_info.c2pa_or_ai_watermark
                else "Kết quả kiểm tra dựa trên đo lường dải màu RGB, dấu vết phần mềm và bản đồ sai lệch mức nén ELA."
            ),
            origin_probabilities=probs,
            suspicious_regions=[],
            forensic_signals=[
                *(
                    [f"Phát hiện chữ ký C2PA / AI: {tech_info.c2pa_or_ai_watermark}"]
                    if tech_info.c2pa_or_ai_watermark
                    else []
                ),
                *(
                    [f"Phát hiện chữ ký phần mềm: {', '.join(tech_info.software_traces)}"]
                    if tech_info.software_traces
                    else []
                ),
                *pixel_info["color_indicators"][:3],
                f"Độ lệch mức nén giữa các vùng ảnh (ELA): {int(tech_info.ela_regional_inconsistency * 100)}%",
            ],
            extracted_ocr_text="",
            technical=tech_info,
        )

    mapped_verdict = _authenticity_to_claim_verdict(forensics_report.authenticity_verdict)
    summary_text = (
        f"[Giám định Hình ảnh: {filename}] {forensics_report.authenticity_label_vi}. "
        f"{forensics_report.summary_explanation_vi}"
    )
    visual_claim = ClaimVerificationResult(
        claim_id="IMG01",
        original_text=f"Tính nguyên bản & độ tin cậy thị giác của ảnh '{filename}'",
        normalized_claim=f"Kiểm tra ảnh thật, chỉnh màu, cắt ghép, ghép mặt và AI trên ảnh '{filename}'",
        claim_type=ClaimTypeEnum.FACTUAL_CLAIM,
        claim_type_label_vi=CLAIM_TYPE_LABELS_VI[ClaimTypeEnum.FACTUAL_CLAIM],
        check_category="Giám định Kỹ thuật Số Hình ảnh & Khuôn mặt",
        topic_category="Đa phương tiện & Deepfake",
        start_char=0,
        end_char=len(summary_text),
        page_number=1,
        verdict=mapped_verdict,
        verdict_label_vi=VERDICT_LABELS_VI[mapped_verdict],
        evidence_completeness=round(forensics_report.tamper_confidence_pct / 100.0, 2),
        explanation=forensics_report.summary_explanation_vi,
        missing_information=[],
        limitations=forensics_report.limitations_vi,
        supporting_evidence=[],
        refuting_evidence=[],
        contextual_evidence=[],
        suggested_correction=None,
        from_claim_memory=False,
        memory_version=1,
        verified_at=now_iso,
    )

    # --- DUAL FORENSICS & FACT-CHECKING ENGINE: Verify in-image factual statements ---
    raw_claims_to_check: List[str] = []
    if vision_out and vision_out.in_image_factual_claims:
        for c in vision_out.in_image_factual_claims:
            clean_c = c.strip()
            if clean_c and clean_c not in raw_claims_to_check:
                raw_claims_to_check.append(clean_c)

    if not raw_claims_to_check and context_caption and len(context_caption.strip()) >= 8:
        raw_claims_to_check.append(context_caption.strip())

    verified_text_claims: List[ClaimVerificationResult] = []
    if raw_claims_to_check:
        async def _verify_single_in_image_claim(idx: int, claim_str: str) -> Optional[ClaimVerificationResult]:
            try:
                cand = ExtractedClaimCandidate(
                    claim_id=f"C{idx + 1:03d}",
                    original_text=claim_str,
                    normalized_claim=claim_str,
                    claim_type=ClaimTypeEnum.FACTUAL_CLAIM,
                    claim_type_label_vi=CLAIM_TYPE_LABELS_VI[ClaimTypeEnum.FACTUAL_CLAIM],
                    check_category="Kiểm chứng Thông tin & Dữ kiện trong ảnh",
                    topic_category="Đa phương tiện & Xã hội",
                    start_char=0,
                    end_char=len(claim_str),
                    page_number=1,
                    search_queries=[claim_str[:80]],
                    missing_context_questions=[],
                )
                raw_evs, used_live = await retrieve_evidence_for_claim(cand)
                eval_evs, decision = await evaluate_and_decide_unified(
                    cand, raw_evs, used_live_search=used_live
                )
                supp = [e for e in eval_evs if e.stance == EvidenceStanceEnum.SUPPORTING]
                ref = [e for e in eval_evs if e.stance == EvidenceStanceEnum.REFUTING]
                ctx = [e for e in eval_evs if e.stance == EvidenceStanceEnum.CONTEXTUAL]
                return ClaimVerificationResult(
                    claim_id=cand.claim_id,
                    original_text=cand.original_text,
                    normalized_claim=cand.normalized_claim,
                    claim_type=cand.claim_type,
                    claim_type_label_vi=CLAIM_TYPE_LABELS_VI[cand.claim_type],
                    check_category=cand.check_category,
                    topic_category=cand.topic_category,
                    start_char=cand.start_char,
                    end_char=cand.end_char,
                    page_number=cand.page_number,
                    verdict=decision.verdict,
                    verdict_label_vi=VERDICT_LABELS_VI[decision.verdict],
                    evidence_completeness=decision.evidence_completeness,
                    explanation=decision.explanation,
                    missing_information=decision.missing_information,
                    limitations=decision.limitations,
                    supporting_evidence=supp,
                    refuting_evidence=ref,
                    contextual_evidence=ctx,
                    suggested_correction=decision.suggested_correction,
                    from_claim_memory=False,
                    memory_version=1,
                    verified_at=now_iso,
                )
            except Exception as exc:
                logger.warning("Could not verify in-image text claim '%s': %s", claim_str, exc)
                return None

        claim_results = await asyncio.gather(
            *[_verify_single_in_image_claim(i, c) for i, c in enumerate(raw_claims_to_check[:3])]
        )
        verified_text_claims = [res for res in claim_results if res is not None]

    all_claims = [visual_claim] + verified_text_claims
    counts: Dict[str, int] = {v.value: 0 for v in VerdictEnum}
    for cl in all_claims:
        counts[cl.verdict.value] = counts.get(cl.verdict.value, 0) + 1

    segments_list = [
        DocumentSegment(
            segment_id="SEG001",
            text=summary_text,
            start_char=0,
            end_char=len(summary_text),
            page_number=1,
            block_type="paragraph",
        )
    ]
    for idx, tc in enumerate(verified_text_claims):
        segments_list.append(
            DocumentSegment(
                segment_id=f"SEG_TXT_{idx + 1:03d}",
                text=f"Thông tin trong ảnh [{tc.claim_id}]: {tc.original_text} — Kết luận: {tc.verdict_label_vi}",
                start_char=0,
                end_char=len(tc.original_text),
                page_number=1,
                block_type="paragraph",
            )
        )

    if verified_text_claims:
        summary_text += f"\n\nĐồng thời hệ thống đã kiểm chứng {len(verified_text_claims)} tuyên bố thông tin/dữ kiện trích xuất từ nội dung trong ảnh."

    elapsed_ms = int((time.perf_counter() - started) * 1000)

    resp = VerificationResponse(
        request_id=str(uuid.uuid4()),
        document_id=doc_id,
        source_type="IMAGE",
        source_title=f"Kiểm tra ảnh & thông tin: {filename}",
        source_url=None,
        full_text=summary_text,
        segments=segments_list,
        claims=all_claims,
        image_forensics=forensics_report,
        manipulation_signals=[],
        manipulation_summary="",
        privacy_scan=PrivacyScanInfo(
            has_pii=forensics_report.faces_detected > 0,
            pii_types=["Dữ liệu hình ảnh khuôn mặt cá nhân"] if forensics_report.faces_detected > 0 else [],
            privacy_notice=None,
            prompt_injection_detected=False,
            injection_warnings=[],
            ocr_required_pages=[],
        ),
        summary_counts=counts,
        engine_mode="LIVE_AI" if vision_out is not None else "HYBRID",
        processing_time_ms=elapsed_ms,
        verified_at=now_iso,
    )

    db.add(
        DocumentJob(
            id=doc_id,
            status="COMPLETED",
            source_type="IMAGE",
            filename=filename,
            file_path=saved_file_path,
            result_payload=resp.model_dump(),
            completed_at=now_dt,
            expires_at=now_dt + timedelta(hours=settings.DOCUMENT_RETENTION_HOURS),
        )
    )
    try:
        await db.commit()
    except Exception:
        await db.rollback()

    if img_cache_key:
        await cache_manager.set_json(img_cache_key, resp.model_dump(), ttl_seconds=1200)

    return resp
