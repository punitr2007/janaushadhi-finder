"""
OCR Pipeline — OpenCV + Tesseract for medicine name extraction
Handles: printed labels, medicine strips, prescription photos
"""
import re
import cv2
import numpy as np
import pytesseract
from PIL import Image

# ── Medicine-context keywords to help filter OCR noise ───────────────────────
DOSAGE_UNITS = re.compile(
    r'\b(\d+\.?\d*)\s*(mg|mcg|g|ml|iu|units?|%|tablet|cap(?:sule)?|inj(?:ection)?|syrup|cream|gel|ointment|drop)\b',
    re.IGNORECASE
)

# Common words to ignore in OCR output (packaging noise)
NOISE_WORDS = {
    "store", "keep", "cool", "dry", "place", "refrigerate", "shake",
    "well", "before", "use", "read", "leaflet", "carefully", "prescription",
    "only", "batch", "mfg", "exp", "date", "manufactured", "marketed",
    "distributed", "licensed", "govt", "india", "pvt", "ltd", "pharma",
    "laboratories", "pharmaceuticals", "each", "contains", "composition",
    "warning", "caution", "schedule", "price", "mrp", "incl",
}

# Patterns that look like salt/medicine names
MEDICINE_NAME_PATTERN = re.compile(
    r'\b([A-Z][a-z]+(?:[\s\-][A-Z]?[a-z]+)*)\s*(\d+\.?\d*\s*(?:mg|mcg|g|iu|%))?',
    re.MULTILINE
)


def preprocess_image(image_input) -> np.ndarray:
    """
    Apply OpenCV preprocessing pipeline for better OCR accuracy.
    Accepts file path, PIL Image, or numpy array.
    """
    # Load image
    if isinstance(image_input, str):
        img = cv2.imread(image_input)
    elif isinstance(image_input, Image.Image):
        img = cv2.cvtColor(np.array(image_input), cv2.COLOR_RGB2BGR)
    elif isinstance(image_input, np.ndarray):
        img = image_input.copy()
    else:
        raise ValueError("Unsupported image input type")

    # 1. Resize if too small (helps OCR)
    h, w = img.shape[:2]
    if max(h, w) < 800:
        scale = 800 / max(h, w)
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    # 2. Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 3. Denoise
    gray = cv2.fastNlMeansDenoising(gray, h=10, searchWindowSize=21, templateWindowSize=7)

    # 4. Deskew (find angle and rotate)
    gray = _deskew(gray)

    # 5. Adaptive thresholding for binarisation
    thresh = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=31,
        C=11
    )

    # 6. Morphological closing to connect broken characters
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 1))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    return thresh


def _deskew(gray: np.ndarray) -> np.ndarray:
    """Detect and correct document skew."""
    try:
        coords = np.column_stack(np.where(gray < 128))
        if len(coords) < 100:
            return gray
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        if abs(angle) < 0.5:
            return gray
        h, w = gray.shape
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC,
                                  borderMode=cv2.BORDER_REPLICATE)
        return rotated
    except Exception:
        return gray


def extract_text(preprocessed: np.ndarray) -> str:
    """Run Tesseract OCR on preprocessed image."""
    config = (
        "--psm 6 "         # Assume uniform block of text
        "--oem 3 "         # LSTM + legacy engine
        "-c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,+/-()%: "
    )
    pil_img = Image.fromarray(preprocessed)
    raw_text = pytesseract.image_to_string(pil_img, config=config)
    return raw_text


def parse_medicine_names(raw_text: str) -> list[dict]:
    """
    Extract medicine names and dosages from OCR raw text.
    Returns list of dicts with 'name' and 'dosage' keys.
    """
    results = []
    seen = set()

    lines = raw_text.split('\n')
    for line in lines:
        line = line.strip()
        if not line or len(line) < 3:
            continue

        # Find all medicine-like tokens on this line
        for match in MEDICINE_NAME_PATTERN.finditer(line):
            name = match.group(1).strip()
            dosage = (match.group(2) or "").strip()

            # Filter noise
            words_lower = name.lower().split()
            if any(w in NOISE_WORDS for w in words_lower):
                continue
            if len(name) < 4:
                continue

            key = name.lower()
            if key not in seen:
                seen.add(key)
                entry = {"name": name, "dosage": dosage, "raw_line": line}
                results.append(entry)

    # Also extract anything that looks like "Salt Xmg" patterns globally
    for match in DOSAGE_UNITS.finditer(raw_text):
        # Get surrounding context (10 chars before)
        start = max(0, match.start() - 25)
        context = raw_text[start:match.end()].strip()
        # Extract the word(s) before the number
        prefix = raw_text[start:match.start()].strip()
        words = re.findall(r'[A-Za-z]{4,}', prefix)
        for w in words[-2:]:  # last 2 words
            if w.lower() not in NOISE_WORDS and w.lower() not in seen:
                seen.add(w.lower())
                results.append({
                    "name": w,
                    "dosage": match.group(0).strip(),
                    "raw_line": context
                })

    return results


def run_ocr_pipeline(image_input) -> dict:
    """
    Full pipeline: preprocess → OCR → parse.
    Returns: { raw_text, medicines: [{name, dosage, raw_line}] }
    """
    try:
        preprocessed = preprocess_image(image_input)
        raw_text = extract_text(preprocessed)
        medicines = parse_medicine_names(raw_text)
        return {
            "success": True,
            "raw_text": raw_text,
            "medicines": medicines,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "raw_text": "",
            "medicines": [],
        }
