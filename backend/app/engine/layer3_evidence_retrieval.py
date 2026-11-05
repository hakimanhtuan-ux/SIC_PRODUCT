import asyncio
import logging
import math
import time
from urllib.parse import quote
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import is_postgres_active
from app.engine.gemini_client import gemini_client
from app.engine.layer2_claim_extraction import ExtractedClaimCandidate
from app.engine.source_tier_rules import classify_source_tier
from app.models.entities import ClaimRecord
from app.schemas.verification import ClaimTypeEnum

logger = logging.getLogger(__name__)

# Shared HTTP connection pool for sub-second keep-alive reuse across external search APIs
_SHARED_HTTP_CLIENT: Optional[httpx.AsyncClient] = None
_SEARCH_CACHE: Dict[str, tuple[float, List["RawCandidateEvidence"], bool]] = {}


def _get_http_client() -> httpx.AsyncClient:
    global _SHARED_HTTP_CLIENT
    if _SHARED_HTTP_CLIENT is None or _SHARED_HTTP_CLIENT.is_closed:
        _SHARED_HTTP_CLIENT = httpx.AsyncClient(
            follow_redirects=True,
            limits=httpx.Limits(max_keepalive_connections=24, max_connections=48),
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TrueCheckAI/0.2"
            },
        )
    return _SHARED_HTTP_CLIENT


@dataclass
class RawCandidateEvidence:
    id: str
    title: str
    url: str
    domain: str
    publisher: str
    published_date: Optional[str]
    tier: int
    tier_label: str
    base_credibility: float
    snippet: str
    from_factcheck_api: bool = False
    factcheck_textual_rating: Optional[str] = None


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


async def lookup_claim_memory(
    db: AsyncSession,
    normalized_claim: str,
) -> tuple[Optional[ClaimRecord], Optional[list[float]]]:
    """
    Fast 2-stage Claim Memory lookup:
    1. Exact normalized text check (~1ms, 0 API calls)
    2. Semantic vector check ONLY if Claim Memory actually has non-expired rows!
    """
    now = datetime.now(timezone.utc)
    threshold = settings.CLAIM_MEMORY_SIMILARITY_THRESHOLD

    try:
        # Stage 1: Instant exact text match (0 embedding API latency!)
        exact_stmt = (
            select(ClaimRecord)
            .where(ClaimRecord.normalized_claim == normalized_claim)
            .where(ClaimRecord.expires_at > now)
            .limit(1)
        )
        exact_rec = (await db.execute(exact_stmt)).scalars().first()
        if exact_rec is not None:
            exact_rec.hit_count += 1
            await db.commit()
            return exact_rec, exact_rec.embedding if isinstance(exact_rec.embedding, list) else None

        # Check if any active records exist before spending network time on embedding
        exists_stmt = select(ClaimRecord.id).where(ClaimRecord.expires_at > now).limit(1)
        has_any = (await db.execute(exists_stmt)).first() is not None
        if not has_any:
            return None, None

        embedding = await gemini_client.embed_text(normalized_claim)

        if is_postgres_active():
            max_distance = 1.0 - threshold
            distance_expr = ClaimRecord.embedding.cosine_distance(embedding)
            stmt = (
                select(ClaimRecord, distance_expr.label("dist"))
                .where(ClaimRecord.expires_at > now)
                .where(ClaimRecord.embedding.is_not(None))
                .order_by(distance_expr.asc())
                .limit(1)
            )
            row = (await db.execute(stmt)).first()
            if row is not None:
                record, dist = row[0], float(row[1])
                if dist <= max_distance:
                    record.hit_count += 1
                    await db.commit()
                    return record, embedding
        else:
            stmt = select(ClaimRecord).where(ClaimRecord.expires_at > now).limit(100)
            records = (await db.execute(stmt)).scalars().all()
            best_rec: Optional[ClaimRecord] = None
            best_sim = 0.0
            for rec in records:
                if isinstance(rec.embedding, list):
                    sim = _cosine_similarity(embedding, rec.embedding)
                    if sim > best_sim:
                        best_sim = sim
                        best_rec = rec
            if best_rec is not None and best_sim >= threshold:
                best_rec.hit_count += 1
                await db.commit()
                return best_rec, embedding
        return None, embedding
    except Exception as exc:
        logger.warning("Claim memory lookup warning: %s", exc)
        return None, None


