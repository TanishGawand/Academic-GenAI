import pandas as pd
import json

# Load Excel
df = pd.read_excel("research.xlsx", header=1)

# Generate Teacher IDs
teacher_id = {}
counter = 1
for name in df['First Author Name'].dropna().unique():
    teacher_id[name.strip().lower()] = f"T{counter:03d}"
    counter += 1

df["Teacher ID"] = df['First Author Name'].str.strip().str.lower().map(teacher_id)

# Save updated Excel
df.to_excel("research_with_ids.xlsx", index=False)

# Convert to JSON for search engine
papers = []
for _, row in df.iterrows():
    papers.append({
        "teacher_id": row.get("Teacher ID", ""),
        "first_author": str(row.get("First Author Name", "")),
        "co_authors": str(row.get("Co-Authors", "")),
        "title": str(row.get("Article Title", "")),
        "journal": str(row.get("Journal Name", "")),
        "year": str(row.get("Year", "")),
        "keywords": [kw.strip() for kw in str(row.get("Keywords", "")).split(",") if kw],
        "doi": str(row.get("DOI", "")),
        "alt_link": str(row.get("Article Link if DOI is not present", "")),
    })

with open("research.json", "w", encoding="utf-8") as f:
    json.dump(papers, f, indent=2, ensure_ascii=False)

print("✅ research_with_ids.xlsx and research.json generated successfully")
