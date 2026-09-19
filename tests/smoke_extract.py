"""Smoke test for PyMuPDF page extraction and Agnes AI JSON structuring.

If data/fixtures/sample.pdf is missing, generates a short invoice-like PDF,
runs extract on it against agnes-3.0-flash, verifies hardened JSON parsing,
validates schema {title, doc_type, fields:[{name,value,page}], tables:[], summary, citations:[{claim,page}]},
and verifies data/cache/last_extract.json.
"""

import json
import sys
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.config import CACHE_DIR, FIXTURES_DIR, is_agnes_key_set
from src.extract import ensure_sample_pdf, extract_pages_pymupdf, extract_with_agnes


def run_smoke():
    print("=== Step 0: Check AGNESAI_API_KEY ===")
    if not is_agnes_key_set():
        raise RuntimeError(
            "AGNESAI_API_KEY is not set in the environment. "
            "Please configure AGNESAI_API_KEY in Windows user environment or .env."
        )
    print("[PASS] AGNESAI_API_KEY is configured.")

    print("\n=== Step 1: Ensure Sample PDF in data/fixtures/sample.pdf ===")
    sample_pdf = FIXTURES_DIR / "sample.pdf"
    ensure_sample_pdf(sample_pdf)
    assert sample_pdf.exists(), f"Failed to find or generate {sample_pdf}"
    print(f"[PASS] Fixture PDF verified at {sample_pdf} ({sample_pdf.stat().st_size} bytes)")

    print("\n=== Step 2: Extract Pages with PyMuPDF ===")
    pages_info, concat_text = extract_pages_pymupdf(sample_pdf)
    print(f"Pages detected: {len(pages_info)}")
    print(f"Concatenated text preview:\n{concat_text[:250]}...\n")
    assert len(concat_text) > 50, "Text extraction returned insufficient content"
    print("[PASS] PyMuPDF page text extraction successful.")

    print("\n=== Step 3: Run Extract against agnes-3.0-flash ===")
    result = extract_with_agnes(pages_info, save_cache=True)
    
    print(f"Document Title: {result.get('title')}")
    print(f"Doc Type: {result.get('doc_type')}")
    print(f"Fields count: {len(result.get('fields', []))}")
    print(f"Tables count: {len(result.get('tables', []))}")
    print(f"Summary: {result.get('summary')[:120]}...")
    print(f"Citations count: {len(result.get('citations', []))}")

    # Schema assertions
    assert "title" in result and isinstance(result["title"], str), "Missing 'title' in result"
    assert "doc_type" in result and isinstance(result["doc_type"], str), "Missing 'doc_type' in result"
    assert "fields" in result and isinstance(result["fields"], list), "Missing 'fields' in result"
    assert "tables" in result and isinstance(result["tables"], list), "Missing 'tables' in result"
    assert "summary" in result and isinstance(result["summary"], str), "Missing 'summary' in result"
    assert "citations" in result and isinstance(result["citations"], list), "Missing 'citations' in result"
    assert len(result["fields"]) > 0, "Expected at least 1 extracted field"

    # Validate fields structure: [{name, value, page}]
    for f in result["fields"]:
        assert "name" in f and "value" in f and "page" in f, f"Field missing required keys: {f}"
        print(f"  - Field: {f['name']} = {f['value']} (Page {f['page']})")

    # Validate citations structure: [{claim, page}]
    for c in result["citations"]:
        assert "claim" in c and "page" in c, f"Citation missing required keys: {c}"
        print(f"  - Citation: [Page {c['page']}] {c['claim']}")

    print("[PASS] Agnes AI returned valid JSON matching required schema.")

    print("\n=== Step 4: Verify data/cache/last_extract.json ===")
    cache_path = CACHE_DIR / "last_extract.json"
    assert cache_path.exists(), f"Cache file does not exist: {cache_path}"
    cached_data = json.loads(cache_path.read_text(encoding="utf-8"))
    assert cached_data.get("title") == result.get("title"), "Cache mismatch"
    print(f"[PASS] Cached extraction verified at {cache_path} ({cache_path.stat().st_size} bytes)")

    print("\n=== ALL SMOKE CHECKS PASSED ===")
    return True


if __name__ == "__main__":
    success = run_smoke()
    sys.exit(0 if success else 1)
