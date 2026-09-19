"""Embedded Qdrant vector store management.

Stores document chunks in local collection 'documents' under data/qdrant.
Supports chunk indexing and retrieval filtered by file_id with page citations.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import hashlib
from qdrant_client import QdrantClient
from qdrant_client.http import models

from src.config import QDRANT_PATH, QDRANT_COLLECTION


def get_qdrant_client(storage_path: str = QDRANT_PATH) -> QdrantClient:
    """Return local embedded QdrantClient instance."""
    path = Path(storage_path)
    path.mkdir(parents=True, exist_ok=True)
    return QdrantClient(path=str(path))


def init_collection(
    client: QdrantClient,
    collection_name: str = QDRANT_COLLECTION,
    vector_size: int = 256,
) -> None:
    """Initialize the documents Qdrant collection if not already existing."""
    collections = [col.name for col in client.get_collections().collections]
    if collection_name not in collections:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE,
            ),
        )


def _pseudo_embed(text: str, vector_size: int = 256) -> List[float]:
    """Generate normalized bag-of-words / hash feature vector for text."""
    vec = [0.0] * vector_size
    words = text.lower().split()
    if not words:
        return [0.0] * vector_size

    for word in words:
        h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
        idx = h % vector_size
        vec[idx] += 1.0

    norm = sum(x * x for x in vec) ** 0.5
    if norm > 0:
        vec = [x / norm for x in vec]
    return vec


def split_text_into_chunks(text: str, chunk_size: int = 500, overlap: int = 80) -> List[str]:
    """Split concatenated text into overlapping paragraph chunks."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [text.strip()] if text.strip() else []

    chunks: List[str] = []
    current_chunk = ""

    for para in paragraphs:
        if len(current_chunk) + len(para) > chunk_size and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = current_chunk[-overlap:] + "\n\n" + para
        else:
            if current_chunk:
                current_chunk += "\n\n" + para
            else:
                current_chunk = para

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks or [text[:chunk_size]]


def index_document_pages_or_text(
    client: QdrantClient,
    file_id: str,
    filename: str,
    content: Union[str, List[Dict[str, Any]]],
    collection_name: str = QDRANT_COLLECTION,
    vector_size: int = 256,
) -> int:
    """Chunk and index document pages or raw text into embedded Qdrant."""
    init_collection(client, collection_name=collection_name, vector_size=vector_size)

    points = []
    chunk_counter = 0

    if isinstance(content, list):
        # List of page dicts: [{"page_number": 1, "text": "..."}]
        for page_data in content:
            page_num = page_data.get("page_number", 1)
            raw_text = page_data.get("text", "").strip()
            if not raw_text:
                continue

            page_chunks = split_text_into_chunks(raw_text)
            for chunk in page_chunks:
                vec = _pseudo_embed(chunk, vector_size=vector_size)
                point_id = int(hashlib.sha256(f"{file_id}_{page_num}_{chunk_counter}_{chunk[:30]}".encode()).hexdigest()[:8], 16)
                points.append(
                    models.PointStruct(
                        id=point_id,
                        vector=vec,
                        payload={
                            "file_id": file_id,
                            "page": page_num,
                            "text": chunk,
                            "filename": filename,
                            "page_number": page_num,
                            "chunk_index": chunk_counter,
                        },
                    )
                )
                chunk_counter += 1
    else:
        # Plain text
        chunks = split_text_into_chunks(content)
        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                continue
            vec = _pseudo_embed(chunk, vector_size=vector_size)
            point_id = int(hashlib.sha256(f"{file_id}_{i}_{chunk[:30]}".encode()).hexdigest()[:8], 16)
            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=vec,
                    payload={
                        "file_id": file_id,
                        "page": 1,
                        "text": chunk,
                        "filename": filename,
                        "page_number": 1,
                        "chunk_index": i,
                    },
                )
            )

    if points:
        client.upsert(collection_name=collection_name, points=points)
    return len(points)


def search_document_chunks(
    client: QdrantClient,
    query: str,
    file_id: Optional[str] = None,
    limit: int = 5,
    collection_name: str = QDRANT_COLLECTION,
    vector_size: int = 256,
) -> List[Dict[str, Any]]:
    """Search for relevant chunks in embedded Qdrant, filtered by file_id."""
    init_collection(client, collection_name=collection_name, vector_size=vector_size)
    query_vector = _pseudo_embed(query, vector_size=vector_size)

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

    if hasattr(client, "query_points"):
        response = client.query_points(
            collection_name=collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=limit,
        )
        hits = response.points
    else:
        hits = client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            query_filter=query_filter,
            limit=limit,
        )

    return [
        {
            "score": getattr(hit, "score", 0.0),
            "text": hit.payload.get("text", "") if hit.payload else "",
            "file_id": hit.payload.get("file_id", "") if hit.payload else "",
            "filename": hit.payload.get("filename", "") if hit.payload else "",
            "page": hit.payload.get("page", hit.payload.get("page_number", 1)) if hit.payload else 1,
            "page_number": hit.payload.get("page", hit.payload.get("page_number", 1)) if hit.payload else 1,
            "chunk_index": hit.payload.get("chunk_index", 0) if hit.payload else 0,
        }
        for hit in hits
    ]
