"""
Jan Aushadhi Generic Medicine Finder
Database Setup Script — run once to build SQLite DB from CSVs
"""
import sqlite3
import csv
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "db", "janaushadhi.db")
MEDICINES_CSV = os.path.join(BASE_DIR, "data", "medicines.csv")
KENDRAS_CSV = os.path.join(BASE_DIR, "data", "kendras.csv")


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Enable WAL for better concurrency
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")

    # ── Medicines table ──────────────────────────────────────────────────────
    c.execute("DROP TABLE IF EXISTS medicines_fts")
    c.execute("DROP TABLE IF EXISTS medicines")

    c.execute("""
        CREATE TABLE medicines (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            drug_code       TEXT UNIQUE NOT NULL,
            product_name    TEXT NOT NULL,
            salt_composition TEXT NOT NULL,
            dosage_form     TEXT,
            unit_size       TEXT,
            mrp             REAL,
            category        TEXT,
            brand_equivalents TEXT
        )
    """)

    # FTS5 virtual table for lightning-fast full-text search
    c.execute("""
        CREATE VIRTUAL TABLE medicines_fts USING fts5(
            drug_code,
            product_name,
            salt_composition,
            category,
            brand_equivalents,
            content='medicines',
            content_rowid='id'
        )
    """)

    # ── Kendras table ────────────────────────────────────────────────────────
    c.execute("DROP TABLE IF EXISTS kendras")
    c.execute("""
        CREATE TABLE kendras (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            kendra_id   TEXT UNIQUE NOT NULL,
            name        TEXT NOT NULL,
            address     TEXT,
            district    TEXT,
            state       TEXT,
            pincode     TEXT,
            phone       TEXT,
            latitude    REAL,
            longitude   REAL
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_kendra_pin   ON kendras(pincode)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_kendra_state ON kendras(state)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_kendra_dist  ON kendras(district)")

    conn.commit()

    # ── Load medicines ───────────────────────────────────────────────────────
    loaded = 0
    with open(MEDICINES_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                c.execute("""
                    INSERT OR REPLACE INTO medicines
                        (drug_code, product_name, salt_composition, dosage_form,
                         unit_size, mrp, category, brand_equivalents)
                    VALUES (?,?,?,?,?,?,?,?)
                """, (
                    row["drug_code"].strip(),
                    row["product_name"].strip(),
                    row["salt_composition"].strip(),
                    row.get("dosage_form", "").strip(),
                    row.get("unit_size", "").strip(),
                    float(row["mrp"]) if row.get("mrp") else 0.0,
                    row.get("category", "").strip(),
                    row.get("brand_equivalents", "").strip(),
                ))
                loaded += 1
            except Exception as e:
                print(f"  [WARN] medicines row skip: {e}")

    # Populate FTS index
    c.execute("""
        INSERT INTO medicines_fts(rowid, drug_code, product_name, salt_composition,
                                  category, brand_equivalents)
        SELECT id, drug_code, product_name, salt_composition,
               category, brand_equivalents
        FROM medicines
    """)
    print(f"  OK Loaded {loaded} medicines")

    # ── Load kendras ─────────────────────────────────────────────────────────
    kloaded = 0
    with open(KENDRAS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                c.execute("""
                    INSERT OR REPLACE INTO kendras
                        (kendra_id, name, address, district, state, pincode,
                         phone, latitude, longitude)
                    VALUES (?,?,?,?,?,?,?,?,?)
                """, (
                    row["kendra_id"].strip(),
                    row["name"].strip(),
                    row.get("address", "").strip(),
                    row.get("district", "").strip(),
                    row.get("state", "").strip(),
                    row.get("pincode", "").strip(),
                    row.get("phone", "").strip(),
                    float(row["latitude"])  if row.get("latitude")  else None,
                    float(row["longitude"]) if row.get("longitude") else None,
                ))
                kloaded += 1
            except Exception as e:
                print(f"  [WARN] kendras row skip: {e}")

    conn.commit()
    conn.close()
    print(f"  OK Loaded {kloaded} kendras")
    print(f"\nDatabase ready at: {DB_PATH}")


if __name__ == "__main__":
    print("Setting up Jan Aushadhi database...")
    init_db()
