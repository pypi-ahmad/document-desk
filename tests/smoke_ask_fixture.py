"""Smoke test for Ask functionality on the fixture PDF.

Indexes data/fixtures/sample.pdf into embedded Qdrant (path='data/qdrant', collection='documents')
with payload {file_id, page, text}, retrieves k chunks filtered by file_id,
and has Agnes AI answer only from chunks with explicit page citations.
Documents and handles Qdrant lock handling (one process only).
"""

import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.config import FIXTURES_DIR, QDRANT_PATH, QDRANT_COLLECTION, is_agnes_key_set
from src.extract import ensure_sample_pdf, extract_pages_pymupdf
from src.vector_store import get_qdrant_client, index_document_pages_or_text, search_document_chunks
from src.qa_service import answer_question_with_page_citations


def run_smoke_ask():
    print("=== Step 0: Check AGNESAI_API_KEY ===")
    if not is_agnes_key_set():
        raise RuntimeError(
            "AGNESAI_API_KEY is not set in the environment. "
            "Please configure AGNESAI_API_KEY in Windows user environment or .env."
        )
    print("[PASS] AGNESAI_API_KEY is configured.")

    print("\n=== Step 1: Ensure Fixture PDF ===")
    sample_pdf = FIXTURES_DIR / "sample.pdf"
    ensure_sample_pdf(sample_pdf)
    assert sample_pdf.exists(), f"Fixture PDF missing at {sample_pdf}"
    print(f"[PASS] Fixture PDF verified at {sample_pdf}")

    print("\n=== Step 2: Extract Pages with PyMuPDF ===")
    pages_info, _ = extract_pages_pymupdf(sample_pdf)
    print(f"Extracted {len(pages_info)} page(s) from fixture.")
    assert len(pages_info) > 0, "No pages extracted"

    print("\n=== Step 3: Index Chunks into Embedded Qdrant ===")
    file_id = "sample_fixture"
    filename = sample_pdf.name
    
    qdrant_client = None
    try:
        qdrant_client = get_qdrant_client(QDRANT_PATH)
        indexed_count = index_document_pages_or_text(
            client=qdrant_client,
            file_id=file_id,
            filename=filename,
            content=pages_info,
        )
        print(f"Indexed {indexed_count} chunk(s) into Qdrant collection '{QDRANT_COLLECTION}' with payload {{file_id, page, text}}.")
    except Exception as err:
        print(f"[WARN] Qdrant access encountered lock/error: {err}")
        print("Note: Embedded Qdrant requires single-process access. Ensure only one Streamlit/Python process accesses data/qdrant.")
        raise
    finally:
        if qdrant_client:
            qdrant_client.close()

    print("\n=== Step 4: Retrieve k Chunks Filtered by file_id ===")
    question = "What is the total amount due, and what are the payment terms?"
    qdrant_client = get_qdrant_client(QDRANT_PATH)
    try:
        chunks = search_document_chunks(
            client=qdrant_client,
            query=question,
            file_id=file_id,
            limit=4,
        )
        print(f"Retrieved {len(chunks)} chunks.")
        for i, c in enumerate(chunks, 1):
            p = c.get('page', c.get('page_number', 1))
            print(f" Chunk {i} (Page {p}, score={c.get('score', 0.0):.2f}): {c.get('text', '')[:60]}...")
    finally:
        qdrant_client.close()

    assert len(chunks) > 0, "Failed to retrieve chunks for query (retrieval empty)"

    print("\n=== Step 5: Answer Question with Agnes AI Page Citations ===")
    answer = answer_question_with_page_citations(question, chunks)
    print("\n--- Agnes AI Grounded Answer ---")
    print(answer)
    print("--------------------------------")

    assert "5,292" in answer or "5292" in answer or "5,292.00" in answer, "Answer missing expected total amount due"
    assert "Page" in answer, "Answer missing page citation"
    print("\n[PASS] Ask on fixture PDF succeeded with verified page citations!")
    print("\n=== ASK SMOKE CHECKS PASSED ===")
    return True


if __name__ == "__main__":
    success = run_smoke_ask()
    sys.exit(0 if success else 1)
