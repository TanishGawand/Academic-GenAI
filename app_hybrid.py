# app_hybrid.py
from flask import Flask, request, jsonify
from search_engine import ResearchSearchEngine

app = Flask(__name__)
engine = ResearchSearchEngine(json_path="research.json")


@app.route("/search", methods=["GET"])
def search():
    q = request.args.get("q", "").strip()
    top_k = int(request.args.get("k", 20))
    if not q:
        return jsonify({"error": "Missing query param ?q=<your question>"}), 400

    out = engine.search(q, top_k=top_k)
    return jsonify(out)


if __name__ == "__main__":
    app.run(debug=True, port=5001)
