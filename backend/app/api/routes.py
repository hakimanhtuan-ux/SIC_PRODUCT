from pathlib import Path
import uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_manager
from app.core.config import settings
from app.core.database import get_db, is_postgres_active
from app.engine.exporter import generate_annotated_pdf, generate_markdown_report
from app.engine.image_forensics import run_image_verification_pipeline
from app.engine.layer1_ingestion import ingest_file_bytes, ingest_plain_text, ingest_url
from app.engine.pipeline import run_verification_pipeline
from app.models.entities import ClaimRecord, DocumentJob, FeedbackReport
from app.schemas.verification import (
    VERDICT_LABELS_VI,
    FeedbackCreateRequest,
    JobStatusResponse,
    TextVerifyRequest,
    UrlVerifyRequest,
    VerdictEnum,
    VerificationResponse,
)

router = APIRouter(prefix="/api/v1", tags=["TrueCheck Verification API"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".heic", ".heif"}
CONTENT_TYPE_TO_IMAGE_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
    "image/heic": ".heic",
    "image/heif": ".heif",
}


@router.get("/health")
async def health_check():
    redis_ok = await cache_manager.is_redis_connected()
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "database": "postgresql+pgvector" if is_postgres_active() else "sqlite_fallback",
        "redis_connected": redis_ok,
        "providers": {
            "gemini_configured": settings.has_gemini_key,
            "gemini_model": settings.GEMINI_MODEL,
            "google_factcheck_configured": settings.has_factcheck_key,
            "tavily_configured": settings.has_tavily_key,
            "google_cse_configured": settings.has_google_cse,
            "free_live_search_enabled": True,
        },
        "engine_ready_mode": (
            "LIVE_AI"
            if settings.has_gemini_key
            else "HYBRID_FREE_SEARCH"
        ),
    }


@router.post("/verify/text", response_model=VerificationResponse)
async def verify_text_endpoint(
    payload: TextVerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    ingested = ingest_plain_text(
        text=payload.text,
        title=payload.context_title or "Kiểm chứng văn bản trực tiếp",
        context_url=payload.context_url,
        redact_pii=payload.redact_pii,
    )
    return await run_verification_pipeline(
        db=db,
        doc=ingested,
        use_claim_memory=payload.use_claim_memory,
    )


@router.post("/verify/url", response_model=VerificationResponse)
async def verify_url_endpoint(
    payload: UrlVerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        ingested = await ingest_url(url=payload.url, redact_pii=payload.redact_pii)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Không thể truy xuất nội dung công khai từ URL này: {exc}",
        ) from exc

    if not ingested.full_text.strip():
        raise HTTPException(
            status_code=422,
            detail="Trang web không chứa văn bản bài viết có thể trích xuất công khai.",
        )

    return await run_verification_pipeline(
        db=db,
        doc=ingested,
        use_claim_memory=payload.use_claim_memory,
    )


@router.post("/verify/document")
async def verify_document_endpoint(
    file: UploadFile = File(...),
    redact_pii: bool = Form(False),
    use_claim_memory: bool = Form(True),
    async_mode: bool = Form(False),
    db: AsyncSession = Depends(get_db),
):
    filename = file.filename or "document.txt"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Định dạng '{ext}' chưa được hỗ trợ. Vui lòng tải lên PDF, DOCX hoặc TXT.",
        )

    file_bytes = await file.read()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Tệp vượt quá dung lượng tối đa {settings.MAX_UPLOAD_SIZE_MB}MB.",
        )
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Tệp tải lên đang trống.")

    doc_id = str(uuid.uuid4())
    saved_path = settings.STORAGE_DIR / "uploads" / f"{doc_id}{ext}"
    saved_path.write_bytes(file_bytes)

    if async_mode and await cache_manager.is_redis_connected():
        from app.worker import process_document_job_task

        job = DocumentJob(
            id=doc_id,
            status="PENDING",
            source_type="DOCUMENT",
            filename=filename,
            file_path=str(saved_path),
        )
        db.add(job)
        await db.commit()
        process_document_job_task.delay(
            job_id=doc_id,
            file_path_str=str(saved_path),
            filename=filename,
            redact_pii=redact_pii,
            use_claim_memory=use_claim_memory,
        )
        return JobStatusResponse(job_id=doc_id, status="PENDING", result=None)

    ingested = ingest_file_bytes(file_bytes=file_bytes, filename=filename, redact_pii=redact_pii)
    if not ingested.full_text.strip():
        raise HTTPException(
            status_code=422,
            detail=(
                "Không thể trích xuất văn bản từ tài liệu. "
                + (
                    f"Các trang {ingested.ocr_required_pages} là ảnh quét cần xử lý OCR chuyên sâu."
                    if ingested.ocr_required_pages
                    else "Vui lòng kiểm tra lại nội dung tệp."
                )
            ),
        )

    result = await run_verification_pipeline(
        db=db,
        doc=ingested,
        use_claim_memory=use_claim_memory,
        existing_job_id=doc_id,
        saved_file_path=str(saved_path),
    )
    return result


