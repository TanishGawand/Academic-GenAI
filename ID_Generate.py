import pandas as pd
import json
from pathlib import Path

SRC_XLSX = "research.xlsx"
OUT_XLSX = "research_with_ids.xlsx"
OUT_JSON = "research.json"

def main():
    if not Path(SRC_XLSX).exists():
        raise FileNotFoundError(f"Missing {SRC_XLSX}. Put your Excel in the project root.")

    # 1) Load Excel (header row at index 1 like your original)
    df = pd.read_excel(SRC_XLSX, header=1)
    df.columns = df.columns.str.strip()

    # 2) Generate Teacher IDs (stable across runs)
    teacher_id = {}
    counter = 1
    for name in df['First Author Name'].dropna().unique():
        teacher_id[name.strip().lower()] = f"T{counter:03d}"
        counter += 1
    df["Teacher ID"] = df['First Author Name'].astype(str).str.strip().str.lower().map(teacher_id)

    # 3) Save updated Excel
    df.to_excel(OUT_XLSX, index=False)

    # 4) Convert to JSON (normalized fields)
    papers = []
    for _, row in df.iterrows():
        year_val = row.get("Year", "")
        try:
            year_str = str(int(float(year_val))) if pd.notna(year_val) and str(year_val).strip() else ""
        except Exception:
            year_str = str(year_val).strip() if pd.notna(year_val) else ""

        keywords_raw = str(row.get("Keywords", "") or "")
        keywords_list = [kw.strip() for kw in keywords_raw.split(",") if kw.strip()]

        paper = {
            "teacher_id": str(row.get("Teacher ID", "") or ""),
            "first_author": str(row.get("First Author Name", "") or ""),
            "co_authors": str(row.get("Co-Authors", "") or ""),
            "title": str(row.get("Article Title", "") or ""),
            "journal": str(row.get("Journal Name", "") or ""),
            "year": year_str,
            "keywords": keywords_list,
            "doi": str(row.get("DOI", "") or ""),
            "alt_link": str(row.get("Article Link if DOI is not present", "") or "")
        }
        # Also store normalized helper fields
        paper["_norm"] = {
            "first_author": paper["first_author"].strip().lower(),
            "co_authors": paper["co_authors"].strip().lower(),
            "title": paper["title"].strip().lower(),
            "journal": paper["journal"].strip().lower(),
            "year": paper["year"].strip(),
            "keywords": [k.lower() for k in paper["keywords"]]
        }
        papers.append(paper)

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(papers, f, indent=2, ensure_ascii=False)

    print(f"✅ Wrote {OUT_XLSX} and {OUT_JSON} ({len(papers)} records).")

if __name__ == "__main__":
    main()
