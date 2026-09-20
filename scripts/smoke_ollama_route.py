"""Smoke 2: Route-to-Ollama Vision-Language OCR test.

Requirements:
- Reads or produces data/cache/last_inspect.json where route is "ollama".
- If route is "ollama":
  - Renders one page with pypdfium2 (150-200 dpi PNG under data/pages/<file_id>/page-XXXX.png).
  - Runs Ollama model AuditAid/PaddleOCR-VL-1.6-0.9B with prompt "OCR:" and image attachment.
  - Verifies extracted text and saves data/cache/last_ocr.json.
"""

from pathlib import Path
import json
import sys

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import CACHE_DIR, FIXTURES_DIR, PAGES_DIR, OLLAMA_OCR_MODEL
from src.pdf_inspect import inspect_pdf
from src.render_pages import render_page
from src.ollama_ocr import check_ollama_status, run_ollama_ocr_page


def run_smoke_ollama_route() -> bool:
    """Force a fixture through the Ollama route and verify its OCR cache.

    Returns:
        True when the service, routing, rendering, OCR, and cache checks pass;
        otherwise False when Ollama or the required model is unavailable.

    Raises:
        AssertionError: If a routed page or OCR result fails validation.
    """
    print("=== Smoke 2: Route-to-Ollama Vision-Language OCR ===")

    # Check Ollama connectivity first
    is_online, has_model, status_msg, _ = check_ollama_status()
    if not is_online or not has_model:
        print(f"[ERROR] Ollama is not ready: {status_msg}")
        print(f"Action required: start Ollama Desktop on 11434, then run:\n  ollama pull {OLLAMA_OCR_MODEL}")
        return False
    print(f"[PASS] Ollama is online on 11434 and model '{OLLAMA_OCR_MODEL}' is pulled.")

    # We need a document that routes to 'ollama'
    # Check if last_inspect.json exists with route == 'ollama', otherwise inspect sample_page fixture or text.pdf with force_ocr=True
    cache_path = CACHE_DIR / "last_inspect.json"
    inspect_data = {}
    if cache_path.exists():
        try:
            inspect_data = json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    file_to_render = None
    if inspect_data.get("route") == "ollama" and Path(inspect_data.get("file_path", "")).exists():
        file_to_render = Path(inspect_data["file_path"])
        file_id = inspect_data.get("filename", file_to_render.stem)
    else:
        # Route a document to ollama
        text_pdf = FIXTURES_DIR / "text.pdf"
        sample_page = FIXTURES_DIR / "sample_page.png"

        target_doc = text_pdf if text_pdf.exists() else sample_page
        print(f"Inspecting '{target_doc.name}' with force_ocr=True to trigger 'ollama' route...")
        inspect_data = inspect_pdf(target_doc, force_ocr=True, save_cache=True)
        file_to_render = target_doc
        file_id = target_doc.stem

    print(f"last_inspect route: '{inspect_data.get('route')}' (pdf_type: {inspect_data.get('pdf_type')})")
    assert inspect_data.get("route") == "ollama", "Expected route to be 'ollama'"

    # Render page 1 using pypdfium2
    print(f"Rendering page 1 for '{file_id}' via pypdfium2...")
    if file_to_render.suffix.lower() == ".pdf":
        page_png = render_page(file_to_render, page_number_1based=1, file_id=file_id, dpi=150, route="ollama")
    else:
        from src.render_pages import render_all_pages
        pngs = render_all_pages(file_to_render, file_id=file_id, dpi=150, route="ollama")
        page_png = pngs[0] if pngs else None

    assert page_png and page_png.exists(), f"Rendered page image not found at {page_png}"
    print(f"[PASS] Rendered page image: {page_png} ({page_png.stat().st_size} bytes)")

    # Run Ollama VL OCR
    print(f"Calling Ollama model '{OLLAMA_OCR_MODEL}' with prompt 'OCR:'...")
    ocr_result = run_ollama_ocr_page(page_png, page=1, include_tables=False)

    print(f"OCR Result page: {ocr_result.get('page')}")
    print(f"Extracted Text: {ocr_result.get('text', '')[:150]}...")
    assert len(ocr_result.get("text", "").strip()) > 0, "Ollama OCR returned empty text"

    # Save data/cache/last_ocr.json
    cache_ocr_path = CACHE_DIR / "last_ocr.json"
    cache_ocr_path.write_text(json.dumps(ocr_result, indent=2), encoding="utf-8")
    print(f"[PASS] Successfully verified and saved {cache_ocr_path}")

    print("=== Smoke 2 PASSED ===")
    return True


if __name__ == "__main__":
    success = run_smoke_ollama_route()
    sys.exit(0 if success else 1)
