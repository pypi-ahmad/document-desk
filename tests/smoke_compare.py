"""Smoke test for field-level document comparison.

Verifies:
1. Python-side set difference of field names.
2. Agnes AI field-level comparison report generation with Changed Fields Table.
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.config import is_agnes_key_set, AGNES_MODEL
from src.qa_service import compute_field_set_diff, diff_document_fields


def run_smoke():
    print("=== Step 0: Check AGNESAI_API_KEY ===")
    if not is_agnes_key_set():
        raise RuntimeError("AGNESAI_API_KEY is not configured.")
    print("[PASS] AGNESAI_API_KEY is configured.")

    print("\n=== Step 1: Compute Python Field Name Set Diff ===")
    fields_a = {
        "Document ID": "INV-2026-9042",
        "Total Amount Due": "$5,292.00",
        "Payment Terms": "Net 30 days",
        "Legacy Clause": "Standard terms apply",
    }
    fields_b = {
        "Document ID": "INV-2026-9042-REV2",
        "Total Amount Due": "$6,400.00",
        "Payment Terms": "Net 15 days",
        "New Compliance Requirement": "ISO 27001",
    }

    diff = compute_field_set_diff(fields_a, fields_b)
    print(f"Common fields: {diff['common_fields']}")
    print(f"Only in A: {diff['only_in_a']}")
    print(f"Only in B: {diff['only_in_b']}")

    assert "Document ID" in diff["common_fields"]
    assert "Legacy Clause" in diff["only_in_a"]
    assert "New Compliance Requirement" in diff["only_in_b"]
    print("[PASS] Python-side field set difference computed accurately.")

    print("\n=== Step 2: Request Field-Level Diff from Agnes AI ===")
    report = diff_document_fields(
        doc_a_name="Invoice_v1.pdf",
        fields_a=fields_a,
        doc_b_name="Invoice_v2.pdf",
        fields_b=fields_b,
        model=AGNES_MODEL,
        provider_name="Agnes AI",
    )

    print("\n--- Agnes AI Comparison Report ---")
    print(report[:400] + "...\n")

    assert len(report) > 50, "Comparison report was unexpectedly empty"
    print("[PASS] Agnes AI field-level comparison report generated successfully.")

    print("\n=== ALL COMPARE SMOKE CHECKS PASSED ===")
    return True


if __name__ == "__main__":
    success = run_smoke()
    sys.exit(0 if success else 1)
