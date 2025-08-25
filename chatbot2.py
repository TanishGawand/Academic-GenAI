from flask import Flask, jsonify, request, render_template, send_file
from flask_cors import CORS
import pandas as pd
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
import re
from rapidfuzz import fuzz

app = Flask(__name__)
CORS(app)

# Load Excel once
df = pd.read_excel("research.xlsx", header=1)
df.columns = df.columns.str.strip()  # Clean column names

PAPERS_FILE = "saved_papers.json"


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
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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

    # --- Step 1: Extract Year from Question ---
    years_in_q = re.findall(r"\b(?:19|20)\d{2}\b", question)
    year_query = years_in_q[0] if years_in_q else None

    # --- Step 2: Fuzzy Teacher Name match ---
    teacher_name = None
    teacher_scores = []
    for _, row in df.iterrows():
        row_teacher = str(row.get("First Author Name", "")).strip().lower()
        if not row_teacher:
            continue
        score = fuzz.partial_ratio(row_teacher, question)
        teacher_scores.append((score, row_teacher))

    if teacher_scores:
        best_score, best_name = max(teacher_scores, key=lambda x: x[0])
        if best_score >= 70:  # threshold
            teacher_name = best_name

    # --- Step 3: Filter Rows ---
    for _, row in df.iterrows():
        row_teacher = str(row.get("First Author Name", "")).strip().lower()

        # Normalize year
        cell_year = row.get("Year", "")
        if pd.notna(cell_year):
            try:
                row_year = str(int(float(cell_year)))
            except Exception:
                row_year = str(cell_year).strip()
        else:
            row_year = ""

        teacher_match = bool(teacher_name and row_teacher == teacher_name)

        # Year match
        year_match = False
        if year_query:
            year_match = (row_year == year_query)
        elif row_year and row_year in question:
            year_match = True

        # Final condition
        if teacher_name and year_query:
            condition = teacher_match and year_match
        elif teacher_name:
            condition = teacher_match
        elif year_query:
            condition = year_match
        else:
            condition = False

        if condition:
            title = row.get("Article Title", "N/A")
            authors = row.get("First Author Name", "N/A")
            journal = row.get("Journal Name", "N/A")
            doi = row.get("DOI", "")
            alt_link = row.get("Article Link if DOI is not present", "")
            link = doi if pd.notna(doi) and doi else alt_link or "N/A"

            matched_papers.append(
                f"""
                <strong>Title:</strong> {title}<br>
                <strong>Authors:</strong> {authors}<br>
                <strong>Journal:</strong> {journal}<br>
                <strong>Year:</strong> {row_year}<br>
                <strong>Link:</strong> <a href="{link}" target="_blank">{link}</a><br><br>
                """
            )

    if matched_papers:
        return jsonify({"answer": "".join(matched_papers)})

    return jsonify({"answer": "No matching papers found."})


UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


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
        doc = docx.Document(filepath)
        text = "\n".join([para.text for para in doc.paragraphs])
    elif filename.endswith(".pdf"):
        with open(filepath, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text() or ""

    # --- Step 2: Simulate plagiarism detection ---
    plagiarism_percentage = random.randint(5, 75)

    return jsonify({"plagiarism": plagiarism_percentage})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