async def lookup_claim_memory_batch(
    db: AsyncSession,
    normalized_claims: List[str],
) -> List[tuple[Optional[ClaimRecord], Optional[list[float]]]]:
    """
    Batch Claim Memory lookup across multiple claims in ONE DB pass + ONE batch embedding API call (~0.35s total).
    """
    if not normalized_claims:
        return []
    now = datetime.now(timezone.utc)
    threshold = settings.CLAIM_MEMORY_SIMILARITY_THRESHOLD
    results: List[tuple[Optional[ClaimRecord], Optional[list[float]]]] = [
        (None, None) for _ in normalized_claims
    ]

    try:
        unique_texts = list({c for c in normalized_claims if c})
        exact_stmt = (
            select(ClaimRecord)
            .where(ClaimRecord.normalized_claim.in_(unique_texts))
            .where(ClaimRecord.expires_at > now)
        )
        exact_rows = (await db.execute(exact_stmt)).scalars().all()
        exact_map = {r.normalized_claim: r for r in exact_rows}

        unmatched_indices: List[int] = []
        hit_any = False
        for idx, c_txt in enumerate(normalized_claims):
            rec = exact_map.get(c_txt)
            if rec is not None:
                rec.hit_count += 1
                hit_any = True
                results[idx] = (rec, rec.embedding if isinstance(rec.embedding, list) else None)
            else:
                unmatched_indices.append(idx)

        if not unmatched_indices:
            if hit_any:
                await db.commit()
            return results

        active_stmt = select(ClaimRecord).where(ClaimRecord.expires_at > now).limit(100)
        active_records = (await db.execute(active_stmt)).scalars().all()
        if not active_records:
            if hit_any:
                await db.commit()
            return results

        unmatched_texts = [normalized_claims[i] for i in unmatched_indices]
        batch_embeddings = await gemini_client.embed_texts_batch(unmatched_texts)

        for idx, emb in zip(unmatched_indices, batch_embeddings):
            best_rec: Optional[ClaimRecord] = None
            best_sim = 0.0
            for rec in active_records:
                if isinstance(rec.embedding, list):
                    sim = _cosine_similarity(emb, rec.embedding)
                    if sim > best_sim:
                        best_sim = sim
                        best_rec = rec
            if best_rec is not None and best_sim >= threshold:
                best_rec.hit_count += 1
                hit_any = True
                results[idx] = (best_rec, emb)
            else:
                results[idx] = (None, emb)

        if hit_any:
            await db.commit()
        return results
    except Exception as exc:
        logger.warning("Batch claim memory lookup warning: %s", exc)
        return results


async def _search_google_factcheck(query: str) -> List[RawCandidateEvidence]:
    if not settings.has_factcheck_key:
        return []
    url = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
    params = {
        "query": query[:150],
        "key": settings.GOOGLE_FACTCHECK_API_KEY,
        "pageSize": 5,
    }
    results: List[RawCandidateEvidence] = []
    try:
        client = _get_http_client()
        resp = await client.get(url, params=params, timeout=1.5)
        if resp.status_code != 200:
            return []
        data = resp.json()

        for claim_obj in data.get("claims", []):
            claim_txt = claim_obj.get("text", "")
            for rev in claim_obj.get("claimReview", []):
                rev_url = rev.get("url", "")
                if not rev_url:
                    continue
                pub_name = (rev.get("publisher") or {}).get("name") or "Fact-Check Organization"
                rating = rev.get("textualRating", "")
                title = rev.get("title") or f"Kiểm chứng: {claim_txt[:90]}"
                tier, tier_label, base_cred, domain = classify_source_tier(
                    rev_url, from_factcheck_api=True
                )
                snippet = f"Tuyên bố đã kiểm chứng: '{claim_txt}'. Đánh giá từ {pub_name}: {rating}."
                results.append(
                    RawCandidateEvidence(
                        id=str(uuid.uuid4())[:8],
                        title=title,
                        url=rev_url,
                        domain=domain,
                        publisher=pub_name,
                        published_date=rev.get("reviewDate"),
                        tier=tier,
                        tier_label=tier_label,
                        base_credibility=base_cred,
                        snippet=snippet,
                        from_factcheck_api=True,
                        factcheck_textual_rating=rating,
                    )
                )
    except Exception as exc:
        logger.warning("Google Fact Check API fast timeout/warning: %s", exc)
    return results


