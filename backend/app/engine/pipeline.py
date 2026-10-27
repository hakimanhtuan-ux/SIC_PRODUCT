import asyncio
import hashlib
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_manager
from app.core.config import settings
from app.engine.gemini_client import gemini_client
from app.engine.layer1_ingestion import IngestedDocument
from app.engine.layer2_claim_extraction import ExtractedClaimCandidate, extract_claims
from app.engine.layer3_evidence_retrieval import lookup_claim_memory, retrieve_evidence_for_claim
from app.engine.layer4_evidence_evaluation import evaluate_and_validate_evidences
from app.engine.layer5_verification import decide_verdict_and_explain
from app.engine.layer6_explanation import analyze_manipulation_signals
from app.models.entities import ClaimRecord, DocumentJob, EvidenceRecord
from app.schemas.verification import (
    CLAIM_TYPE_LABELS_VI,
    VERDICT_LABELS_VI,
    ClaimTypeEnum,
    ClaimVerificationResult,
    EvidenceEvaluationScores,
    EvidenceItem,
    EvidenceStanceEnum,
    PrivacyScanInfo,
    SuggestedCorrection,
    VerdictEnum,
    VerificationResponse,
)


def _claim_record_to_result(
    record: ClaimRecord,
    candidate: ExtractedClaimCandidate,
) -> ClaimVerificationResult:
    verdict_enum = VerdictEnum(record.verdict)
    supp: List[EvidenceItem] = []
    ref: List[EvidenceItem] = []
    ctx: List[EvidenceItem] = []

    for ev in record.evidences:
        stance_enum = EvidenceStanceEnum(ev.stance)
        item = EvidenceItem(
            id=ev.id[:8],
            title=ev.title,
            url=ev.url,
            domain=ev.domain,
            publisher=ev.publisher,
            published_date=ev.published_date,
            tier=ev.tier,
            tier_label=ev.tier_label,
            stance=stance_enum,
            snippet=ev.snippet,
            scores=EvidenceEvaluationScores(**(ev.scores or {})),
            citation_validated=ev.citation_validated,
            validation_note=ev.validation_note,
        )
        if stance_enum == EvidenceStanceEnum.SUPPORTING:
            supp.append(item)
        elif stance_enum == EvidenceStanceEnum.REFUTING:
            ref.append(item)
        else:
            ctx.append(item)

    suggestion = (
        SuggestedCorrection(**record.suggested_correction)
        if isinstance(record.suggested_correction, dict)
        else None
    )

    return ClaimVerificationResult(
        claim_id=candidate.claim_id,
        original_text=candidate.original_text,
        normalized_claim=record.normalized_claim,
        claim_type=candidate.claim_type,
        claim_type_label_vi=CLAIM_TYPE_LABELS_VI[candidate.claim_type],
        check_category=candidate.check_category,
        topic_category=record.topic_category or candidate.topic_category,
        start_char=candidate.start_char,
        end_char=candidate.end_char,
        page_number=candidate.page_number,
        verdict=verdict_enum,
        verdict_label_vi=VERDICT_LABELS_VI[verdict_enum],
        evidence_completeness=record.evidence_completeness,
        explanation=record.explanation,
        missing_information=record.missing_information or [],
        limitations=record.limitations,
        supporting_evidence=supp,
        refuting_evidence=ref,
        contextual_evidence=ctx,
        suggested_correction=suggestion,
        from_claim_memory=True,
        memory_version=record.version,
        verified_at=record.verified_at.isoformat(),
    )


async def _verify_single_claim(
    db: AsyncSession,
    candidate: ExtractedClaimCandidate,
    use_claim_memory: bool,
) -> tuple[ClaimVerificationResult, bool]:
    """
    Runs Layers 3 -> 4 -> 5 for a single atomic claim and persists to Claim Memory.
    Returns (ClaimVerificationResult, used_live_search).
    """
    embedding: list[float] | None = None
    if use_claim_memory and candidate.claim_type == ClaimTypeEnum.FACTUAL_CLAIM:
        cached_rec, embedding = await lookup_claim_memory(db, candidate.normalized_claim)
        if cached_rec is not None:
            return _claim_record_to_result(cached_rec, candidate), True

    raw_evidences, used_live_search = await retrieve_evidence_for_claim(candidate)
    evaluated_evidences = await evaluate_and_validate_evidences(
        candidate, raw_evidences, used_live_search=used_live_search
    )
    decision = await decide_verdict_and_explain(
        candidate, evaluated_evidences, used_live_search=used_live_search
    )

    supp = [e for e in evaluated_evidences if e.stance == EvidenceStanceEnum.SUPPORTING]
    ref = [e for e in evaluated_evidences if e.stance == EvidenceStanceEnum.REFUTING]
    ctx = [e for e in evaluated_evidences if e.stance == EvidenceStanceEnum.CONTEXTUAL]

    now = datetime.now(timezone.utc)

    # Persist into Versioned Claim Memory when factual & live search or explicit analysis ran
    if candidate.claim_type == ClaimTypeEnum.FACTUAL_CLAIM and used_live_search:
        if embedding is None:
            embedding = await gemini_client.embed_text(candidate.normalized_claim)
        claim_rec = ClaimRecord(
            normalized_claim=candidate.normalized_claim,
            claim_type=candidate.claim_type.value,
            topic_category=candidate.topic_category,
            embedding=embedding,
            verdict=decision.verdict.value,
            evidence_completeness=decision.evidence_completeness,
            explanation=decision.explanation,
            missing_information=decision.missing_information,
            limitations=decision.limitations,
            suggested_correction=(
                decision.suggested_correction.model_dump()
                if decision.suggested_correction
                else None
            ),
            version=1,
            hit_count=1,
            verified_at=now,
            expires_at=now + timedelta(days=settings.CLAIM_MEMORY_TTL_DAYS),
        )
        for ev in evaluated_evidences:
            claim_rec.evidences.append(
                EvidenceRecord(
                    claim_version=1,
                    title=ev.title,
                    url=ev.url,
                    domain=ev.domain,
                    publisher=ev.publisher,
                    published_date=ev.published_date,
                    tier=ev.tier,
                    tier_label=ev.tier_label,
                    stance=ev.stance.value,
                    snippet=ev.snippet,
                    scores=ev.scores.model_dump(),
                    citation_validated=ev.citation_validated,
                    validation_note=ev.validation_note,
                )
            )
        db.add(claim_rec)
        try:
            await db.commit()
        except Exception:
            await db.rollback()

    result = ClaimVerificationResult(
        claim_id=candidate.claim_id,
        original_text=candidate.original_text,
        normalized_claim=candidate.normalized_claim,
        claim_type=candidate.claim_type,
        claim_type_label_vi=candidate.claim_type_label_vi,
        check_category=candidate.check_category,
        topic_category=candidate.topic_category,
        start_char=candidate.start_char,
        end_char=candidate.end_char,
        page_number=candidate.page_number,
        verdict=decision.verdict,
        verdict_label_vi=decision.verdict_label_vi,
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
        verified_at=now.isoformat(),
    )
    return result, used_live_search


