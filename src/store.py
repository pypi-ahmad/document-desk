"""Embedded Qdrant storage for page-text chunks."""

import hashlib
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models

from src.config import QDRANT_COLLECTION, QDRANT_PATH


def get_qdrant_client(storage_path: str = QDRANT_PATH) -> QdrantClient:
    """Open the embedded Qdrant database for one local process.

    Args:
        storage_path: Local Qdrant data directory.

    Returns:
        Embedded Qdrant client. Callers must close it after use.

    Raises:
        Exception: If Qdrant cannot open the local storage path.
    """
    path = Path(storage_path)
    path.mkdir(parents=True, exist_ok=True)
    return QdrantClient(path=str(path))


def init_collection(
    client: QdrantClient,
    collection_name: str = QDRANT_COLLECTION,
    vector_size: int = 256,
) -> None:
    """Create the vector collection when it is absent.

    Args:
        client: Open embedded Qdrant client.
        collection_name: Target collection name.
        vector_size: Deterministic local embedding dimension.

    Raises:
        Exception: If Qdrant cannot inspect or create the collection.

    Returns:
        None. The collection is created only when absent.
    """
    names = {item.name for item in client.get_collections().collections}
    if collection_name not in names:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE,
            ),
        )


def _embed(text: str, vector_size: int = 256) -> list[float]:
    """Create a deterministic local lexical vector without an external model."""
    vector = [0.0] * vector_size
    for word in text.lower().split():
        index = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16) % vector_size
        vector[index] += 1.0
    norm = sum(value * value for value in vector) ** 0.5
    return [value / norm for value in vector] if norm else vector


def split_text_into_chunks(
    text: str,
    chunk_size: int = 500,
    overlap: int = 80,
) -> list[str]:
    """Split one page of text into overlapping retrieval chunks.

    Args:
        text: Source page text.
        chunk_size: Target maximum character count per chunk.
        overlap: Trailing character count repeated into the next chunk.

    Returns:
        Non-empty chunks in source order; empty input yields an empty list.
    """
    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if current and len(current) + len(paragraph) > chunk_size:
            chunks.append(current.strip())
            current = f"{current[-overlap:]}\n\n{paragraph}"
        else:
            current = f"{current}\n\n{paragraph}".strip()
    if current:
        chunks.append(current.strip())
    return chunks


def index_document_pages_or_text(
    client: QdrantClient,
    file_id: str,
    content: str | list[dict[str, Any]],
    filename: str = "",
    collection_name: str = QDRANT_COLLECTION,
    vector_size: int = 256,
) -> int:
    """Replace one document's chunks using the canonical payload contract.

    Args:
        client: Open embedded Qdrant client.
        file_id: Document identifier used for replacement and retrieval filters.
        content: Plain text or page records containing page/text fields.
        filename: Compatibility argument; it is intentionally not persisted.
        collection_name: Target embedded collection.
        vector_size: Deterministic local embedding dimension.

    Returns:
        Number of chunks upserted with `{file_id, page, text}` payloads.

    Raises:
        Exception: If collection replacement or point upsert fails.
    """
    del filename  # Kept only for compatibility with existing callers.
    init_collection(client, collection_name, vector_size)
    client.delete(
        collection_name=collection_name,
        points_selector=models.Filter(
            must=[
                models.FieldCondition(
                    key="file_id",
                    match=models.MatchValue(value=file_id),
                )
            ]
        ),
    )

    pages = content if isinstance(content, list) else [{"page": 1, "text": content}]
    points: list[models.PointStruct] = []
    chunk_index = 0
    for fallback_page, page_data in enumerate(pages, 1):
        page = page_data.get("page", page_data.get("page_number", fallback_page))
        text = str(page_data.get("text", "")).strip()
        for chunk in split_text_into_chunks(text):
            digest = hashlib.sha256(
                f"{file_id}:{page}:{chunk_index}:{chunk}".encode()
            ).hexdigest()
            points.append(
                models.PointStruct(
                    id=int(digest[:15], 16),
                    vector=_embed(chunk, vector_size),
                    payload={"file_id": file_id, "page": page, "text": chunk},
                )
            )
            chunk_index += 1

    if points:
        client.upsert(collection_name=collection_name, points=points)
    return len(points)


def search_document_chunks(
    client: QdrantClient,
    query: str,
    file_id: str | None = None,
    limit: int = 5,
    collection_name: str = QDRANT_COLLECTION,
    vector_size: int = 256,
) -> list[dict[str, Any]]:
    """Retrieve the most similar local chunks, optionally for one file.

    Args:
        client: Open embedded Qdrant client.
        query: User question or retrieval text.
        file_id: Exact document filter, or None for all indexed documents.
        limit: Maximum number of chunks to return.
        collection_name: Target embedded collection.
        vector_size: Deterministic local embedding dimension.

    Returns:
        Ranked chunk dictionaries containing score, file ID, page, and text.

    Raises:
        Exception: If Qdrant cannot query the collection.
    """
    init_collection(client, collection_name, vector_size)
    query_filter = None
    if file_id and file_id != "All Documents":
        query_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="file_id",
                    match=models.MatchValue(value=file_id),
                )
            ]
        )
    response = client.query_points(
        collection_name=collection_name,
        query=_embed(query, vector_size),
        query_filter=query_filter,
        limit=limit,
    )
    return [
        {
            "score": hit.score,
            "file_id": hit.payload.get("file_id", ""),
            "page": hit.payload.get("page", 1),
            "text": hit.payload.get("text", ""),
        }
        for hit in response.points
        if hit.payload
    ]


def index_document_chunks(
    client: QdrantClient,
    file_id: str,
    filename: str,
    text: str | list[dict[str, Any]],
    collection_name: str = QDRANT_COLLECTION,
    vector_size: int = 256,
) -> int:
    """Index text through the backwards-compatible storage entry point.

    Args:
        client: Open embedded Qdrant client.
        file_id: Document identifier for replacement and retrieval filtering.
        filename: Compatibility filename argument that is not persisted.
        text: Plain text or page records to chunk and index.
        collection_name: Target embedded collection.
        vector_size: Deterministic local embedding dimension.

    Returns:
        Number of chunks upserted.

    Raises:
        Exception: If canonical indexing cannot complete.
    """
    return index_document_pages_or_text(
        client=client,
        file_id=file_id,
        filename=filename,
        content=text,
        collection_name=collection_name,
        vector_size=vector_size,
    )