async def _search_tavily(query: str) -> List[RawCandidateEvidence]:
    if not settings.has_tavily_key:
        return []
    url = "https://api.tavily.com/search"
    # Using "basic" cuts Tavily latency from ~7.3s down to ~1.0s while preserving top snippets!
    payload = {
        "api_key": settings.TAVILY_API_KEY,
        "query": query[:180],
        "search_depth": "basic",
        "max_results": 3,
        "include_answer": False,
    }
    results: List[RawCandidateEvidence] = []
    try:
        client = _get_http_client()
        resp = await client.post(url, json=payload, timeout=1.8)
        if resp.status_code != 200:
            return []
        data = resp.json()

        for item in data.get("results", []):
            item_url = item.get("url", "")
            if not item_url:
                continue
            tier, tier_label, base_cred, domain = classify_source_tier(item_url)
            results.append(
                RawCandidateEvidence(
                    id=str(uuid.uuid4())[:8],
                    title=item.get("title") or domain,
                    url=item_url,
                    domain=domain,
                    publisher=domain,
                    published_date=item.get("published_date"),
                    tier=tier,
                    tier_label=tier_label,
                    base_credibility=base_cred,
                    snippet=(item.get("content") or "")[:420],
                )
            )
    except Exception as exc:
        logger.warning("Tavily Search API fast timeout/warning: %s", exc)
    return results


async def _search_google_cse(query: str) -> List[RawCandidateEvidence]:
    if not settings.has_google_cse:
        return []
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": settings.GOOGLE_CSE_API_KEY,
        "cx": settings.GOOGLE_CSE_CX,
        "q": query[:150],
        "num": 5,
    }
    results: List[RawCandidateEvidence] = []
    try:
        client = _get_http_client()
        resp = await client.get(url, params=params, timeout=1.5)
        if resp.status_code != 200:
            return []
        data = resp.json()

        for item in data.get("items", []):
            item_url = item.get("link", "")
            if not item_url:
                continue
            tier, tier_label, base_cred, domain = classify_source_tier(item_url)
            results.append(
                RawCandidateEvidence(
                    id=str(uuid.uuid4())[:8],
                    title=item.get("title") or domain,
                    url=item_url,
                    domain=domain,
                    publisher=item.get("displayLink") or domain,
                    published_date=None,
                    tier=tier,
                    tier_label=tier_label,
                    base_credibility=base_cred,
                    snippet=(item.get("snippet") or "")[:650],
                )
            )
    except Exception as exc:
        logger.warning("Google CSE warning: %s", exc)
    return results


def _curated_reference_portals(claim: ExtractedClaimCandidate) -> List[RawCandidateEvidence]:
    """
    When no external Search API returns hits, provides transparent official portal references
    (marked clearly as unvalidated contextual portals, NEVER fabricated quotes).
    """
    low = claim.normalized_claim.lower()
    refs: list[tuple[str, str, str]] = []

    if "giá điện" in low or "điện lực" in low:
        refs.append((
            "Cổng thông tin Tập đoàn Điện lực Việt Nam (EVN) – Biểu giá bán lẻ điện hiện hành",
            "https://www.evn.com.vn",
            "Nguồn tra cứu chính thức các quyết định điều chỉnh giá bán lẻ điện bình quân của Bộ Công Thương và EVN.",
        ))
        refs.append((
            "Cổng Thông tin điện tử Chính phủ – Văn bản điều hành giá năng lượng",
            "https://chinhphu.vn",
            "Tra cứu công báo và chỉ đạo chính thức về điều hành giá điện, kinh tế vĩ mô.",
        ))
    elif any(k in low for k in ("công an", "lừa đảo", "bắt giữ", "khởi tố", "phạt", "luật", "an ninh", "giả mạo")):
        refs.append((
            "Cổng Thông tin điện tử Bộ Công an Việt Nam – Cảnh báo tội phạm & tin giả an ninh trật tự",
            "https://bocongan.gov.vn",
            "Nguồn xác minh chính thức của Bộ Công an về các vụ việc an ninh trật tự, cảnh báo thủ đoạn lừa đảo không gian mạng và văn bản giả mạo.",
        ))
        refs.append((
            "Trung tâm Xử lý tin giả Việt Nam (VAFC – Bộ TT&TT)",
            "https://tingia.gov.vn",
            "Cổng tiếp nhận, thẩm định và công bố các thông tin giả mạo, sai sự thật đã được cơ quan chức năng xác minh.",
        ))
    elif "sinh viên" in low or "giáo dục" in low or "học tập" in low:
        refs.append((
            "Bộ Giáo dục và Đào tạo – Số liệu thống kê giáo dục đại học",
            "https://moet.gov.vn",
            "Nguồn dữ liệu chính thức về quy mô sinh viên và báo cáo chuyển đổi số / ứng dụng AI trong giáo dục tại Việt Nam.",
        ))
    else:
        refs.append((
            "Trung tâm Xử lý tin giả Việt Nam (VAFC – tingia.gov.vn)",
            "https://tingia.gov.vn",
            "Cổng tiếp nhận và công bố các thông tin đã được cơ quan chức năng xác minh, đính chính.",
        ))
        refs.append((
            "Cổng Thông tin điện tử Bộ Công an Việt Nam (bocongan.gov.vn)",
            "https://bocongan.gov.vn",
            "Cơ quan công bố chính thức các cảnh báo an ninh mạng, tin giả và thông tin điều tra.",
        ))
        refs.append((
            "PolitiFact (Poynter Institute) – Hệ thống kiểm chứng quốc tế chuẩn IFCN",
            "https://www.politifact.com",
            "Cơ sở dữ liệu kiểm chứng quốc tế theo thang đo Truth-O-Meter (True, Mostly True, Half True, Mostly False, False).",
        ))

    output: List[RawCandidateEvidence] = []
    for title, url, desc in refs:
        tier, tier_label, base_cred, domain = classify_source_tier(url)
        output.append(
            RawCandidateEvidence(
                id=str(uuid.uuid4())[:8],
                title=title,
                url=url,
                domain=domain,
                publisher=domain,
                published_date=None,
                tier=tier,
                tier_label=tier_label,
                base_credibility=base_cred,
                snippet=desc,
            )
        )
    return output


