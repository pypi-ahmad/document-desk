"""Backward-compatible imports for the canonical Qdrant store module."""

from src.store import (
    get_qdrant_client,
    index_document_chunks,
    index_document_pages_or_text,
    init_collection,
    search_document_chunks,
    split_text_into_chunks,
)

__all__ = [
    "get_qdrant_client",
    "index_document_chunks",
    "index_document_pages_or_text",
    "init_collection",
    "search_document_chunks",
    "split_text_into_chunks",
]
