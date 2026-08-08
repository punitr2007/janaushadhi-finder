"""
Jan Aushadhi Generic Medicine Finder — Flask Backend
"""
import os
import io
import math
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from PIL import Image
from rapidfuzz import fuzz, process

# ── Config ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH   = os.path.join(BASE_DIR, "db", "janaushadhi.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DATA_DATE = "July 2025"  # Update when refreshing the CSV


def ensure_database():
    """Initialize SQLite database on first boot (useful for fresh deploys)."""
    if os.path.exists(DB_PATH):
        return
    from setup_db import init_db
    init_db()


ensure_database()

# ── Database helpers ──────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def medicine_row_to_dict(row) -> dict:
    d = dict(row)
    brands = d.get("brand_equivalents", "") or ""
    d["brand_list"] = [b.strip() for b in brands.split(",") if b.strip()]
    # Compute estimated branded price (heuristic: ~8–20× the JA MRP)
    mrp = d.get("mrp", 0) or 0
    d["estimated_branded_price"] = round(mrp * 12, 2)
    d["savings_pct"] = round((1 - mrp / max(d["estimated_branded_price"], 1)) * 100, 0)
    return d


def kendra_row_to_dict(row) -> dict:
    return dict(row)


# ── Fuzzy search helpers ──────────────────────────────────────────────────────

def _build_search_corpus(conn) -> list[dict]:
    """Load all medicines for fuzzy scoring (cached in app context)."""
    rows = conn.execute(
        "SELECT id, drug_code, product_name, salt_composition, "
        "       dosage_form, unit_size, mrp, category, brand_equivalents "
        "FROM medicines"
    ).fetchall()
    return [medicine_row_to_dict(r) for r in rows]


def fuzzy_search(query: str, top_n: int = 10) -> list[dict]:
    """
    Multi-field fuzzy search:
      1. SQLite FTS5 for fast candidate retrieval
      2. RapidFuzz for re-ranking by similarity
    """
    query = query.strip()
    if not query or len(query) < 2:
        return []

    conn = get_db()
    try:
        # Step 1: FTS5 candidate retrieval (broad)
        fts_rows = conn.execute(
            """
            SELECT m.id, m.drug_code, m.product_name, m.salt_composition,
                   m.dosage_form, m.unit_size, m.mrp, m.category, m.brand_equivalents
            FROM medicines_fts f
            JOIN medicines m ON m.id = f.rowid
            WHERE medicines_fts MATCH ?
            LIMIT 100
            """,
            (f"{query}*",)
        ).fetchall()

        # Fall back to LIKE search if FTS finds nothing
        if not fts_rows:
            like_q = f"%{query}%"
            fts_rows = conn.execute(
                """
                SELECT id, drug_code, product_name, salt_composition,
                       dosage_form, unit_size, mrp, category, brand_equivalents
                FROM medicines
                WHERE product_name LIKE ?
                   OR salt_composition LIKE ?
                   OR brand_equivalents LIKE ?
                LIMIT 100
                """,
                (like_q, like_q, like_q)
            ).fetchall()

        candidates = [medicine_row_to_dict(r) for r in fts_rows]

        # Step 2: RapidFuzz re-ranking
        def score(med: dict) -> float:
            q = query.lower()
            scores = [
                fuzz.token_set_ratio(q, med["product_name"].lower()),
                fuzz.token_set_ratio(q, med["salt_composition"].lower()),
                fuzz.partial_ratio(q, med["brand_equivalents"].lower()),
            ]
            return max(scores)

        candidates.sort(key=score, reverse=True)
        return candidates[:top_n]

    finally:
        conn.close()


# ── Kendra search helpers ─────────────────────────────────────────────────────

def _haversine(lat1, lon1, lat2, lon2) -> float:
    """Distance in km between two lat/lon points."""
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.asin(math.sqrt(a))


