"""Smoke test for OCR on fixture page followed by Agnes AI structured extraction."""

import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from tests.generate_fixture import generate_fixture
from src.document_processor import run_page_ocr
from src.agnes_client import structure_document_text

def run_test():
    """Run live local OCR followed by Agnes structuring on an invoice fixture.

    Returns:
        True when the OCR and Agnes output assertions pass.

    Raises:
        AssertionError: If expected OCR or structuring output is absent.
        Exception: If required local or Agnes services cannot complete a request.
    """
    print("=== Step 1: Generate Test Fixture Page ===")
    fixture_path = generate_fixture()
    assert fixture_path.exists(), "Fixture image was not created"

    print("\n=== Step 2: Smoke OCR with PaddleOCR-VL (AuditAid/PaddleOCR-VL-1.6-0.9B) ===")
    dual_result = run_page_ocr(fixture_path, include_tables=True)
    ocr_text = dual_result.get("ocr", "")
    table_text = dual_result.get("tables", "")

    print(f"--- OCR Output (Pass 1 - OCR:) ---\n{ocr_text}\n")
    print(f"--- Table Recognition Output (Pass 2 - Table Recognition:) ---\n{table_text}\n")

    assert "INV-2026-9042" in ocr_text or "INVOICE" in ocr_text, "OCR failed to detect invoice number"
    assert "999" in ocr_text or "TOTAL" in ocr_text, "OCR failed to detect totals"
    print("[PASS] PaddleOCR-VL fixture OCR succeeded.")

    print("\n=== Step 3: Agnes AI Extraction (agnes-3.0-flash) ===")
    combined_content = f"{ocr_text}\n\nTables:\n{table_text}"
    structured_output = structure_document_text(combined_content, model="agnes-3.0-flash")

    print(f"--- Agnes AI Structured Output ---\n{structured_output}\n")

    assert len(structured_output) > 50, "Agnes extraction returned empty or unexpectedly short response"
    print("[PASS] Agnes AI structured extraction succeeded.")

    print("\n=== All Smoke Checks Succeeded ===")
    return True

if __name__ == "__main__":
    success = run_test()
    sys.exit(0 if success else 1)
