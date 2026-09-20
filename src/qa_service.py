"""QA and Document Comparison Service.

Uses Agnes AI (agnes-3.0-flash) or selected provider to:
- Answer questions with page citations from retrieved chunks.
- Perform comparative field diffs between two document file_ids.
- Compute Python-side set diffs of field names.
"""

from typing import Any, Dict, List, Set
import json

from src.agnes_client import chat_completion_with_retry
from src.config import AGNES_MODEL


def answer_question_with_page_citations(
    question: str,
    chunks: List[Dict[str, Any]],
    model: str = AGNES_MODEL,
    provider_name: str = "Agnes AI",
) -> str:
    """Answer a question from retrieved chunks with required page citations.

    Args:
        question: User question to answer from document evidence.
        chunks: Retrieved chunk dictionaries containing page and text fields.
        model: Agnes model identifier.
        provider_name: Configured provider display name.

    Returns:
        A grounded cited answer, or an explicit empty-retrieval message without
        calling Agnes when `chunks` is empty.

    Raises:
        AgnesClientError: If a non-empty grounded completion cannot be produced.
    """
    if not chunks:
        return "Retrieval returned empty. No relevant chunks found for this document in Qdrant."

    context_parts = []
    for i, c in enumerate(chunks, 1):
        page_num = c.get("page", c.get("page_number", 1))
        score = c.get("score", 0.0)
        text = c.get("text", "").strip()
        context_parts.append(f"--- Chunk {i} [Page {page_num}] (Relevance: {score:.2f}) ---\n{text}")

    context_str = "\n\n".join(context_parts)

    system_prompt = (
        "You are an accurate Document QA assistant. Answer the user's question using ONLY the provided excerpts.\n"
        "Do not assume or extrapolate facts not present in the excerpts.\n"
        "Rules:\n"
        "1. Every factual statement or data point MUST cite the source page in square brackets (e.g., '[Page 1]').\n"
        "2. If multiple pages support a statement, cite all relevant pages (e.g., '[Page 1, Page 2]').\n"
        "3. If the excerpts do not contain enough information to answer, state clearly that the provided context does not contain the answer.\n"
        "4. Be concise, direct, and factual."
    )

    user_prompt = (
        f"Document Context:\n{context_str}\n\n"
        f"User Question: {question}\n\n"
        "Provide your grounded answer with explicit page citations:"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    return chat_completion_with_retry(
        messages,
        model=model,
        provider_name=provider_name,
        temperature=0.1,
    )


def compute_field_set_diff(
    fields_a: Dict[str, Any],
    fields_b: Dict[str, Any],
) -> Dict[str, List[str]]:
    """Compute deterministic field-name set differences for two documents.

    Args:
        fields_a: First document's field-name-to-value mapping.
        fields_b: Second document's field-name-to-value mapping.

    Returns:
        Sorted common, first-only, and second-only field-name lists.
    """
    set_a: Set[str] = set(fields_a.keys())
    set_b: Set[str] = set(fields_b.keys())

    return {
        "common_fields": sorted(list(set_a & set_b)),
        "only_in_a": sorted(list(set_a - set_b)),
        "only_in_b": sorted(list(set_b - set_a)),
    }


def diff_document_fields(
    doc_a_name: str,
    fields_a: Dict[str, Any],
    doc_b_name: str,
    fields_b: Dict[str, Any],
    model: str = AGNES_MODEL,
    provider_name: str = "Agnes AI",
) -> str:
    """Request a prose comparison of two extracted-field mappings.

    Args:
        doc_a_name: Display name of the base document.
        fields_a: Base document's field-name-to-value mapping.
        doc_b_name: Display name of the comparison document.
        fields_b: Comparison document's field-name-to-value mapping.
        model: Agnes model identifier.
        provider_name: Configured provider display name.

    Returns:
        Markdown-oriented Agnes report limited to the supplied extracted fields.

    Raises:
        AgnesClientError: If the comparison completion cannot be produced.
    """
    str_a = json.dumps(fields_a, indent=2)
    str_b = json.dumps(fields_b, indent=2)

    system_prompt = (
        "You are an expert document and contract diff specialist.\n"
        "Compare the extracted fields of two documents. Diff the fields ONLY.\n"
        "Output:\n"
        "1. Summary of Field Changes: High-level overview of which key fields modified, added, or removed.\n"
        "2. Changed Fields Table: Output a Markdown table with columns:\n"
        "   | Field Name | Document A Value | Document B Value | Status (Modified / Added / Removed) |\n"
        "3. Material Impact: Note any significant value changes (e.g., payment amounts, deadlines, parties).\n"
        "Be exact and factual."
    )

    user_prompt = (
        f"=== Document A ({doc_a_name}) Fields ===\n{str_a}\n\n"
        f"=== Document B ({doc_b_name}) Fields ===\n{str_b}\n\n"
        "Generate the fields-only diff report:"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    return chat_completion_with_retry(
        messages,
        model=model,
        provider_name=provider_name,
        temperature=0.1,
    )