def find_kendras(pincode: str = "", state: str = "", limit: int = 15) -> list[dict]:
    """
    Find nearest Kendras:
      1. Exact PIN match
      2. If < 3 found → same district
      3. If still < 3 → same state
    """
    conn = get_db()
    results = []

    try:
        pin = pincode.strip()
        st  = state.strip()

        if pin:
            rows = conn.execute(
                "SELECT * FROM kendras WHERE pincode = ? ORDER BY name",
                (pin,)
            ).fetchall()
            results = [kendra_row_to_dict(r) for r in rows]

        # Fallback 1: same district (look up district from a matching pin)
        if len(results) < 3 and pin:
            # Find district for this pin
            ref = conn.execute(
                "SELECT district, state FROM kendras WHERE pincode = ? LIMIT 1", (pin,)
            ).fetchone()
            if ref:
                district, matched_state = ref["district"], ref["state"]
                rows = conn.execute(
                    "SELECT * FROM kendras WHERE district = ? ORDER BY name LIMIT ?",
                    (district, limit)
                ).fetchall()
                seen_ids = {r["kendra_id"] for r in results}
                for r in rows:
                    d = kendra_row_to_dict(r)
                    if d["kendra_id"] not in seen_ids:
                        results.append(d)
                        seen_ids.add(d["kendra_id"])

        # Fallback 2: same state
        if len(results) < 3 and st:
            rows = conn.execute(
                "SELECT * FROM kendras WHERE state LIKE ? ORDER BY name LIMIT ?",
                (f"%{st}%", limit)
            ).fetchall()
            seen_ids = {r["kendra_id"] for r in results}
            for r in rows:
                d = kendra_row_to_dict(r)
                if d["kendra_id"] not in seen_ids:
                    results.append(d)
                    seen_ids.add(d["kendra_id"])

        # Compute distance if reference coords available
        if results and results[0].get("latitude"):
            ref_lat = results[0]["latitude"]
            ref_lon = results[0]["longitude"]
            for r in results:
                if r.get("latitude") and r.get("longitude"):
                    r["distance_km"] = round(
                        _haversine(ref_lat, ref_lon, r["latitude"], r["longitude"]), 1
                    )
                else:
                    r["distance_km"] = None
            results.sort(key=lambda x: x.get("distance_km") or 9999)

        return results[:limit]

    finally:
        conn.close()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", data_date=DATA_DATE)


@app.route("/api/search")
def api_search():
    q    = request.args.get("q", "").strip()
    mode = request.args.get("type", "auto")   # auto | salt | brand | name

    if not q or len(q) < 2:
        return jsonify({"results": [], "query": q, "count": 0})

    results = fuzzy_search(q, top_n=12)
    return jsonify({
        "results": results,
        "query": q,
        "count": len(results),
    })


@app.route("/api/kendras")
def api_kendras():
    pin   = request.args.get("pin", "").strip()
    state = request.args.get("state", "").strip()

    if not pin and not state:
        return jsonify({"error": "Provide pin or state"}), 400

    kendras = find_kendras(pincode=pin, state=state)
    return jsonify({
        "kendras": kendras,
        "count": len(kendras),
        "query": {"pin": pin, "state": state},
    })


@app.route("/api/medicine/<drug_code>")
def api_medicine_detail(drug_code):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM medicines WHERE drug_code = ?", (drug_code,)
        ).fetchone()
        if not row:
            return jsonify({"error": "Not found"}), 404
        return jsonify(medicine_row_to_dict(row))
    finally:
        conn.close()


@app.route("/api/ocr", methods=["POST"])
def api_ocr():
    """
    Upload prescription/medicine photo → extract medicine names.
    Returns: { raw_text, medicines, search_suggestions }
    """
    # Lazy import — only load if OCR route is hit
    try:
        from ocr.pipeline import run_ocr_pipeline
        import pytesseract  # noqa: F401 — check availability
    except ImportError as e:
        return jsonify({
            "success": False,
            "error": f"OCR dependencies not installed: {e}. Install opencv-python pytesseract.",
            "medicines": [],
        }), 500

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    try:
        img_bytes = file.read()
        pil_img = Image.open(io.BytesIO(img_bytes))
        result = run_ocr_pipeline(pil_img)

        # For each extracted name, get top search suggestion
        suggestions = []
        seen = set()
        for med in result.get("medicines", []):
            name = med.get("name", "")
            if name and name.lower() not in seen:
                seen.add(name.lower())
                hits = fuzzy_search(name, top_n=3)
                if hits:
                    suggestions.append({
                        "ocr_term": name,
                        "dosage_context": med.get("dosage", ""),
                        "matches": hits,
                    })

        result["search_suggestions"] = suggestions
        return jsonify(result)

    except Exception as e:
        return jsonify({"success": False, "error": str(e), "medicines": []}), 500


@app.route("/api/states")
def api_states():
    """Return list of unique states for dropdown."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT DISTINCT state FROM kendras ORDER BY state"
        ).fetchall()
        return jsonify({"states": [r["state"] for r in rows]})
    finally:
        conn.close()


@app.route("/api/info")
def api_info():
    conn = get_db()
    try:
        med_count  = conn.execute("SELECT COUNT(*) FROM medicines").fetchone()[0]
        kend_count = conn.execute("SELECT COUNT(*) FROM kendras").fetchone()[0]
        return jsonify({
            "medicines":  med_count,
            "kendras":    kend_count,
            "data_date":  DATA_DATE,
            "version":    "1.0.0",
        })
    finally:
        conn.close()


if __name__ == "__main__":
    ensure_database()
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
    )
