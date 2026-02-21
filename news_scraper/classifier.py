"""
Keyword filtering and sector classification for Indonesian financial news.
"""
import re
from typing import Optional

# ---------------------------------------------------------------------------
# Keywords that trigger flagging (corporate action / equity events)
# ---------------------------------------------------------------------------
TRIGGER_KEYWORDS: list[str] = [
    # English / mixed usage
    "right issue",
    "rights issue",
    "buyback",
    "buy back",
    "divestasi",
    "divestiture",
    "divestment",
    # Indonesian corporate actions
    "akuisisi",
    "acquisition",
    "borong",          # bulk buying by insiders/institutions
    "lego",            # selling off stakes
    "suntik modal",    # capital injection
    "injeksi modal",   # capital injection (alt phrase)
    "rights offering",
    "penawaran umum terbatas",   # PUT = rights issue
    "saham baru",                # new shares
    "emisi saham",               # share issuance
    "private placement",
    "PMTHMETD",                  # Penambahan Modal Tanpa HMETD (non-rights placement)
    "PMHMETD",                   # Penambahan Modal dengan HMETD (rights issue)
    "merger",
    "take over",
    "takeover",
    "go private",
    "MBO",                       # Management buyout
    "delisting",
    "tender offer",
    "konsolidasi saham",         # share consolidation
    "stock split",
    "pemecahan saham",
]

# Compiled patterns for fast matching
_PATTERNS = [re.compile(rf"\b{re.escape(kw)}\b", re.IGNORECASE) for kw in TRIGGER_KEYWORDS]


def find_keywords(text: str) -> list[str]:
    """Return list of matched trigger keywords found in text."""
    found = []
    combined = text.lower()
    for kw, pat in zip(TRIGGER_KEYWORDS, _PATTERNS):
        if pat.search(combined):
            found.append(kw)
    return found


# ---------------------------------------------------------------------------
# Sector classification
# ---------------------------------------------------------------------------
# Map of sector label -> keywords to look for in title/summary
SECTOR_KEYWORDS: dict[str, list[str]] = {
    "Perbankan": [
        "bank", "bri", "bca", "bni", "mandiri", "btpn", "cimb niaga",
        "bank central", "bank rakyat", "bank negara", "bank mandiri",
        "kredit", "tabungan", "deposito", "npl", "net interest",
    ],
    "Asuransi & Keuangan": [
        "asuransi", "insurance", "multifinance", "pembiayaan", "leasing",
        "oto multiartha", "adira", "finansial", "fintech", "modal ventura",
    ],
    "Pertambangan": [
        "tambang", "mining", "batubara", "coal", "nikel", "nickel",
        "tembaga", "copper", "timah", "tin", "emas", "gold", "mineral",
        "bumi resources", "bukit asam", "adaro", "vale indonesia",
        "antam", "merdeka copper", "harum energy",
    ],
    "Energi & Migas": [
        "minyak", "oil", "gas", "pertamina", "lng", "lpg", "pgas",
        "energi", "geothermal", "panas bumi", "medco", "elnusa",
        "radiant utama", "benakat", "petroleum",
    ],
    "Properti & Real Estate": [
        "properti", "property", "real estate", "apartemen", "ruko",
        "perumahan", "kawasan industri", "summarecon", "ciputra",
        "pakuwon", "lippo", "bsd", "sinarmas land", "modernland",
        "agung podomoro", "alam sutera",
    ],
    "Infrastruktur": [
        "infrastruktur", "infrastructure", "jalan tol", "tol", "pelabuhan",
        "port", "bandara", "airport", "kereta", "rail", "listrik",
        "pln", "adhi karya", "wika", "wskt", "waskita", "jasa marga",
        "hutama karya", "pp properti",
    ],
    "Teknologi & Telekomunikasi": [
        "teknologi", "technology", "telekomunikasi", "telecom",
        "telkom", "indosat", "xl axiata", "smartfren", "tower bersama",
        "mitratel", "digital", "internet", "data center", "cloud",
        "software", "e-commerce", "startup", "gojek", "tokopedia",
        "bukalapak", "traveloka",
    ],
    "Konsumer & Ritel": [
        "konsumer", "consumer", "ritel", "retail", "supermarket",
        "hypermarket", "indomaret", "alfamart", "transmart",
        "indofood", "unilever", "mayora", "wings", "sido muncul",
        "kalbe farma", "matahari", "map aktif", "mitra adiperkasa",
    ],
    "Farmasi & Kesehatan": [
        "farmasi", "pharmaceutical", "kesehatan", "health", "rumah sakit",
        "hospital", "klinik", "clinic", "obat", "medicine",
        "kalbe", "kimia farma", "phapros", "mitra keluarga",
        "siloam", "eka hospital", "omni", "biofarma",
    ],
    "Agrikultur & Perkebunan": [
        "sawit", "palm oil", "cpo", "perkebunan", "plantation",
        "karet", "rubber", "kakao", "cocoa", "kopi", "coffee",
        "astra agro", "sampoerna agro", "pp london sumatra",
        "salim ivomas", "smart", "simp",
    ],
    "Manufaktur & Industri": [
        "manufaktur", "manufacturing", "pabrik", "factory",
        "semen", "cement", "baja", "steel", "kimia", "chemical",
        "semen indonesia", "indocement", "holcim", "krakatau steel",
        "astra international", "indomobil", "tunas ridean",
        "chandra asri", "lotte chemical",
    ],
    "Transportasi & Logistik": [
        "transportasi", "transport", "logistik", "logistics",
        "pelayaran", "shipping", "penerbangan", "airline",
        "garuda", "lion air", "citilink", "samudera indonesia",
        "berlian laju tanker", "caraka tirta perkasa",
    ],
    "Media & Hiburan": [
        "media", "hiburan", "entertainment", "televisi", "television",
        "surya citra", "sctv", "mnc", "trans media", "kompas",
        "detik", "kumparan", "sinema",
    ],
}

# Build reverse lookup: keyword -> sector
_KW_TO_SECTOR: dict[str, str] = {}
for _sector, _kws in SECTOR_KEYWORDS.items():
    for _kw in _kws:
        _KW_TO_SECTOR[_kw.lower()] = _sector


def classify_sector(title: str, summary: str = "") -> Optional[str]:
    """
    Return the most likely sector for an article based on keyword matching.
    Checks title first (higher weight), then summary.
    Returns None if no sector detected.
    """
    text = f"{title} {summary}".lower()
    scores: dict[str, int] = {}

    for kw, sector in _KW_TO_SECTOR.items():
        if kw in text:
            # Title match = 2 points, summary match = 1 point
            title_hits = title.lower().count(kw)
            summary_hits = summary.lower().count(kw) if summary else 0
            scores[sector] = scores.get(sector, 0) + title_hits * 2 + summary_hits

    if not scores:
        return None
    return max(scores, key=lambda s: scores[s])


def extract_ticker(title: str, summary: str = "") -> Optional[str]:
    """
    Attempt to extract an IDX ticker from text.
    IDX tickers are 4-letter uppercase codes, often wrapped in parentheses
    or prefixed with 'IHSG', 'IDX:' etc.
    """
    text = f"{title} {summary}"
    # Match patterns like (BBCA), (TLKM), IDX:BBRI, saham TLKM, etc.
    patterns = [
        r"\(([A-Z]{4})\)",           # (BBCA)
        r"\bIDX:([A-Z]{4})\b",       # IDX:BBCA
        r"\bsaham\s+([A-Z]{4})\b",   # saham BBCA
        r"\bemiten\s+([A-Z]{4})\b",  # emiten BBCA
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(1)
    return None