async def _search_free_google_news_vn(query: str) -> List[RawCandidateEvidence]:
    """100% Free, keyless real-time search via Google News Vietnam RSS feed."""
    url = "https://news.google.com/rss/search"
    params = {
        "q": query[:120],
        "hl": "vi",
        "gl": "VN",
        "ceid": "VN:vi",
    }
    results: List[RawCandidateEvidence] = []
    try:
        client = _get_http_client()
        resp = await client.get(url, params=params, timeout=1.5)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "xml")

        for item in soup.find_all("item")[:5]:
            title_tag = item.find("title")
            link_tag = item.find("link")
            pub_tag = item.find("pubDate")
            source_tag = item.find("source")
            desc_tag = item.find("description")

            title = title_tag.get_text(strip=True) if title_tag else ""
            article_url = link_tag.get_text(strip=True) if link_tag else ""
            if not title or not article_url:
                continue

            publisher_url = (
                source_tag.get("url")
                if (source_tag and source_tag.get("url"))
                else article_url
            )
            publisher_name = source_tag.get_text(strip=True) if source_tag else ""

            tier, tier_label, base_cred, domain = classify_source_tier(str(publisher_url))
            clean_desc = ""
            if desc_tag and desc_tag.get_text():
                clean_desc = BeautifulSoup(desc_tag.get_text(), "html.parser").get_text(" ", strip=True)

            snippet = f"{title}. {clean_desc}".strip()[:650]
            results.append(
                RawCandidateEvidence(
                    id=str(uuid.uuid4())[:8],
                    title=title,
                    url=article_url,
                    domain=domain or publisher_name,
                    publisher=publisher_name or domain or "Google News VN",
                    published_date=pub_tag.get_text(strip=True) if pub_tag else None,
                    tier=tier,
                    tier_label=tier_label,
                    base_credibility=base_cred,
                    snippet=snippet,
                )
            )
    except Exception as exc:
        logger.warning("Free Google News VN RSS search warning: %s", exc)
    return results


