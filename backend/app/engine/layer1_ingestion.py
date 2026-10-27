import io
import re
from dataclasses import dataclass, field
from typing import List, Optional
from bs4 import BeautifulSoup
import httpx

from app.core.security import SecurityScanResult, scan_and_protect_input
from app.schemas.verification import DocumentSegment


@dataclass
class IngestedDocument:
    source_type: str  # TEXT | DOCUMENT | URL
    source_title: str
    source_url: Optional[str]
    full_text: str
    segments: List[DocumentSegment]
    security_scan: SecurityScanResult
    ocr_required_pages: List[int] = field(default_factory=list)


def _build_segments_from_paragraphs(
    paragraphs: List[tuple[str, Optional[int]]],
) -> tuple[str, List[DocumentSegment]]:
    """
    Constructs unified full_text and exact character-offset DocumentSegments
    so every claim can be highlighted accurately on the UI and Annotated PDF.
    """
    segments: List[DocumentSegment] = []
    cursor = 0
    chunks: List[str] = []

    for idx, (raw_para, page_no) in enumerate(paragraphs):
        cleaned = re.sub(r"[ \t]+", " ", raw_para).strip()
        if not cleaned:
            continue
        if chunks:
            chunks.append("\n\n")
            cursor += 2
        start_char = cursor
        end_char = start_char + len(cleaned)
        chunks.append(cleaned)
        cursor = end_char
        segments.append(
            DocumentSegment(
                segment_id=f"SEG-{idx + 1:03d}",
                text=cleaned,
                start_char=start_char,
                end_char=end_char,
                page_number=page_no,
                block_type="paragraph",
            )
        )

    return "".join(chunks), segments


def ingest_plain_text(
    text: str,
    title: str = "Văn bản kiểm chứng trực tiếp",
    context_url: Optional[str] = None,
    redact_pii: bool = False,
) -> IngestedDocument:
    scan = scan_and_protect_input(text, redact_pii=redact_pii)
    raw_blocks = [blk for blk in re.split(r"\n\s*\n|\r\n\s*\r\n", scan.sanitized_text) if blk.strip()]
    if not raw_blocks and scan.sanitized_text.strip():
        raw_blocks = [scan.sanitized_text.strip()]
    paragraphs = [(blk, None) for blk in raw_blocks]
    full_text, segments = _build_segments_from_paragraphs(paragraphs)
    return IngestedDocument(
        source_type="TEXT",
        source_title=title,
        source_url=context_url,
        full_text=full_text,
        segments=segments,
        security_scan=scan,
    )


def ingest_file_bytes(
    file_bytes: bytes,
    filename: str,
    redact_pii: bool = False,
) -> IngestedDocument:
    """
    Layer 1 Document Processor (Phần IV.2):
    Supports PDF (PyMuPDF with page coordinates + selective OCR detection),
    DOCX (python-docx paragraphs & tables), and TXT/MD.
    """
    lower_name = filename.lower()
    paragraphs_with_page: List[tuple[str, Optional[int]]] = []
    ocr_pages: List[int] = []

    if lower_name.endswith(".pdf"):
        import fitz  # PyMuPDF

        doc = fitz.open(stream=file_bytes, filetype="pdf")
        try:
            for page_idx in range(len(doc)):
                page = doc[page_idx]
                page_num = page_idx + 1
                blocks = page.get_text("blocks")
                extracted_page_chars = 0
                for blk in blocks:
                    # blk: (x0, y0, x1, y1, "text", block_no, block_type)
                    if len(blk) >= 7 and blk[6] == 0:
                        blk_text = str(blk[4]).strip()
                        if blk_text:
                            extracted_page_chars += len(blk_text)
                            paragraphs_with_page.append((blk_text, page_num))
                # Selective OCR detection: only flag scanned image pages with near-zero text
                if extracted_page_chars < 25 and len(page.get_images()) > 0:
                    ocr_pages.append(page_num)
        finally:
            doc.close()

    elif lower_name.endswith(".docx"):
        import docx

        document = docx.Document(io.BytesIO(file_bytes))
        for para in document.paragraphs:
            if para.text and para.text.strip():
                paragraphs_with_page.append((para.text.strip(), None))
        for table in document.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells if c.text and c.text.strip()]
                if cells:
                    paragraphs_with_page.append((" | ".join(cells), None))

    else:
        decoded = ""
        for enc in ("utf-8-sig", "utf-8", "cp1258", "latin-1"):
            try:
                decoded = file_bytes.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        for blk in re.split(r"\n\s*\n", decoded):
            if blk.strip():
                paragraphs_with_page.append((blk.strip(), None))

    combined_raw = "\n\n".join(p[0] for p in paragraphs_with_page)
    scan = scan_and_protect_input(combined_raw, redact_pii=redact_pii)

    if redact_pii and scan.has_pii:
        # Re-apply PII redaction per paragraph while preserving page numbers
        sanitized_paras = [
            (scan_and_protect_input(p_text, redact_pii=True).sanitized_text, p_page)
            for p_text, p_page in paragraphs_with_page
        ]
    else:
        sanitized_paras = [
            (p_text.replace("</untrusted_content>", "[/untrusted_content]"), p_page)
            for p_text, p_page in paragraphs_with_page
        ]

    full_text, segments = _build_segments_from_paragraphs(sanitized_paras)
    return IngestedDocument(
        source_type="DOCUMENT",
        source_title=filename,
        source_url=None,
        full_text=full_text,
        segments=segments,
        security_scan=scan,
        ocr_required_pages=ocr_pages,
    )


async def ingest_url(url: str, redact_pii: bool = False) -> IngestedDocument:
    """Fetches public article content from a URL and extracts structured paragraphs."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 "
            "TrueCheckBot/0.1"
        ),
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=headers) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        html = resp.text

    soup = BeautifulSoup(html, "lxml")
    title = (soup.title.string.strip() if soup.title and soup.title.string else url)

    for noisy in soup(["script", "style", "noscript", "nav", "footer", "header", "aside", "form", "iframe"]):
        noisy.decompose()

    container = soup.find("article") or soup.find("main") or soup.body or soup
    paragraphs: List[tuple[str, Optional[int]]] = []

    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        paragraphs.append((h1.get_text(" ", strip=True), None))

    for tag in container.find_all(["p", "h2", "h3", "li"]):
        txt = tag.get_text(" ", strip=True)
        if len(txt) >= 35:
            paragraphs.append((txt, None))

    if not paragraphs:
        fallback = container.get_text("\n", strip=True)
        paragraphs = [(blk, None) for blk in fallback.split("\n") if len(blk.strip()) >= 30]

    combined_raw = "\n\n".join(p[0] for p in paragraphs[:60])
    scan = scan_and_protect_input(combined_raw, redact_pii=redact_pii)

    processed_paras = [
        (scan_and_protect_input(p[0], redact_pii=redact_pii).sanitized_text, None)
        for p in paragraphs[:60]
    ]
    full_text, segments = _build_segments_from_paragraphs(processed_paras)

    return IngestedDocument(
        source_type="URL",
        source_title=title,
        source_url=url,
        full_text=full_text,
        segments=segments,
        security_scan=scan,
    )

