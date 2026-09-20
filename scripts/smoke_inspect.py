"""Smoke 1: Text PDF Inspection via pdf-inspector.

Requirements:
- Tiny checked-in text PDF at data/fixtures/text.pdf.
- pdf_inspector.process_pdf must return text_based and markdown containing a known string ("AGREEMENT").
- Save data/cache/last_inspect.json.
- No Ollama required for this smoke.
"""

from pathlib import Path
import json
import sys

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import CACHE_DIR, FIXTURES_DIR
from src.pdf_inspect import inspect_pdf


def run_smoke_inspect() -> bool:
    """Inspect the checked-in text-PDF fixture and verify its native route.

    Returns:
        True after the expected inspection cache and fixture text are verified.

    Raises:
        AssertionError: If inspection or the saved cache violates the fixture
            contract.
    """
    print("=== Smoke 1: Text PDF Inspection via pdf-inspector ===")
    text_pdf = FIXTURES_DIR / "text.pdf"

    if not text_pdf.exists():
        sample_pdf = FIXTURES_DIR / "sample.pdf"
        assert sample_pdf.exists(), f"Source fixture missing at {sample_pdf}"
        import shutil
        shutil.copyfile(sample_pdf, text_pdf)

    print(f"Testing text PDF at: {text_pdf}")
    result = inspect_pdf(text_pdf, force_ocr=False, save_cache=True)

    print(f"pdf_type: {result['pdf_type']}")
    print(f"confidence: {result['confidence']}")
    print(f"page_count: {result['page_count']}")
    print(f"route: {result['route']}")
    print(f"markdown preview: {result['markdown'][:120]}...")

    # Assertions
    assert result["pdf_type"] == "text_based", f"Expected 'text_based', got '{result['pdf_type']}'"
    assert result["path"] == str(text_pdf.resolve())
    assert "AGREEMENT" in result["markdown"], "Known string 'AGREEMENT' not found in extracted markdown"
    assert result["route"] == "native", f"Expected route 'native', got '{result['route']}'"

    # Verify data/cache/last_inspect.json
    cache_path = CACHE_DIR / "last_inspect.json"
    assert cache_path.exists() and cache_path.stat().st_size > 0, "last_inspect.json not written"

    saved_data = json.loads(cache_path.read_text(encoding="utf-8"))
    assert saved_data["pdf_type"] == "text_based"
    assert saved_data["route"] == "native"
    assert "AGREEMENT" in saved_data["markdown"]
    print(f"[PASS] Successfully verified and saved {cache_path} ({cache_path.stat().st_size} bytes)")
    print("=== Smoke 1 PASSED (No Ollama required) ===")
    return True


if __name__ == "__main__":
    success = run_smoke_inspect()
    sys.exit(0 if success else 1)
