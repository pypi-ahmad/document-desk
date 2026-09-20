"""Smoke test for local Ollama OCR with AuditAid/PaddleOCR-VL-1.6-0.9B.

Uses or creates data/fixtures/sample_page.png, calls Ollama, and writes
data/cache/last_ocr.json. If the model is missing or offline, prints the exact
pull command and fails clearly.
"""

import json
from pathlib import Path
import sys

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from PIL import Image, ImageDraw
from src.config import CACHE_DIR, FIXTURES_DIR, OLLAMA_OCR_MODEL
from src.ollama_ocr import check_ollama_status, run_ollama_ocr_page


def ensure_fixture_page() -> Path:
    """Ensure data/fixtures/sample_page.png exists with required text."""
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    fixture_path = FIXTURES_DIR / "sample_page.png"
    if fixture_path.exists():
        return fixture_path

    img = Image.new("RGB", (800, 600), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    text = "Invoice 1042 Total 26.00 Line A 10.00 Line B 16.00"
    draw.text((50, 50), text, fill=(0, 0, 0))
    img.save(fixture_path, format="PNG")
    print(f"Created fixture at: {fixture_path}")
    return fixture_path


def run_smoke_ocr() -> bool:
    print("=== Step 1: Ensure Fixture Page ===")
    fixture_path = ensure_fixture_page()
    assert fixture_path.exists(), f"Fixture missing: {fixture_path}"
    print(f"[PASS] Fixture verified at: {fixture_path}")

    print("\n=== Step 2: Check Ollama & Model Status ===")
    is_online, has_model, status_msg, models = check_ollama_status()
    if not is_online:
        print(f"[FAIL] Ollama is not running: {status_msg}")
        print("Please run:")
        print(f"  ollama pull {OLLAMA_OCR_MODEL}")
        return False

    if not has_model:
        print(f"[FAIL] Model '{OLLAMA_OCR_MODEL}' is not available in Ollama.")
        print(f"Available models: {models}")
        print("Please pull the model using:")
        print(f"  ollama pull {OLLAMA_OCR_MODEL}")
        return False

    print(f"[PASS] Ollama is online with model: {OLLAMA_OCR_MODEL}")

    print("\n=== Step 3: Run Ollama OCR on Fixture Page ===")
    try:
        ocr_result = run_ollama_ocr_page(
            image_input=fixture_path,
            page=1,
            include_tables=True,
            timeout=60.0,
        )
    except Exception as e:
        print(f"[FAIL] Ollama OCR call failed: {e}")
        print("Please run:")
        print(f"  ollama pull {OLLAMA_OCR_MODEL}")
        return False

    print("--- OCR Output (Pass 1 - OCR:) ---")
    print(ocr_result.get("text", ""))
    print("\n--- Table Recognition Output (Pass 2 - Table Recognition:) ---")
    print(ocr_result.get("table_text", ""))

    print("\n=== Step 4: Write data/cache/last_ocr.json ===")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / "last_ocr.json"
    cache_file.write_text(json.dumps(ocr_result, indent=2), encoding="utf-8")
    assert cache_file.exists() and cache_file.stat().st_size > 0, "last_ocr.json was not created"
    print(f"[PASS] Successfully wrote {cache_file} ({cache_file.stat().st_size} bytes)")

    print("\n=== OCR SMOKE TEST PASSED ===")
    return True


if __name__ == "__main__":
    success = run_smoke_ocr()
    sys.exit(0 if success else 1)
