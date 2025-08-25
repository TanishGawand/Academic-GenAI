import json
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple

from rapidfuzz import fuzz
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DB_JSON = "research.json"

# ----------------------
# Load papers + build index
# ----------------------
_PAPERS: List[Dict[str, Any]] = []
_VECTORIZER: TfidfVectorizer = None
_DOC_MATRIX = None

_STOPWORDS = set("""
a an and are as at be by for from has have in is it its of on or that the this to was were will with into within
since after before between over under than then about into not no yes do does did done their there here those these
""".split())

def load_papers() -> List[Dict[str, Any]]:
    global _PAPERS
    if not _PAPERS:
        if not Path(DB_JSON).exists():
            raise FileNotFoundError(f"Missing {DB_JSON}. Run ID_Generate.py first.")
        with open(DB_JSON, "r", encoding="utf-8") as f:
            _PAPERS = json.load(f)
    return _PAPERS

def _compose_doc_text(p: Dict[str, Any]) -> str:
    # Text used for TF-IDF; lower-cased
    parts = [
        p.get("title", ""),
        p.get("journal", ""),
        p.get("first_author", ""),
        p.get("co_authors", ""),
        " ".join(p.get("keywords", [])),
        p.get("year", "")
    ]
    return " ".join([str(x) for x in parts]).lower()

def build_index():
    global _VECTORIZER, _DOC_MATRIX
    papers = load_papers()
    corpus = [_compose_doc_text(p) for p in papers]
    _VECTORIZER = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
    _DOC_MATRIX = _VECTORIZER.fit_transform(corpus)

# Build once on import
build_index()

# ----------------------
# Query parsing
# ----------------------
def _find_years(q: str) -> Tuple[str, str]:
    # Finds constraints: exact year or ranges with after/before/since
    # Returns (year_min, year_max) where empty string means no bound
    q_low = q.lower()
    years = re.findall(r"\b(19|20)\d{2}\b", q)
    all_years = re.findall(r"\b((?:19|20)\d{2})\b", q)
    year_min, year_max = "", ""

    # Range: after/since X, before Y
    m_after = re.search(r"\b(after|since)\s+((?:19|20)\d{2})", q_low)
    m_before = re.search(r"\b(before|until)\s+((?:19|20)\d{2})", q_low)
    if m_after:
        year_min = m_after.group(2)
    if m_before:
        year_max = m_before.group(2)

    # Exact: "year: 2021" or just a standalone year if no range set
    m_year = re.search(r"\byear\s*[:=]\s*((?:19|20)\d{2})", q_low)
    if m_year:
        y = m_year.group(1)
        year_min, year_max = y, y
    elif all_years and not (year_min or year_max):
        # Take the first year as an exact match if query contains a single year
        uniq = list(dict.fromkeys(all_years))
        if len(uniq) == 1:
            year_min = year_max = uniq[0]
    return year_min, year_max

def _extract_after_token(q_low: str, token: str) -> str:
    # Extract phrase right after token: e.g., "by Dr. Mehta", "journal: IEEE Transactions"
    # Handles "by <words...>", "author: <...>", "journal: <...>", "in <...>"
    pat = rf"{token}\s*[:]*\s+([a-z0-9\.\-&/() ',]+)"
    m = re.search(pat, q_low)
    if m:
        # Stop if we hit another keyword (by/in/journal/author/before/after/since/year)
        val = m.group(1)
        val = re.split(r"\b(by|in|journal|author|before|after|since|year)\b", val)[0]
        return val.strip(" ,")
    return ""

