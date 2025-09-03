from flask import Flask, request, jsonify, render_template
import requests

app = Flask(__name__)

# Function to fetch author info from Semantic Scholar API
def get_author_info(teacher):
    url = "https://api.semanticscholar.org/graph/v1/author/search"
    params = {
        "query": teacher,
        "limit": 1,
        "fields": "authorId,name,affiliations,paperCount,citationCount,hIndex,url"
    }
    response = requests.get(url, params=params, timeout=10)
    data = response.json()

    if "data" not in data or not data["data"]:
        return None

    author = data["data"][0]
    author_id = author.get("authorId")

    # Fetch top 5 papers
    papers = []
    if author_id:
        papers_url = f"https://api.semanticscholar.org/graph/v1/author/{author_id}/papers"
        papers_params = {
            "limit": 5,
            "fields": "title,year,url"
        }
        papers_response = requests.get(papers_url, params=papers_params, timeout=10).json()
        papers = papers_response.get("data", [])

    return {
        "name": author.get("name", "N/A"),
        "affiliations": author.get("affiliations", []),
        "papers": author.get("paperCount", "N/A"),
        "citations": author.get("citationCount", "N/A"),
        "hIndex": author.get("hIndex", "N/A"),
        "profile_url": author.get("url", "#"),
        "top_papers": [
            {
                "title": p.get("title", "Untitled"),
                "year": p.get("year", "N/A"),
                "url": p.get("url", "#")
            }
            for p in papers
        ]
    }

@app.route("/")
def home():
    # Serves templates/index1.html
    return render_template("index1.html")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    teacher = (data.get("teacher") or "").strip()
    if not teacher:
        return jsonify({"answer": "Please enter a teacher's name."}), 400

    try:
        author = get_author_info(teacher)
        if not author:
            return jsonify({"answer": f"No author found for '{teacher}'."})

        # Format publications
        pubs_html = "".join(
            f'<li><a href="{p["url"]}" target="_blank">{p["title"]}</a> ({p["year"]})</li>'
            for p in author["top_papers"]
        ) or "<li>No publications found.</li>"

        # Final HTML response
        html = f"""
        <strong>Name:</strong> {author['name']}<br>
        <strong>Affiliations:</strong> {", ".join(author['affiliations']) or "N/A"}<br>
        <strong>Papers:</strong> {author['papers']}<br>
        <strong>Citations:</strong> {author['citations']}<br>
        <strong>hIndex:</strong> {author['hIndex']}<br>
        <strong>Profile:</strong> <a href="{author['profile_url']}" target="_blank">Semantic Scholar</a><br>
        <strong>Top Publications:</strong>
        <ul>{pubs_html}</ul>
        """
        return jsonify({"answer": html})

    except Exception as e:
        return jsonify({"answer": f"Error fetching data: {e}"}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5000)