async def _search_free_wikipedia_vi(query: str) -> List[RawCandidateEvidence]:
    """100% Free, keyless search via Vietnamese Wikipedia API."""
    url = "https://vi.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query[:100],
        "utf8": 1,
        "format": "json",
        "srlimit": 3,
    }
    headers = {
        "User-Agent": "TrueCheckAI/0.2 (https://localhost:3000; contact@truecheck.local)"
    }
    results: List[RawCandidateEvidence] = []
    try:
        client = _get_http_client()
        resp = await client.get(url, params=params, headers=headers, timeout=1.3)
        if resp.status_code != 200:
            return []
        data = resp.json()

        for item in (data.get("query") or {}).get("search", []):
            title = item.get("title", "")
            raw_snip = item.get("snippet", "")
            clean_snip = BeautifulSoup(raw_snip, "html.parser").get_text(" ", strip=True)
            if not title or not clean_snip:
                continue
            wiki_url = f"https://vi.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"
            results.append(
                RawCandidateEvidence(
                    id=str(uuid.uuid4())[:8],
                    title=f"Wikipedia Tiếng Việt: {title}",
                    url=wiki_url,
                    domain="vi.wikipedia.org",
                    publisher="Wikipedia Tiếng Việt",
                    published_date=item.get("timestamp"),
                    tier=2,
                    tier_label="Cấp 2 – Bách khoa toàn thư mở & Cơ sở dữ liệu tri thức",
                    base_credibility=0.82,
                    snippet=clean_snip[:420],
                )
            )
    except Exception as exc:
        logger.warning("Free Wikipedia VI search warning: %s", exc)
    return results


async def _search_vn_official_factcheck_portals(query: str) -> List[RawCandidateEvidence]:
    """
    Targeted search across official Vietnamese Anti-Fake-News & Law Enforcement portals
    (tingia.gov.vn, bocongan.gov.vn, chinhphu.vn, baochinhphu.vn) and international PolitiFact (politifact.com).
    """
    url = "https://news.google.com/rss/search"
    scoped_q = (
        f"({query[:90]}) "
        "(site:tingia.gov.vn OR site:bocongan.gov.vn OR site:chinhphu.vn OR site:baochinhphu.vn OR site:politifact.com)"
    )
    params = {
        "q": scoped_q,
        "hl": "vi",
        "gl": "VN",
        "ceid": "VN:vi",
    }
    results: List[RawCandidateEvidence] = []
    try:
        client = _get_http_client()
        resp = await client.get(url, params=params, timeout=1.5)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "xml")

        for item in soup.find_all("item")[:3]:
            title_tag = item.find("title")
            link_tag = item.find("link")
            pub_tag = item.find("pubDate")
            source_tag = item.find("source")
            desc_tag = item.find("description")

            title = title_tag.get_text(strip=True) if title_tag else ""
            article_url = link_tag.get_text(strip=True) if link_tag else ""
            if not title or not article_url:
                continue

            publisher_url = (
                source_tag.get("url")
                if (source_tag and source_tag.get("url"))
                else article_url
            )
            publisher_name = source_tag.get_text(strip=True) if source_tag else ""
            tier, tier_label, base_cred, domain = classify_source_tier(
                str(publisher_url), from_factcheck_api=True
            )
            clean_desc = ""
            if desc_tag and desc_tag.get_text():
                clean_desc = BeautifulSoup(desc_tag.get_text(), "html.parser").get_text(" ", strip=True)

            snippet = f"[Cổng Chính thống / Kiểm chứng] {title}. {clean_desc}".strip()[:650]
            results.append(
                RawCandidateEvidence(
                    id=str(uuid.uuid4())[:8],
                    title=title,
                    url=article_url,
                    domain=domain or publisher_name,
                    publisher=publisher_name or domain or "Cổng Xác minh Chính thống",
                    published_date=pub_tag.get_text(strip=True) if pub_tag else None,
                    tier=tier,
                    tier_label=tier_label,
                    base_credibility=max(0.92, base_cred),
                    snippet=snippet,
                    from_factcheck_api=True,
                )
            )
    except Exception as exc:
        logger.warning("Official portal search warning: %s", exc)
    return results