def parse_query(q: str) -> Dict[str, Any]:
    """
    Detects filters:
      - author (e.g., "by Dr. Mehta", "author: Mehta")
      - journal (e.g., "in IEEE", "journal: Springer")
      - year exact/range (year: 2021, after 2019, before 2022)
      - keywords (remaining words)
    """
    q = q.strip()
    q_low = q.lower()

    author = _extract_after_token(q_low, r"\bby\b") or _extract_after_token(q_low, r"\bauthor\b")
    journal = _extract_after_token(q_low, r"\bin\b") or _extract_after_token(q_low, r"\bjournal\b")
    year_min, year_max = _find_years(q)

    # Remove extracted parts to isolate keywords
    rm = [author, journal, year_min, year_max, "author", "journal", "year", "after", "before", "since", "in", "by"]
    cleaned = q_low
    for r in rm:
        if r:
            cleaned = cleaned.replace(str(r).lower(), " ")
    cleaned = re.sub(r"\b(author|journal|year|after|before|since|in|by)\b", " ", cleaned)
    cleaned = re.sub(r"[^a-z0-9\s\-\&]", " ", cleaned)
    tokens = [t for t in cleaned.split() if t and t not in _STOPWORDS and not re.match(r"^(19|20)\d{2}$", t)]
    keywords = list(dict.fromkeys(tokens))  # de-duplicate

    return {
        "author": author,
        "journal": journal,
        "year_min": year_min,
        "year_max": year_max,
        "keywords": keywords
    }

# ----------------------
# Hybrid search
# ----------------------
def _within_year_bounds(y: str, ymin: str, ymax: str) -> bool:
    if not (ymin or ymax):
        return True
    if not y:
        return False
    try:
        yi = int(y)
        if ymin and yi < int(ymin):
            return False
        if ymax and yi > int(ymax):
            return False
        return True
    except Exception:
        return False

def _passes_filters(p: Dict[str, Any], f: Dict[str, Any]) -> bool:
    n = p.get("_norm", {})
    # Author: if provided, require soft match in first_author
    if f.get("author"):
        if fuzz.partial_ratio(n.get("first_author",""), f["author"]) < 70:
            return False
    # Journal: if provided, require soft match in journal
    if f.get("journal"):
        if fuzz.partial_ratio(n.get("journal",""), f["journal"]) < 70:
            return False
    # Year bounds
    if not _within_year_bounds(n.get("year",""), f.get("year_min",""), f.get("year_max","")):
        return False
    # Keywords: at least one keyword should appear in title/journal/keywords/author
    kws = f.get("keywords", [])
    if kws:
        hay = " ".join([n.get("title",""), n.get("journal",""), n.get("first_author",""), " ".join(n.get("keywords",[]))])
        if not any(k in hay for k in kws):
            # Allow fuzzy fallback (e.g., misspellings)
            fuzzy_ok = any(fuzz.partial_ratio(hay, k) >= 70 for k in kws)
            if not fuzzy_ok:
                return False
    return True

def _score_paper(p: Dict[str, Any], q: str, q_vec, idx: int) -> float:
    # Cosine similarity
    cos = cosine_similarity(q_vec, _DOC_MATRIX[idx]).ravel()[0]  # 0..1

    # Fuzzy signals against title, journal, author
    n = p.get("_norm", {})
    f1 = fuzz.partial_ratio(n.get("title",""), q.lower()) / 100.0
    f2 = fuzz.partial_ratio(n.get("journal",""), q.lower()) / 100.0
    f3 = fuzz.partial_ratio(n.get("first_author",""), q.lower()) / 100.0
    fuzzy = max(f1, f2, f3)

    # Blend
    return 0.7 * cos + 0.3 * fuzzy

def hybrid_search(filters: Dict[str, Any], raw_query: str, top_k: int = 10) -> List[Dict[str, Any]]:
    papers = load_papers()
    if _VECTORIZER is None or _DOC_MATRIX is None:
        build_index()

    # 1) Apply structured filters
    candidate_idxs = []
    for i, p in enumerate(papers):
        if _passes_filters(p, filters):
            candidate_idxs.append(i)

    if not candidate_idxs:
        # Relax: if strict filters fail, return best semantic matches overall
        candidate_idxs = list(range(len(papers)))

    # 2) Vectorize the query
    q_vec = _VECTORIZER.transform([raw_query.lower()])

    # 3) Score candidates
    scored = []
    for i in candidate_idxs:
        s = _score_paper(papers[i], raw_query, q_vec, i)
        scored.append((s, i))

    # 4) Rank + return
    scored.sort(key=lambda x: x[0], reverse=True)
    out = []
    for s, i in scored[:top_k]:
        item = dict(papers[i])
        item["_score"] = round(float(s), 4)
        out.append(item)
    return out
