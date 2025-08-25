import pandas as pd
import json
import sqlite3
import os

# ========== CONFIG ==========
EXCEL_FILE = "research.xlsx"
JSON_FILE = "research.json"
SQLITE_FILE = "research.db"
TABLE_NAME = "research_papers"
# ============================

def excel_to_json(excel_file, json_file):
    """Convert Excel to clean JSON format"""
    df = pd.read_excel(excel_file)

    # Standardize column names (adapt if your Excel has slightly different names)
    df = df.rename(columns={
        "Teacher ID": "teacher_id",
        "First Author Name": "first_author",
        "Co-Authors Name": "co_authors",
        "Title of Paper": "title",
        "Journal Name": "journal",
        "Year": "year",
        "Keywords": "keywords",
        "DOI": "doi"
    })

    # Clean NaN values → ""
    df = df.fillna("")

    # Ensure keywords are always a list
    def process_keywords(x):
        if isinstance(x, str):
            return [kw.strip() for kw in x.split(",") if kw.strip()]
        return []

    df["keywords"] = df["keywords"].apply(process_keywords)

    # Convert to list of dicts
    records = df.to_dict(orient="records")

    # Save JSON
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=4, ensure_ascii=False)

    print(f"✅ JSON saved at {json_file} with {len(records)} records.")
    return records


def excel_to_sqlite(excel_file, sqlite_file, table_name):
    """Convert Excel to SQLite database"""
    df = pd.read_excel(excel_file)

    df = df.rename(columns={
        "Teacher ID": "teacher_id",
        "First Author Name": "first_author",
        "Co-Authors Name": "co_authors",
        "Title of Paper": "title",
        "Journal Name": "journal",
        "Year": "year",
        "Keywords": "keywords",
        "DOI": "doi"
    })

    df = df.fillna("")

    # Save to SQLite
    conn = sqlite3.connect(sqlite_file)
    df.to_sql(table_name, conn, if_exists="replace", index=False)
    conn.close()

    print(f"✅ SQLite DB saved at {sqlite_file} (table: {table_name}) with {len(df)} records.")


if __name__ == "__main__":
    if not os.path.exists(EXCEL_FILE):
        print(f"❌ ERROR: {EXCEL_FILE} not found. Place it in the project folder.")
    else:
        excel_to_json(EXCEL_FILE, JSON_FILE)
        excel_to_sqlite(EXCEL_FILE, SQLITE_FILE, TABLE_NAME)