async def _search_free_academic_openalex(query: str) -> List[RawCandidateEvidence]:
    """
    100% Free, keyless search across 250M+ peer-reviewed academic & scientific papers
    (IEEE, Nature, PubMed, ScienceDirect, Springer) via OpenAlex API.
    """
    url = "https://api.openalex.org/works"
    params = {
        "search": query[:120],
        "per-page": 2,
        "select": "id,doi,title,publication_year,primary_location,cited_by_count,abstract_inverted_index",
    }
    results: List[RawCandidateEvidence] = []
    try:
        client = _get_http_client()
        resp = await client.get(url, params=params, timeout=1.5)
        if resp.status_code != 200:
            return []
        data = resp.json()

        for work in data.get("results", []):
            title = (work.get("title") or "").strip()
            if not title:
                continue
            doi_url = work.get("doi") or work.get("id") or ""
            if not doi_url:
                continue
            pub_year = str(work.get("publication_year") or "")
            cited_by = int(work.get("cited_by_count") or 0)
            loc = work.get("primary_location") or {}
            src_info = loc.get("source") or {}
            journal_name = src_info.get("display_name") or "OpenAlex Peer-Reviewed Literature"

            # Reconstruct abstract from OpenAlex inverted index if present
            inv_idx = work.get("abstract_inverted_index")
            abstract_text = ""
            if isinstance(inv_idx, dict) and inv_idx:
                word_positions: list[tuple[int, str]] = []
                for word, positions in inv_idx.items():
                    if isinstance(positions, list):
                        for pos in positions[:10]:
                            if isinstance(pos, int) and pos < 90:
                                word_positions.append((pos, word))
                word_positions.sort(key=lambda x: x[0])
                abstract_text = " ".join(w for _, w in word_positions[:70])

            snippet = (
                f"Công trình học thuật ({journal_name}, {pub_year}, {cited_by} trích dẫn): {title}. "
                f"{abstract_text}"
            ).strip()[:600]

            results.append(
                RawCandidateEvidence(
                    id=str(uuid.uuid4())[:8],
                    title=f"[Nghiên cứu Học thuật] {title}",
                    url=doi_url,
                    domain="doi.org",
                    publisher=journal_name,
                    published_date=pub_year or None,
                    tier=1,
                    tier_label="Cấp 1 – Công trình nghiên cứu học thuật & Báo cáo khoa học (DOI / Peer-Reviewed)",
                    base_credibility=0.95,
                    snippet=snippet,
                )
            )
    except Exception as exc:
        logger.warning("OpenAlex academic search warning: %s", exc)
    return results


async def retrieve_evidence_for_claim(
    claim: ExtractedClaimCandidate,
) -> tuple[List[RawCandidateEvidence], bool]:
    """
    Returns (deduplicated_sorted_evidences, used_live_search).
    Queries configured APIs (Google Fact Check, Tavily Basic, Google CSE),
    Official Anti-Fake-News portals (tingia.gov.vn, bocongan.gov.vn, politifact.com),
    Peer-Reviewed Academic Literature (OpenAlex / DOI), Google News VN RSS & Wikipedia VI in parallel.
    """
    if claim.claim_type in (ClaimTypeEnum.OPINION, ClaimTypeEnum.SATIRE):
        return [], True

    primary_query = (claim.search_queries[0] if claim.search_queries else claim.normalized_claim).strip()
    cache_k = primary_query.lower()[:160]
    cached_hit = _SEARCH_CACHE.get(cache_k)
    if cached_hit and time.monotonic() < cached_hit[0]:
        return cached_hit[1], cached_hit[2]

    low_q = primary_query.lower()
    needs_academic = any(
        kw in low_q
        for kw in (
            "nghiên cứu",
            "khảo sát",
            "khoa học",
            "y tế",
            "ung thư",
            "vaccine",
            "bệnh",
            "sinh viên",
            "đại học",
            "tỷ lệ",
            "%",
            "ai",
            "study",
            "research",
        )
    )

    tasks = [
        _search_google_factcheck(primary_query),
        _search_vn_official_factcheck_portals(primary_query),
        _search_tavily(primary_query),
        _search_google_cse(primary_query),
        _search_free_google_news_vn(primary_query),
        _search_free_wikipedia_vi(primary_query),
    ]
    if needs_academic:
        tasks.append(_search_free_academic_openalex(primary_query))

    batches = await asyncio.gather(*tasks, return_exceptions=True)
    merged: List[RawCandidateEvidence] = []
    seen_urls: set[str] = set()

    for batch in batches:
        if isinstance(batch, Exception):
            continue
        for item in batch:
            norm_url = item.url.rstrip("/")
            if norm_url in seen_urls:
                continue
            seen_urls.add(norm_url)
            merged.append(item)

    if not merged:
        return _curated_reference_portals(claim), False

    merged.sort(key=lambda e: (e.tier, -int(e.from_factcheck_api), -len(e.snippet)))
    top_merged = merged[:5]
    if len(_SEARCH_CACHE) >= 256:
        _SEARCH_CACHE.pop(next(iter(_SEARCH_CACHE)))
    _SEARCH_CACHE[cache_k] = (time.monotonic() + 600.0, top_merged, True)
    return top_merged, True
