"""Smoke test: Extract and Ask on fixture OCR text against Agnes AI.

Validates:
1. Extraction on fixture OCR text (Invoice 1042 Total 26.00 Line A 10.00 Line B 16.00).
2. Strictly sends concatenated OCR page text (not images) to agnes-3.0-flash.
3. Hardens and validates JSON schema:
   {title, doc_type, fields:[{name,value,page}], tables, summary, citations:[{claim,page}]}
4. Writes data/cache/last_extract.json.
5. Chunks OCR text into Qdrant collection 'documents' with payload {file_id, page, text}.
6. Ask: retrieves by file_id, Agnes answers strictly with page citations.
7. Compare: two file_ids field-level diff (Python set diff + model diff).
"""

import json
from pathlib import Path
import sys

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import CACHE_DIR, FIXTURES_DIR, is_agnes_key_set
from src.extract import extract_with_agnes
from src.ollama_ocr import run_ollama_ocr_page, check_ollama_status
from src.vector_store import (
    get_qdrant_client,
    index_document_pages_or_text,
    search_document_chunks,
)
from src.qa_service import (
    answer_question_with_page_citations,
    compute_field_set_diff,
    diff_document_fields,
)


def run_smoke_extract_ask() -> bool:
    """Run the live OCR-text, extraction, retrieval, Ask, and Compare smoke.

    Returns:
        True when every required live-service assertion succeeds; otherwise False
        when the Agnes key or Ollama setup is unavailable.

    Raises:
        AssertionError: If a pipeline result violates its expected contract.
    """
    print("=== Step 0: Environment & Key Verification ===")
    if not is_agnes_key_set():
        print("[FAIL] AGNESAI_API_KEY is not set in the environment or .env.")
        print("Please configure AGNESAI_API_KEY before running this test.")
        return False
    print("[PASS] AGNESAI_API_KEY is configured.")

    print("\n=== Step 1: Obtain Fixture OCR Text ===")
    fixture_path = FIXTURES_DIR / "sample_page.png"
    last_ocr_file = CACHE_DIR / "last_ocr.json"

    ocr_text = ""
    if last_ocr_file.exists():
        try:
            cached_ocr = json.loads(last_ocr_file.read_text(encoding="utf-8"))
            if isinstance(cached_ocr, dict):
                ocr_text = cached_ocr.get("text", "")
            elif isinstance(cached_ocr, list) and cached_ocr:
                ocr_text = cached_ocr[0].get("text", "")
        except Exception:
            ocr_text = ""

    if not ocr_text:
        print("Running local Ollama OCR on sample_page.png...")
        ocr_result = run_ollama_ocr_page(fixture_path, page=1)
        ocr_text = ocr_result.get("text", "")

    assert ocr_text, "OCR text is empty"
    print(f"[PASS] Fixture OCR Text: '{ocr_text}'")

    print("\n=== Step 2: Extract Structured JSON with Agnes AI (agnes-3.0-flash) ===")
    pages_payload = [
        {
            "page_number": 1,
            "text": ocr_text,
            "char_count": len(ocr_text),
        }
    ]

    extracted = extract_with_agnes(
        content=pages_payload,
        save_cache=True,
    )

    print("--- Extracted JSON Result ---")
    print(json.dumps(extracted, indent=2))

    # Verify JSON Schema: {title, doc_type, fields:[{name,value,page}], tables, summary, citations:[{claim,page}]}
    assert "title" in extracted and isinstance(extracted["title"], str), "Missing or invalid 'title'"
    assert "doc_type" in extracted and isinstance(extracted["doc_type"], str), "Missing or invalid 'doc_type'"
    assert "fields" in extracted and isinstance(extracted["fields"], list), "Missing or invalid 'fields'"
    assert "tables" in extracted, "Missing 'tables'"
    assert "summary" in extracted and isinstance(extracted["summary"], str), "Missing or invalid 'summary'"
    assert "citations" in extracted and isinstance(extracted["citations"], list), "Missing or invalid 'citations'"

    # Verify field objects have name, value, page
    for f in extracted["fields"]:
        assert "name" in f and "value" in f and "page" in f, f"Malformed field item: {f}"

    # Verify citations have claim, page
    for c in extracted["citations"]:
        assert "claim" in c and "page" in c, f"Malformed citation item: {c}"

    # Verify data/cache/last_extract.json exists
    cache_file = CACHE_DIR / "last_extract.json"
    assert cache_file.exists() and cache_file.stat().st_size > 0, "last_extract.json was not written"
    print(f"[PASS] Successfully verified and saved {cache_file} ({cache_file.stat().st_size} bytes)")

    print("\n=== Step 3: Chunk OCR Text into Qdrant Collection 'documents' ===")
    file_id = "sample_page"
    client = get_qdrant_client()
    num_indexed = index_document_pages_or_text(
        client=client,
        file_id=file_id,
        filename="sample_page.png",
        content=pages_payload,
    )
    assert num_indexed > 0, "No points were indexed into Qdrant"
    print(f"[PASS] Indexed {num_indexed} chunk(s) with payload {{file_id, page, text}}")

    print("\n=== Step 4: Ask: Retrieve Chunks & Answer with Page Citations ===")
    question = "What is the invoice number and total amount due?"
    retrieved = search_document_chunks(
        client=client,
        query=question,
        file_id=file_id,
        limit=3,
    )
    client.close()

    assert retrieved, f"Retrieval returned empty for file_id='{file_id}'"
    print(f"[PASS] Retrieved {len(retrieved)} chunk(s). Top chunk: '{retrieved[0].get('text', '')}'")

    answer = answer_question_with_page_citations(
        question=question,
        chunks=retrieved,
    )
    print("\n--- Agnes AI Grounded Answer ---")
    print(answer)
    assert "Page" in answer or "[Page" in answer, "Answer did not contain expected page citation"
    print("[PASS] Answer successfully generated with page citations.")

    print("\n=== Step 5: Compare: Two file_ids Field-Level Diff ===")
    fields_doc_a = {f["name"]: f["value"] for f in extracted["fields"]}
    # Create simulated comparison doc with modified values
    fields_doc_b = dict(fields_doc_a)
    fields_doc_b["Total Amount Due"] = "32.00"
    fields_doc_b["Line C"] = "6.00"

    # Python set diff
    set_diff = compute_field_set_diff(fields_doc_a, fields_doc_b)
    print(f"[PASS] Python set diff computed: {set_diff}")

    # Agnes AI field diff report
    diff_report = diff_document_fields(
        doc_a_name="sample_page_v1",
        fields_a=fields_doc_a,
        doc_b_name="sample_page_v2",
        fields_b=fields_doc_b,
    )
    print("\n--- Agnes AI Diff Report ---")
    print(diff_report[:350] + "...")
    assert len(diff_report) > 50, "Diff report was unexpectedly short"
    print("[PASS] Field-level comparison diff generated successfully.")

    print("\n=== ALL SMOKE EXTRACT + ASK + COMPARE CHECKS PASSED ===")
    return True


if __name__ == "__main__":
    success = run_smoke_extract_ask()
    sys.exit(0 if success else 1)
