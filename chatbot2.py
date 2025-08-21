from config import API_KEY

from flask import Flask, jsonify, request, render_template, send_file
from flask_cors import CORS
import pandas as pd
import requests
import random
import docx
import json
from datetime import datetime
from docx import Document
import PyPDF2
from werkzeug.utils import secure_filename
import os
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)
CORS(app)

# Load Excel once
df = pd.read_excel("research.xlsx", header=1)
df.columns = df.columns.str.strip()  # Clean column names

PAPERS_FILE = "saved_papers.json"

api_key=os.getenv("GROK_API_KEY")

def load_papers():
    if os.path.exists(PAPERS_FILE):
        with open(PAPERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_papers(data):
    with open(PAPERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/create-paper")
def create_paper_page():
    return render_template("create_paper.html")

@app.route("/download-paper", methods=["POST"])
def download_paper():
    data = request.json
    format_type = data.get("format", "docx")

    if format_type == "docx":
        doc = Document()
        doc.add_heading(data.get("title", "Untitled Paper"), 0)
        if data.get("authors"):
            doc.add_paragraph(f"Authors: {data['authors']}")
            doc.add_paragraph("")

        for sec in data.get("sections", []):
            doc.add_heading(sec["title"], level=1)
            doc.add_paragraph(sec["content"])

        filepath = "generated_paper.docx"
        doc.save(filepath)

    elif format_type == "pdf":
        filepath = "generated_paper.pdf"
        doc = SimpleDocTemplate(filepath)
        styles = getSampleStyleSheet()
        story = []

        story.append(Paragraph(data.get("title", "Untitled Paper"), styles["Title"]))
        if data.get("authors"):
            story.append(Paragraph(f"Authors: {data['authors']}", styles["Normal"]))
        story.append(Spacer(1, 12))

        for sec in data.get("sections", []):
            story.append(Paragraph(sec["title"], styles["Heading2"]))
            story.append(Paragraph(sec["content"], styles["Normal"]))
            story.append(Spacer(1, 12))

        doc.build(story)

    return send_file(filepath, as_attachment=True)

@app.route("/save-paper", methods=["POST"])
def save_paper():
    paper = request.json
    if not paper:
        return jsonify({"message": "Invalid paper data"}), 400

    papers = load_papers()

    paper_entry = {
        "id": len(papers) + 1,
        "title": paper.get("title", "Untitled Paper"),
        "sections": paper.get("sections", []),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    papers.append(paper_entry)
    save_papers(papers)

    return jsonify({"message": f"Paper '{paper_entry['title']}' saved successfully!"})

@app.route("/get-papers", methods=["GET"])
def get_papers():
    papers = load_papers()
    return jsonify(papers)

@app.route("/myspace")
def myspace_page():
    return render_template("myspace.html")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    question = data.get("question", "").strip().lower()

    if not question:
        return jsonify({"answer": "Please enter a valid question."}), 400

    matched_papers = []

    # --- Step 1: Check Excel for journal/year matches ---
    for _, row in df.iterrows():
        journal = str(row.get("Journal Name", "")).strip().lower()
        year = str(row.get("Year", "")).strip().lower()

        if journal in question or year in question:
            title = row.get("Article Title", "N/A")
            authors = row.get("First Author Name", "N/A")
            doi = row.get("DOI", "")
            alt_link = row.get("Article Link if DOI is not present", "")
            link = doi if pd.notna(doi) and doi else alt_link or "N/A"

            matched_papers.append(f"""
                <strong>Title:</strong> {title}<br>
                <strong>Authors:</strong> {authors}<br>
                <strong>Link:</strong> <a href="{link}" target="_blank">{link}</a><br><br>
            """)

    if matched_papers:
        return jsonify({"answer": "".join(matched_papers)})

    # --- Step 2: Fallback to Grok API ---
    try:
        grok_prompt = f"Answer this academic query: {question}"
        grok_response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "grok-2",  # or "gpt-4o-mini" if using OpenAI
                "messages": [
                    {"role": "system", "content": "You are an academic research assistant."},
                    {"role": "user", "content": grok_prompt}
                ]
            },
            timeout=15
        )

        if grok_response.status_code == 200:
            result = grok_response.json()["choices"][0]["message"]["content"]
        else:
            result = f"Grok API failed: {grok_response.text}"

    except Exception as e:
        result = f"Error connecting to Grok API: {str(e)}"

    return jsonify({"answer": result})

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route("/plagirism")
def plagiarism_page():
    return render_template("plagirism.html")

@app.route("/check-plagiarism", methods=["POST"])
def check_plagiarism():
    if "file" not in request.files:
        return jsonify({"message": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"message": "No selected file"}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    # --- Step 1: Extract text depending on file type ---
    text = ""
    if filename.endswith(".txt"):
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
    elif filename.endswith(".docx"):
        import docx
        doc = docx.Document(filepath)
        text = "\n".join([para.text for para in doc.paragraphs])
    elif filename.endswith(".pdf"):
        import PyPDF2
        with open(filepath, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text() or ""

    # --- Step 2: Simulate plagiarism detection ---
    plagiarism_percentage = random.randint(5, 75)  

    return jsonify({"plagiarism": plagiarism_percentage})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
