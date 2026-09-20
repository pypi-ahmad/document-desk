"""Compatibility facade over the canonical Document Desk pipeline."""

from pathlib import Path
from typing import Any, Dict, Optional, Union
import uuid

from src.extract import extract_document_pages
from src.ollama_ocr import run_ollama_ocr_page
from src.pdf_inspect import inspect_pdf
from src.render_pages import render_page


class ProcessingError(Exception):
    """Represent a compatibility-layer document processing failure.

    Attributes:
        args: Error-message arguments inherited from `Exception`.
    """


def inspect_pdf_file(pdf_path: Union[str, Path]) -> Dict[str, Any]:
    """Inspect one PDF through the canonical local inspection function.

    Args:
        pdf_path: Existing PDF path.

    Returns:
        Normalized inspection data plus the legacy `is_usable` flag.

    Raises:
        FileNotFoundError: If `pdf_path` does not exist.
        Exception: If the canonical inspection call fails.
    """
    result = inspect_pdf(pdf_path, save_cache=False)
    return {
        **result,
        "is_usable": result["markdown_usable"],
    }


def render_pdf_page_pypdfium2(
    pdf_path: Union[str, Path],
    page_number_1based: int,
    file_id: str,
    dpi: int = 150,
) -> Path:
    """Render one PDF page through the canonical pypdfium2 renderer.

    Args:
        pdf_path: Existing PDF path.
        page_number_1based: One-based page number to render.
        file_id: Output directory identifier.
        dpi: Requested DPI, clamped to 150 through 200.

    Returns:
        Path to the rendered PNG.

    Raises:
        ProcessingError: If the renderer fails or produces no page.
    """
    try:
        rendered = render_page(
            pdf_path,
            page_number_1based=page_number_1based,
            file_id=file_id,
            dpi=dpi,
            route="ollama",
        )
    except (IndexError, OSError, ValueError) as exc:
        raise ProcessingError(str(exc)) from exc
    if rendered is None:
        raise ProcessingError(f"Failed to render page {page_number_1based}")
    return rendered


def run_page_ocr(
    image_input: Union[bytes, str, Path],
    include_tables: bool = False,
) -> Dict[str, str]:
    """Run local Ollama OCR and adapt it to legacy result keys.

    Args:
        image_input: Local rendered image path or image bytes.
        include_tables: Whether to run the table-recognition second pass.

    Returns:
        Legacy `ocr`, `tables`, and `combined_text` values.

    Raises:
        RuntimeError: If Ollama or its required model is unavailable.
        Exception: If OCR fails after retry.
    """
    result = run_ollama_ocr_page(
        image_input=image_input,
        page=1,
        include_tables=include_tables,
    )
    return {
        "ocr": result["text"],
        "tables": result["table_text"],
        "combined_text": result["combined_text"],
    }


def process_document(
    file_path: Union[str, Path],
    file_id: Optional[str] = None,
    force_ocr: bool = False,
    include_tables: bool = True,
) -> Dict[str, Any]:
    """Process a PDF or image into locally derived page text.

    Args:
        file_path: Existing PDF or supported image path.
        file_id: Optional active-document identifier.
        force_ocr: Whether to route a PDF through OCR regardless of classification.
        include_tables: Whether OCR should run the table-recognition pass.

    Returns:
        Compatibility metadata, page records, and concatenated text.

    Raises:
        FileNotFoundError: If `file_path` does not exist.
        ValueError: If the source format is unsupported.
        RuntimeError: If required Ollama OCR is unavailable.
    """
    path = Path(file_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    document_id = file_id or f"doc_{uuid.uuid4().hex[:8]}"
    pages, concatenated_text = extract_document_pages(
        path,
        file_id=document_id,
        force_ocr=force_ocr,
        include_tables=include_tables,
    )

    if path.suffix.lower() == ".pdf":
        inspection = inspect_pdf(path, force_ocr=force_ocr, save_cache=False)
        pdf_type = inspection["pdf_type"]
        confidence = inspection["confidence"]
        page_count = inspection["page_count"]
        route = inspection["route"]
    else:
        pdf_type = "standalone_image"
        confidence = 1.0
        page_count = 1
        route = "ollama"

    return {
        "file_id": document_id,
        "filename": path.name,
        "is_pdf": path.suffix.lower() == ".pdf",
        "pdf_type": pdf_type,
        "confidence": confidence,
        "page_count": page_count,
        "route": route,
        "pages": pages,
        "concatenated_text": concatenated_text,
    }
