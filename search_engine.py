# search_engine.py
import json
import math
import re
from typing import List, Dict, Any, Optional, Tuple

from rapidfuzz import fuzz
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class ResearchSearchEngine:
    """
    Hybrid search over research.json:
      - Hard filters: author / year / journal / topic
      - Fuzzy signals: author, journal
      - TF–IDF similarity: title + keywords + journal + authors
    """

    def __init__(self, json_path: str = "research.json"):
        with open(json_path, "r", encoding="utf-8") as f:
            self.papers: List[Dict[str, Any]] = json.load(f)

        # build searchable text for each paper
        self.docs: List[str] = []
        for p in self.papers:
            parts = [
                str(p.get("title", "")),
                str(p.get("journal", "")),
                str(p.get("first_author", "")),
                str(p.get("co_authors", "")),
                " ".join(p.get("keywords", []) if isinstance(p.get("keywords", []), list) else [])
            ]
            self.docs.append(" | ".join([s.strip() for s in parts if s and str(s).strip()]))

        # TF–IDF vectorizer (local, no internet)
        self.vectorizer = TfidfVectorizer(
            strip_accents="unicode",
            lowercase=True,
            stop_words="english",
            ngram_range=(1, 2),
            max_features=50000
        )
        self.doc_matrix = self.vectorizer.fit_transform(self.docs)

    # -------- Query Parsing (rule-based) --------
    def parse_query(self, query: str) -> Dict[str, Any]:
        q = query.lower()

        filters = {
            "author": None,
            "journal": None,
            "year_after": None,
            "year_before": None,
            "exact_year": None,
            "topics": []  # list[str]
        }

        # after/before/exact year
        m_after = re.search(r"\bafter\s+(19|20)\d{2}\b", q)
        if m_after:
            filters["year_after"] = int(m_after.group(0).split()[-1])

        m_before = re.search(r"\bbefore\s+(19|20)\d{2}\b", q)
        if m_before:
            filters["year_before"] = int(m_before.group(0).split()[-1])

        # "in 2021", "of 2022" etc., only if no after/before already set
        if filters["year_after"] is None and filters["year_before"] is None:
            m_year = re.search(r"\b(19|20)\d{2}\b", q)
            if m_year:
                filters["exact_year"] = int(m_year.group(0))

        # author patterns: "by Dr. Mehta", "by Prof. Rao", or "by <name>"
        m_author = re.search(r"\bby\s+(dr\.?|prof\.?)?\s*([a-z][a-z\s\.]+)", q)
        if m_author:
            name = m_author.group(0).replace("by", "").strip()
            filters["author"] = re.sub(r"\s+", " ", name).strip(". ").title()

        # journal: "in IEEE", "in Springer", "published in Nature"
        m_journal = re.search(r"\b(in|published in)\s+([a-z0-9&\-\.\s]+)", q)
        if m_journal:
            j = m_journal.group(2).strip()
            # stop at "after/before/in <year>"
            j = re.split(r"\b(after|before|in\s+(19|20)\d{2})\b", j)[0].strip()
            filters["journal"] = j

        # topic keywords: collect interesting tokens (basic)
        topic_seed = [
            "ai", "artificial intelligence", "machine learning", "ml",
            "deep learning", "dl", "nlp", "natural language processing",
            "computer vision", "cv", "blockchain", "cybersecurity",
            "data mining", "cloud", "cloud computing", "iot",
            "healthcare", "bioinformatics", "security", "privacy",
            "recommendation", "graph", "optimization", "edge computing"
        ]
        topics_found = []
        for kw in topic_seed:
            if kw in q:
                topics_found.append(kw)
        # also add quoted phrases as topics: "..." in the query
        topics_found += re.findall(r"\"([^\"]+)\"", query)
        filters["topics"] = list(dict.fromkeys(topics_found))  # unique, keep order

        return filters

    # -------- Core filter pass (hard constraints) --------
    def _passes_filters(self, p: Dict[str, Any], f: Dict[str, Any]) -> bool:
        # year logic
        py = p.get("year", "")
        try:
            py_int = int(str(py).strip())
        except Exception:
            py_int = None

        if f["exact_year"] is not None and py_int is not None:
            if py_int != f["exact_year"]:
                return False

        if f["year_after"] is not None and py_int is not None:
            if py_int <= f["year_after"]:
                return False

        if f["year_before"] is not None and py_int is not None:
            if py_int >= f["year_before"]:
                return False

        # topic must exist in title or keywords, if provided
        if f["topics"]:
            title = (p.get("title") or "").lower()
            kws = [k.lower() for k in (p.get("keywords") or [])] if isinstance(p.get("keywords", []), list) else []
            combined = title + " " + " ".join(kws)
            if not any(t.lower() in combined for t in f["topics"]):
                return False

        return True

    # -------- Score calculation (hybrid) --------
    def _hybrid_score(
        self,
        p: Dict[str, Any],
        query: str,
        filters: Dict[str, Any],
        tfidf_sim: float
    ) -> float:
        """
        Combine signals:
        - TF–IDF similarity (0..1)
        - Fuzzy author match (0..100 → 0..1)
        - Fuzzy journal match (0..100 → 0..1)
        - Topic presence bonus
        """
        score = 0.0

        # TF–IDF signal (weight 0.6)
        score += 0.6 * float(tfidf_sim)

        # Fuzzy author (0.2)
        if filters.get("author"):
            fa = p.get("first_author", "") or ""
            fuzzy_a = fuzz.partial_ratio(filters["author"].lower(), fa.lower()) / 100.0
            score += 0.2 * fuzzy_a

        # Fuzzy journal (0.15)
        if filters.get("journal"):
            j = p.get("journal", "") or ""
            fuzzy_j = fuzz.partial_ratio(filters["journal"].lower(), j.lower()) / 100.0
            score += 0.15 * fuzzy_j

        # Topic presence bonus (0.05)
        if filters.get("topics"):
            title = (p.get("title") or "").lower()
            kws = [k.lower() for k in (p.get("keywords") or [])] if isinstance(p.get("keywords", []), list) else []
            combined = title + " " + " ".join(kws)
            topic_hits = sum(1 for t in filters["topics"] if t.lower() in combined)
            if topic_hits > 0:
                # cap to 0.05
                score += min(0.05, 0.02 * topic_hits)

        # clamp
        return max(0.0, min(score, 1.0))

    # -------- Public search API --------
    def search(self, query: str, top_k: int = 20) -> Dict[str, Any]:
        filters = self.parse_query(query)

        # Build a query string for TF–IDF:
        # include detected topics/author/journal words to help similarity
        q_parts = [query]
        if filters.get("author"):
            q_parts.append(filters["author"])
        if filters.get("journal"):
            q_parts.append(filters["journal"])
        q_parts += filters.get("topics", [])
        q_aug = " ".join(q_parts)

        q_vec = self.vectorizer.transform([q_aug])
        sims = cosine_similarity(q_vec, self.doc_matrix).ravel()

        # score and filter
        scored: List[Tuple[float, Dict[str, Any]]] = []
        for idx, p in enumerate(self.papers):
            if not self._passes_filters(p, filters):
                continue
            hybrid = self._hybrid_score(p, query, filters, sims[idx])
            if hybrid > 0.0:
                scored.append((hybrid, p))

        # sort by score desc
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:top_k]

        # attach score to result for transparency
        results = []
        for s, p in top:
            item = dict(p)
            item["_score"] = round(float(s), 4)
            results.append(item)

        return {
            "query": query,
            "filters": filters,
            "count": len(results),
            "results": results
        }
