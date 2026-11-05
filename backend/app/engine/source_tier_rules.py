from typing import Tuple
from urllib.parse import urlparse


TIER_LABELS: dict[int, str] = {
    1: "Cấp 1 – Cơ quan Nhà nước (Bộ Công an, TinGiả.gov.vn, Chính phủ) & Nghiên cứu gốc (Peer-Reviewed)",
    2: "Cấp 2 – Tổ chức Kiểm chứng Quốc tế (PolitiFact, IFCN, AFP) & Cơ quan Học thuật / Quốc tế (WHO, IEEE)",
    3: "Cấp 3 – Cơ quan báo chí chính thống có quy trình biên tập minh bạch",
    4: "Cấp 4 – Chuyên trang đối chiếu dữ liệu & Cổng tri thức mở",
    5: "Cấp 5 – Website chung / Mạng xã hội (Đối chiếu ngữ cảnh)",
}

TIER_BASE_CREDIBILITY: dict[int, float] = {
    1: 0.97,
    2: 0.92,
    3: 0.82,
    4: 0.86,
    5: 0.35,
}

TIER_1_DOMAINS = {
    "tingia.gov.vn",
    "bocongan.gov.vn",
    "mps.gov.vn",
    "chinhphu.vn",
    "baochinhphu.vn",
    "vanban.chinhphu.vn",
    "thuvienphapluat.vn",
    "vbpl.vn",
    "quochoi.vn",
    "gso.gov.vn",
    "nso.gov.vn",
    "sbv.gov.vn",
    "mof.gov.vn",
    "moit.gov.vn",
    "moet.gov.vn",
    "moh.gov.vn",
    "most.gov.vn",
    "mic.gov.vn",
    "evn.com.vn",
    "doi.org",
    "arxiv.org",
    "pubmed.ncbi.nlm.nih.gov",
    "ncbi.nlm.nih.gov",
    "nih.gov",
    "cdc.gov",
    "nature.com",
    "science.org",
    "sciencedirect.com",
    "thelancet.com",
    "ieee.org",
    "ieeexplore.ieee.org",
    "dl.acm.org",
    "springer.com",
    "link.springer.com",
    "onlinelibrary.wiley.com",
    "cell.com",
    "nejm.org",
    "bmj.com",
    "jamanetwork.com",
}

TIER_2_DOMAINS = {
    "politifact.com",
    "factcheck.org",
    "snopes.com",
    "fullfact.org",
    "factcheck.afp.com",
    "checkyourfact.com",
    "leadstories.com",
    "poynter.org",
    "deepai.org",
    "contentauthenticity.org",
    "c2pa.org",
    "who.int",
    "worldbank.org",
    "data.worldbank.org",
    "imf.org",
    "un.org",
    "unesco.org",
    "unicef.org",
    "oecd.org",
    "ilo.org",
    "wto.org",
    "adb.org",
    "vass.gov.vn",
    "vast.vn",
    "ourworldindata.org",
    "openalex.org",
    "semanticscholar.org",
    "scholar.google.com",
    "crossref.org",
}

TIER_3_DOMAINS = {
    "baochinhphu.vn",
    "nhandan.vn",
    "vietnamplus.vn",
    "vnexpress.net",
    "tuoitre.vn",
    "thanhnien.vn",
    "vtv.vn",
    "vov.vn",
    "laodong.vn",
    "vietnamnet.vn",
    "dantri.com.vn",
    "sggp.org.vn",
    "tienphong.vn",
    "vneconomy.vn",
    "thesaigontimes.vn",
    "reuters.com",
    "apnews.com",
    "bbc.com",
    "bbc.co.uk",
    "bloomberg.com",
    "ft.com",
}

TIER_4_DOMAINS = {
    "tingia.gov.vn",
    "factcheck.org",
    "politifact.com",
    "snopes.com",
    "fullfact.org",
    "factcheck.afp.com",
    "checkyourfact.com",
    "leadstories.com",
}


def extract_clean_domain(url: str) -> str:
    try:
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def classify_source_tier(url: str, from_factcheck_api: bool = False) -> Tuple[int, str, float, str]:
    """
    Returns (tier, tier_label, base_credibility, domain).
    Implements Principle IV.4: prioritizes primary/official data and transparent editorial standards.
    """
    domain = extract_clean_domain(url)

    for d1 in TIER_1_DOMAINS:
        if domain == d1 or domain.endswith("." + d1):
            return 1, TIER_LABELS[1], TIER_BASE_CREDIBILITY[1], domain

    if (
        domain.endswith(".gov.vn")
        or domain.endswith(".gov")
        or domain.endswith(".chinhphu.vn")
    ):
        return 1, TIER_LABELS[1], TIER_BASE_CREDIBILITY[1], domain

    for d2 in TIER_2_DOMAINS:
        if domain == d2 or domain.endswith("." + d2):
            return 2, TIER_LABELS[2], TIER_BASE_CREDIBILITY[2], domain

    if (
        from_factcheck_api
        or domain.endswith(".edu.vn")
        or domain.endswith(".edu")
        or domain.endswith(".ac.uk")
        or domain.endswith(".ac.jp")
    ):
        return 2, TIER_LABELS[2], TIER_BASE_CREDIBILITY[2], domain

    if domain in TIER_4_DOMAINS:
        return 4, TIER_LABELS[4], TIER_BASE_CREDIBILITY[4], domain

    for d3 in TIER_3_DOMAINS:
        if domain == d3 or domain.endswith("." + d3):
            return 3, TIER_LABELS[3], TIER_BASE_CREDIBILITY[3], domain

    return 5, TIER_LABELS[5], TIER_BASE_CREDIBILITY[5], domain

