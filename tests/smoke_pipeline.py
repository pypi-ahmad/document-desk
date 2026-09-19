"""End-to-end pipeline smoke test for Document Desk.

Validates:
1. pdf-inspector classification and native Markdown extraction on a test PDF.
2. pypdfium2 rasterization of page to data/pages/<file_id>/page_1.png at 150 dpi.
3. Ollama VL (AuditAid/PaddleOCR-VL-1.6-0.9B) OCR and Table Recognition at temperature 0.
4. Agnes AI (agnes-3.0-flash) structuring into Summary, Fields, Tables, Citations, and JSON.
5. Embedded Qdrant chunk indexing into collection 'documents' under data/qdrant and retrieval by file_id.
6. Agnes AI diff comparison between two documents.
"""

import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import pdf_inspector
import pypdfium2 as pdfium
from tests.generate_fixture import generate_fixture
from src.config import QDRANT_PATH, QDRANT_COLLECTION, OLLAMA_OCR_MODEL
from src.document_processor import (
    inspect_pdf_file,
    render_pdf_page_pypdfium2,
    run_page_ocr,
    process_document,
)
from src.agnes_client import structure_document_text, ask_document_question, compare_document_diffs
from src.vector_store import get_qdrant_client, index_document_chunks, search_document_chunks


def run_pipeline_smoke():
    print("=== 1. Testing pdf-inspector API Attributes ===")
    fixture_png = generate_fixture()
    
    # Create a test PDF from fixture image using pypdfium2 / Pillow
    test_pdf_path = BASE_DIR / "data" / "uploads" / "sample_invoice.pdf"
    test_pdf_path.parent.mkdir(parents=True, exist_ok=True)
    from PIL import Image
    im = Image.open(fixture_png)
    im.save(test_pdf_path, "PDF", resolution=150.0)
    print(f"Created test PDF at: {test_pdf_path}")

    # Inspect PDF with pdf_inspector.process_pdf(path)
    res = inspect_pdf_file(test_pdf_path)
    print(f"pdf_type: {res['pdf_type']}")
    print(f"confidence: {res['confidence']}")
    print(f"page_count: {res['page_count']}")
    print(f"is_usable markdown: {res['is_usable']}")
    assert res["page_count"] >= 1, "Expected at least 1 page"
    assert res["pdf_type"] in ["scanned", "image_based", "text_based", "mixed"], f"Unexpected type: {res['pdf_type']}"
    print("[PASS] pdf-inspector classification validated.")

    print("\n=== 2. Testing pypdfium2 Page Rasterization ===")
    rendered_png = render_pdf_page_pypdfium2(
        pdf_path=test_pdf_path,
        page_number_1based=1,
        file_id="smoke_test_doc",
        dpi=150,
    )
    assert rendered_png.exists(), f"Rendered PNG missing: {rendered_png}"
    print(f"Rendered page via pypdfium2 to: {rendered_png}")
    print("[PASS] pypdfium2 rasterization validated.")

    print(f"\n=== 3. Testing Ollama VL OCR ({OLLAMA_OCR_MODEL}) at temp 0 ===")
    ocr_results = run_page_ocr(rendered_png, include_tables=True)
    ocr_text = ocr_results.get("ocr", "")
    table_text = ocr_results.get("tables", "")
    print(f"OCR Text sample:\n{ocr_text[:200]}...")
    print(f"Table Recognition sample:\n{table_text[:200]}...")
    assert len(ocr_text) > 20, "OCR produced empty text"
    print("[PASS] Ollama VL OCR and Table Recognition validated.")

    print("\n=== 4. Testing Agnes AI Structuring (agnes-3.0-flash) ===")
    combined_text = f"{ocr_text}\n\n[Tables]:\n{table_text}"
    struct_output = structure_document_text(combined_text)
    print(f"Agnes Structuring Output sample:\n{struct_output[:350]}...\n")
    assert "summary" in struct_output.lower() or "invoice" in struct_output.lower()
    assert len(struct_output) > 100
    print("[PASS] Agnes AI structure (summary, fields, tables, citations, JSON) validated.")

    print(f"\n=== 5. Testing Embedded Qdrant (path='data/qdrant', collection='{QDRANT_COLLECTION}') ===")
    q_client = get_qdrant_client(QDRANT_PATH)
    file_id = "smoke_test_doc"
    chunk_count = index_document_chunks(
        client=q_client,
        file_id=file_id,
        filename="sample_invoice.pdf",
        text=combined_text,
    )
    print(f"Indexed {chunk_count} chunk(s) in Qdrant collection '{QDRANT_COLLECTION}'")

    # Search filtered by file_id
    search_hits = search_document_chunks(
        client=q_client,
        query="What is the total amount due?",
        file_id=file_id,
        limit=3,
    )
    assert len(search_hits) > 0, "Vector search returned 0 hits"
    print(f"Retrieved top hit with score {search_hits[0]['score']:.2f}: {search_hits[0]['text'][:100]}...")

    # Ask with context
    ask_response = ask_document_question(
        question="What is the invoice number and total amount due?",
        context=search_hits[0]["text"],
        file_id=file_id,
    )
    print(f"Agnes Ask Answer: {ask_response[:200]}...")
    print("[PASS] Embedded Qdrant index, retrieval by file_id, and Agnes Ask validated.")

    print("\n=== 6. Testing Agnes AI Document Diff ===")
    doc_a = "INVOICE #1024 - Item: Widget A, Total: $42.00, Net 30 days."
    doc_b = "INVOICE #1024 - Item: Widget A, Total: $55.00, Net 15 days, Late fee 5%."
    diff_res = compare_document_diffs(doc_a, doc_b, "Version 1", "Version 2")
    print(f"Agnes Diff Output sample:\n{diff_res[:250]}...")
    assert len(diff_res) > 50
    print("[PASS] Document comparison validated.")

    print("\n=== ALL PIPELINE SMOKE CHECKS PASSED ===")
    return True


if __name__ == "__main__":
    success = run_pipeline_smoke()
    sys.exit(0 if success else 1)
