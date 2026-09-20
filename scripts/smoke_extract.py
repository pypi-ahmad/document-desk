"""Smoke extraction, Qdrant indexing, and grounded Ask with cached page text."""

import json
import sys
from pathlib import Path

from qdrant_client.http import models

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import CACHE_DIR, is_agnes_key_set
from src.extract import extract_with_agnes, parse_and_harden_json
from src.qa_service import answer_question_with_page_citations
from src.store import (
    get_qdrant_client,
    index_document_pages_or_text,
    search_document_chunks,
)


def load_cached_pages() -> list[dict]:
    """Load cached page text without passing local image paths to Agnes.

    Returns:
        Non-empty page records with `page` and `text` keys.

    Raises:
        RuntimeError: If neither supported cache contains usable page text.
    """
    ocr_path = CACHE_DIR / "last_ocr.json"
    if ocr_path.exists():
        cached = json.loads(ocr_path.read_text(encoding="utf-8"))
        items = cached if isinstance(cached, list) else [cached]
        pages = [
            {
                "page": item.get("page", index),
                "text": item.get("combined_text", "") or item.get("text", ""),
            }
            for index, item in enumerate(items, 1)
            if isinstance(item, dict)
            and (item.get("combined_text", "") or item.get("text", "")).strip()
        ]
        if pages:
            return pages

    inspect_path = CACHE_DIR / "last_inspect.md"
    if inspect_path.exists() and inspect_path.read_text(encoding="utf-8").strip():
        return [{"page": 1, "text": inspect_path.read_text(encoding="utf-8")}]

    raise RuntimeError("No text found in data/cache/last_ocr.json or last_inspect.md")


def run_smoke() -> None:
    """Run the live Agnes extraction, Qdrant, and grounded-Ask smoke.

    Raises:
        RuntimeError: If `AGNESAI_API_KEY` or usable cached text is unavailable.
        AssertionError: If schema, cache, indexing, retrieval, or citation checks
            fail.
    """
    if not is_agnes_key_set():
        raise RuntimeError("AGNESAI_API_KEY is unavailable in the current process")

    parser_probe = 'prefix {"title":"first"} suffix {"title":"second"}'
    assert parse_and_harden_json(parser_probe)["title"] == "first"

    pages = load_cached_pages()
    extracted = extract_with_agnes(pages, save_cache=False)
    expected_keys = {"title", "doc_type", "fields", "tables", "summary", "citations"}
    assert set(extracted) == expected_keys

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    extract_path = CACHE_DIR / "last_extract.json"
    extract_path.write_text(json.dumps(extracted, indent=2), encoding="utf-8")

    file_id = "smoke_cached_text"
    client = get_qdrant_client()
    try:
        indexed = index_document_pages_or_text(
            client=client,
            file_id=file_id,
            content=pages,
        )
        assert indexed > 0
        stored, _ = client.scroll(
            collection_name="documents",
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="file_id",
                        match=models.MatchValue(value=file_id),
                    )
                ]
            ),
            limit=1,
            with_payload=True,
            with_vectors=False,
        )
        assert stored and set(stored[0].payload or {}) == {"file_id", "page", "text"}

        question = "What is the invoice number and total?"
        chunks = search_document_chunks(client, question, file_id=file_id, limit=3)
    finally:
        client.close()

    assert chunks
    answer = answer_question_with_page_citations(question, chunks)
    assert "Page" in answer
    ask_path = CACHE_DIR / "last_ask.json"
    ask_path.write_text(
        json.dumps(
            {
                "file_id": file_id,
                "question": question,
                "answer": answer,
                "chunks": chunks,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    assert extract_path.exists() and ask_path.exists()
    print(f"PASS: {extract_path}")
    print(f"PASS: {ask_path}")


if __name__ == "__main__":
    run_smoke()