@router.post("/verify/image", response_model=VerificationResponse)
async def verify_image_endpoint(
    file: UploadFile = File(...),
    context_caption: str = Form(""),
    redact_pii: bool = Form(False),
    use_claim_memory: bool = Form(True),
    db: AsyncSession = Depends(get_db),
):
    filename = file.filename or "clipboard-image.png"
    ext = Path(filename).suffix.lower()
    if not ext and file.content_type in CONTENT_TYPE_TO_IMAGE_EXT:
        ext = CONTENT_TYPE_TO_IMAGE_EXT[file.content_type]
        filename = f"{filename}{ext}"

    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Định dạng ảnh '{ext or file.content_type}' chưa được hỗ trợ. "
                "Vui lòng tải lên JPG, PNG, WEBP, BMP hoặc HEIC."
            ),
        )

    file_bytes = await file.read()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Ảnh vượt quá dung lượng tối đa {settings.MAX_UPLOAD_SIZE_MB}MB.",
        )
    if len(file_bytes) < 32:
        raise HTTPException(status_code=400, detail="Tệp hình ảnh tải lên không hợp lệ hoặc bị trống.")

    uploads_dir = settings.STORAGE_DIR / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    saved_path = uploads_dir / f"{uuid.uuid4()}{ext}"
    saved_path.write_bytes(file_bytes)

    return await run_image_verification_pipeline(
        db=db,
        image_bytes=file_bytes,
        filename=filename,
        context_caption=context_caption,
        redact_pii=redact_pii,
        use_claim_memory=use_claim_memory,
        saved_file_path=str(saved_path),
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await db.get(DocumentJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên kiểm chứng tài liệu.")
    parsed = VerificationResponse.model_validate(job.result_payload) if job.result_payload else None
    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        error_message=job.error_message,
        result=parsed,
    )


@router.get("/documents/{doc_id}/export/report")
async def export_verification_report(doc_id: str, db: AsyncSession = Depends(get_db)):
    job = await db.get(DocumentJob, doc_id)
    if not job or not job.result_payload:
        raise HTTPException(status_code=404, detail="Không tìm thấy dữ liệu báo cáo kiểm chứng.")

    res = VerificationResponse.model_validate(job.result_payload)
    md_content = generate_markdown_report(res)
    headers = {
        "Content-Disposition": f'attachment; filename="truecheck-report-{doc_id[:8]}.md"'
    }
    return Response(
        content=md_content.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers=headers,
    )


@router.get("/documents/{doc_id}/export/annotated-pdf")
async def export_annotated_pdf(doc_id: str, db: AsyncSession = Depends(get_db)):
    job = await db.get(DocumentJob, doc_id)
    if not job or not job.result_payload:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu đã kiểm chứng.")

    res = VerificationResponse.model_validate(job.result_payload)
    orig_path = Path(job.file_path) if job.file_path else None
    pdf_bytes = generate_annotated_pdf(res, original_file_path=orig_path)
    headers = {
        "Content-Disposition": f'attachment; filename="truecheck-annotated-{doc_id[:8]}.pdf"'
    }
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


@router.delete("/documents/{doc_id}")
async def delete_document_data(doc_id: str, db: AsyncSession = Depends(get_db)):
    """Right-to-erasure endpoint compliant with Personal Data Protection Law 91/2025/QH15."""
    job = await db.get(DocumentJob, doc_id)
    if not job:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu.")

    if job.file_path:
        p = Path(job.file_path)
        if p.exists():
            p.unlink(missing_ok=True)

    await db.delete(job)
    await db.commit()
    return {"deleted": True, "document_id": doc_id}


@router.get("/claims/memory")
async def list_claim_memory(limit: int = 20, db: AsyncSession = Depends(get_db)):
    """Returns recent versioned Claim Memory entries and topic trends (Rumor Radar seed)."""
    stmt = select(ClaimRecord).order_by(desc(ClaimRecord.verified_at)).limit(min(limit, 50))
    records = (await db.execute(stmt)).scalars().all()

    topic_stmt = (
        select(ClaimRecord.topic_category, func.sum(ClaimRecord.hit_count))
        .group_by(ClaimRecord.topic_category)
        .order_by(desc(func.sum(ClaimRecord.hit_count)))
    )
    topic_rows = (await db.execute(topic_stmt)).all()

    items = []
    for r in records:
        v_enum = VerdictEnum(r.verdict) if r.verdict in VerdictEnum._value2member_map_ else VerdictEnum.INSUFFICIENT_EVIDENCE
        items.append({
            "id": r.id,
            "normalized_claim": r.normalized_claim,
            "topic_category": r.topic_category,
            "verdict": r.verdict,
            "verdict_label_vi": VERDICT_LABELS_VI[v_enum],
            "evidence_completeness": r.evidence_completeness,
            "version": r.version,
            "hit_count": r.hit_count,
            "verified_at": r.verified_at.isoformat(),
            "expires_at": r.expires_at.isoformat(),
            "evidence_count": len(r.evidences),
        })

    return {
        "items": items,
        "topic_trends": [
            {"topic": row[0], "total_queries": int(row[1] or 0)} for row in topic_rows
        ],
    }


@router.post("/feedback")
async def submit_feedback(
    payload: FeedbackCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    report = FeedbackReport(
        document_id=payload.document_id,
        claim_text=payload.claim_text,
        reported_verdict=payload.reported_verdict.value,
        suggested_verdict=payload.suggested_verdict.value if payload.suggested_verdict else None,
        reason=payload.reason,
        evidence_url=payload.evidence_url,
    )
    db.add(report)
    await db.commit()
    return {
        "status": "received",
        "feedback_id": report.id,
        "message": "Cảm ơn bạn đã gửi phản hồi đính chính. Hệ thống đã ghi nhận để rà soát lại bằng chứng.",
    }