async def run_verification_pipeline(
    db: AsyncSession,
    doc: IngestedDocument,
    use_claim_memory: bool = True,
    existing_job_id: Optional[str] = None,
    saved_file_path: Optional[str] = None,
) -> VerificationResponse:
    """
    Master 6-Layer TrueCheck AI Pipeline:
    Layer 1 (IngestedDocument) -> Layer 2 (Claim Extraction) ->
    Layer 3 (Claim Memory & Retrieval) -> Layer 4 (Citation Validation) ->
    Layer 5 (6-State Decision) -> Layer 6 (Explanation & Manipulation Signals).
    """
    started = time.perf_counter()
    now_iso = datetime.now(timezone.utc).isoformat()
    doc_id = existing_job_id or str(uuid.uuid4())

    # Short-TTL exact text cache in Redis for rapid repeated Extension highlights
    cache_key = None
    if doc.source_type == "TEXT" and use_claim_memory and len(doc.full_text) <= 1500:
        digest = hashlib.sha256(doc.full_text.encode("utf-8")).hexdigest()[:24]
        cache_key = f"truecheck:v1:text:{digest}"
        cached_payload = await cache_manager.get_json(cache_key)
        if cached_payload:
            return VerificationResponse.model_validate(cached_payload)

    # Layer 2 & Layer 6 Manipulation Scan in parallel
    candidates_task = asyncio.create_task(extract_claims(doc))
    manip_task = asyncio.create_task(analyze_manipulation_signals(doc.full_text))
    candidates, (manip_signals, manip_summary) = await asyncio.gather(candidates_task, manip_task)

    # Process claims sequentially or in bounded concurrency (protects DB session & API rate limits)
    claim_results: List[ClaimVerificationResult] = []
    any_live_search = False
    for cand in candidates:
        c_res, live_used = await _verify_single_claim(db, cand, use_claim_memory=use_claim_memory)
        claim_results.append(c_res)
        if live_used:
            any_live_search = True

    counts: Dict[str, int] = {v.value: 0 for v in VerdictEnum}
    for cr in claim_results:
        counts[cr.verdict.value] = counts.get(cr.verdict.value, 0) + 1

    if gemini_client.is_live and any_live_search:
        engine_mode = "LIVE_AI"
    elif gemini_client.is_live or any_live_search:
        engine_mode = "HYBRID"
    else:
        engine_mode = "DEMO_FALLBACK"

    elapsed_ms = int((time.perf_counter() - started) * 1000)

    response = VerificationResponse(
        request_id=str(uuid.uuid4()),
        document_id=doc_id,
        source_type=doc.source_type,
        source_title=doc.source_title,
        source_url=doc.source_url,
        full_text=doc.full_text,
        segments=doc.segments,
        claims=claim_results,
        manipulation_signals=manip_signals,
        manipulation_summary=manip_summary,
        privacy_scan=PrivacyScanInfo(
            has_pii=doc.security_scan.has_pii,
            pii_types=doc.security_scan.pii_types,
            privacy_notice=doc.security_scan.privacy_notice,
            prompt_injection_detected=doc.security_scan.prompt_injection_detected,
            injection_warnings=doc.security_scan.injection_warnings,
            ocr_required_pages=doc.ocr_required_pages,
        ),
        summary_counts=counts,
        engine_mode=engine_mode,
        processing_time_ms=elapsed_ms,
        verified_at=now_iso,
    )

    # Save or update DocumentJob for Report / Annotated PDF exporting
    now_dt = datetime.now(timezone.utc)
    retention_dt = now_dt + timedelta(hours=settings.DOCUMENT_RETENTION_HOURS)
    existing_job = await db.get(DocumentJob, doc_id)
    if existing_job:
        existing_job.status = "COMPLETED"
        existing_job.result_payload = response.model_dump()
        existing_job.completed_at = now_dt
        existing_job.expires_at = retention_dt
    else:
        db.add(
            DocumentJob(
                id=doc_id,
                status="COMPLETED",
                source_type=doc.source_type,
                filename=doc.source_title,
                file_path=saved_file_path,
                source_url=doc.source_url,
                result_payload=response.model_dump(),
                completed_at=now_dt,
                expires_at=retention_dt,
            )
        )
    try:
        await db.commit()
    except Exception:
        await db.rollback()

    if cache_key:
        await cache_manager.set_json(cache_key, response.model_dump(), ttl_seconds=900)

    return response

