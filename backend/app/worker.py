import asyncio
import logging
from pathlib import Path
from celery import Celery

from app.core.config import settings
from app.core.database import get_db, init_db
from app.engine.layer1_ingestion import ingest_file_bytes
from app.engine.pipeline import run_verification_pipeline
from app.models.entities import DocumentJob

logger = logging.getLogger(__name__)

celery_app = Celery(
    "truecheck_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Ho_Chi_Minh",
    enable_utc=True,
    task_track_started=True,
)


async def _execute_document_job(
    job_id: str,
    file_path_str: str,
    filename: str,
    redact_pii: bool,
    use_claim_memory: bool,
) -> None:
    await init_db()
    async for db in get_db():
        job = await db.get(DocumentJob, job_id)
        if job:
            job.status = "PROCESSING"
            await db.commit()
        try:
            file_bytes = Path(file_path_str).read_bytes()
            ingested = ingest_file_bytes(file_bytes, filename=filename, redact_pii=redact_pii)
            await run_verification_pipeline(
                db=db,
                doc=ingested,
                use_claim_memory=use_claim_memory,
                existing_job_id=job_id,
                saved_file_path=file_path_str,
            )
        except Exception as exc:
            logger.exception("Document verification job %s failed: %s", job_id, exc)
            if job:
                job.status = "FAILED"
                job.error_message = str(exc)
                await db.commit()
        break


@celery_app.task(name="truecheck.process_document_job")
def process_document_job_task(
    job_id: str,
    file_path_str: str,
    filename: str,
    redact_pii: bool = False,
    use_claim_memory: bool = True,
) -> str:
    asyncio.run(
        _execute_document_job(
            job_id=job_id,
            file_path_str=file_path_str,
            filename=filename,
            redact_pii=redact_pii,
            use_claim_memory=use_claim_memory,
        )
    )
    return job_id

