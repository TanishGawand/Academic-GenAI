from flask import Flask, request, jsonify
import json
import re

app = Flask(__name__)

# ========= Load Database =========
with open("research.json", "r", encoding="utf-8") as f:
    PAPERS = json.load(f)


# ========= Helper: Query Parsing =========
def parse_query(query: str):
    """
    Extract filters from natural language query.
    Supported filters: author, year, journal, topic
    """
    query = query.lower()

    filters = {
        "author": None,
        "year_after": None,
        "year_before": None,
        "journal": None,
        "topic": []
    }

    # --- Author (match "Dr." or capitalized names) ---
    author_match = re.findall(r"(dr\.?\s+[a-z]+)", query)
    if author_match:
        filters["author"] = author_match[0].replace("dr", "Dr").strip()

    # --- Year conditions ---
    after_match = re.search(r"after\s+(\d{4})", query)
    before_match = re.search(r"before\s+(\d{4})", query)
    year_match = re.search(r"\b(19|20)\d{2}\b", query)

    if after_match:
        filters["year_after"] = int(after_match.group(1))
    if before_match:
        filters["year_before"] = int(before_match.group(1))
    if year_match and not (after_match or before_match):
        filters["year_after"] = int(year_match.group(0)) - 1
        filters["year_before"] = int(year_match.group(0)) + 1

    # --- Journal filter ---
    for paper in PAPERS:
        journal = paper["journal"].lower()
        if journal in query:
            filters["journal"] = paper["journal"]
            break

    # --- Topic keywords (AI, blockchain, etc.) ---
    keywords = ["ai", "machine learning", "blockchain", "cybersecurity",
                "data mining", "cloud", "iot", "nlp", "healthcare"]

    for kw in keywords:
        if kw in query:
            filters["topic"].append(kw)

    return filters


# ========= Helper: Search Function =========
def search_papers(filters):
    results = []

    for paper in PAPERS:
        match = True

        # Author filter
        if filters["author"]:
            if filters["author"].lower() not in paper["first_author"].lower():
                match = False

        # Year filter
        if filters["year_after"] and int(paper["year"]) <= filters["year_after"]:
            match = False
        if filters["year_before"] and int(paper["year"]) >= filters["year_before"]:
            match = False

        # Journal filter
        if filters["journal"]:
            if filters["journal"].lower() not in paper["journal"].lower():
                match = False

        # Topic filter (match in title + keywords)
        if filters["topic"]:
            found_topic = False
            for topic in filters["topic"]:
                if (topic in paper["title"].lower()) or \
                   any(topic in kw.lower() for kw in paper["keywords"]):
                    found_topic = True
            if not found_topic:
                match = False

        if match:
            results.append(paper)

    return results


# ========= Flask API =========
@app.route("/search", methods=["GET"])
def search():
    query = request.args.get("q", "")
    if not query:
        return jsonify({"error": "Missing query param ?q="}), 400

    filters = parse_query(query)
    results = search_papers(filters)

    return jsonify({
        "query": query,
        "filters": filters,
        "results": results,
        "count": len(results)
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
