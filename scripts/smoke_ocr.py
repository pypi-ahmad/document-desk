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

from PIL import Image, ImageDraw, ImageFont
from src.config import CACHE_DIR, FIXTURES_DIR, OLLAMA_OCR_MODEL
from src.ollama_ocr import (
    OLLAMA_SETUP_MESSAGE,
    check_ollama_status,
    run_ollama_ocr_page,
)
from src.render_pages import render_all_pages


def ensure_fixture_page() -> Path:
    """Create the readable OCR fixture image.

    Returns:
        Path to `data/fixtures/sample_page.png` containing the required invoice
        text.
    """
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    fixture_path = FIXTURES_DIR / "sample_page.png"
    img = Image.new("RGB", (800, 600), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 34)
    except OSError:
        font = ImageFont.load_default()
    lines = ["Invoice 1042", "Line A 10.00", "Line B 16.00", "Total 26.00"]
    for index, line in enumerate(lines):
        draw.text((60, 60 + index * 70), line, fill=(0, 0, 0), font=font)
    img.save(fixture_path, format="PNG")
    print(f"Created fixture at: {fixture_path}")
    return fixture_path


def run_smoke_ocr() -> bool:
    """Run Ollama OCR against the generated fixture and save its cache.

    Returns:
        True when Ollama is ready, OCR returns text, and `last_ocr.json` is
        written; otherwise False for an unavailable service or model.

    Raises:
        AssertionError: If rendering, OCR output, or cache assertions fail.
    """
    print("=== Step 1: Ensure Fixture Page ===")
    fixture_path = ensure_fixture_page()
    assert fixture_path.exists(), f"Fixture missing: {fixture_path}"
    print(f"[PASS] Fixture verified at: {fixture_path}")

    rendered_pages = render_all_pages(
        fixture_path,
        file_id="sample_page",
        dpi=150,
        route="ollama",
    )
    assert len(rendered_pages) == 1
    assert rendered_pages[0].name == "page-0001.png"
    assert rendered_pages[0].suffix.lower() == ".png"
    ocr_input = rendered_pages[0]

    print("\n=== Step 2: Check Ollama & Model Status ===")
    is_online, has_model, _status_msg, models = check_ollama_status()
    if not is_online:
        print(f"[FAIL] {OLLAMA_SETUP_MESSAGE}")
        return False

    if not has_model:
        print(f"[FAIL] Model '{OLLAMA_OCR_MODEL}' is not available in Ollama.")
        print(f"Available models: {models}")
        print(OLLAMA_SETUP_MESSAGE)
        return False

    print(f"[PASS] Ollama is online with model: {OLLAMA_OCR_MODEL}")

    print("\n=== Step 3: Run Ollama OCR on Fixture Page ===")
    try:
        ocr_result = run_ollama_ocr_page(
            image_input=ocr_input,
            page=1,
            include_tables=True,
            timeout=60.0,
        )
    except Exception as e:
        print(f"[FAIL] Ollama OCR call failed: {e}")
        print(OLLAMA_SETUP_MESSAGE)
        return False

    required_keys = {"page", "text", "table_text", "raw"}
    assert required_keys <= ocr_result.keys(), "OCR result is missing required keys"
    assert ocr_result["text"].strip(), "OCR result text is empty"

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
