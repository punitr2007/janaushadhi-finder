# Jan Aushadhi Finder

Jan Aushadhi Finder is a Flask-based web application that helps users discover affordable Jan Aushadhi generic medicines, compare estimated savings against common branded alternatives, and locate nearby Jan Aushadhi Kendras.

It also includes an OCR-assisted prescription/medicine-strip scanner to extract medicine names from uploaded images and suggest matching generics.

## Key Features

- Smart medicine search (brand name, generic/salt name, category)
- Fuzzy-matched results using SQLite FTS5 + RapidFuzz re-ranking
- Price comparison and savings estimate display
- Nearby Kendra discovery by PIN code or state
- OCR upload flow for prescription/strip text extraction
- API endpoints for search, medicine details, states, and metadata

## Tech Stack

- **Backend:** Python, Flask
- **Database:** SQLite (with FTS5 virtual table)
- **Search:** RapidFuzz + SQL filtering
- **OCR:** OpenCV + pytesseract (optional route capability)
- **Frontend:** HTML, CSS, JavaScript
- **Production Server:** Gunicorn

## Project Structure

```text
janaushadhi-finder/
├── app.py
├── setup_db.py
├── requirements.txt
├── render.yaml
├── data/
├── db/
├── ocr/
├── static/
├── templates/
└── tests/
```

## Local Setup

### 1) Clone repository

```bash
git clone https://github.com/punitr2007/janaushadhi-finder.git
cd janaushadhi-finder
```

### 2) Create virtual environment and install dependencies

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3) Initialize database

```bash
python setup_db.py
```

### 4) Run app

```bash
python app.py
```

Open: `http://127.0.0.1:5000`

## API Overview

- `GET /api/search?q=<query>`
- `GET /api/medicine/<drug_code>`
- `GET /api/kendras?pin=<pincode>&state=<state>`
- `GET /api/states`
- `GET /api/info`
- `POST /api/ocr`

## Deployment (Render)

This project includes `render.yaml` for zero-config Render deployment.

1. Push code to GitHub.
2. In Render, select **New +** → **Blueprint**.
3. Connect this repository and deploy.

Render uses:

- `buildCommand`: `pip install -r requirements.txt`
- `startCommand`: `gunicorn app:app`

### Notes

- On first boot, the app auto-initializes SQLite DB if it does not exist.
- OCR functionality requires Tesseract binaries in the deployment environment.

## License

Add your preferred license (MIT/Apache-2.0/etc.) before public distribution.
