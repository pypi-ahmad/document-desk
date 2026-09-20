"""PDF Inspection and Routing module using pdf-inspector.

Wraps pdf_inspector.process_pdf(pdf_path) and returns:
{
    "pdf_type": str,
    "confidence": float,
    "page_count": int,
    "markdown": str,
    "route": "native" | "ollama"
}

Routing rule:
- "native" for text_based PDFs with substantial Markdown.
- mixed PDFs with substantial Markdown stay native unless pdf-inspector identifies
  pages that need OCR.
- "ollama" for scanned/image PDFs, unusable Markdown, mixed pages needing OCR,
  or forced OCR.
"""

import json
from pathlib import Path
import re
from typing import Any

import pdf_inspector

from src.config import CACHE_DIR


SUBSTANTIAL_MARKDOWN_CHARS = 20


def _normalize_pdf_type(value: Any) -> str:
    """Normalize pdf-inspector enum or string values to lowercase snake case."""
    raw_value = getattr(value, "value", value)
    normalized = re.sub(r"[^a-z0-9]+", "_", str(raw_value).strip().lower()).strip("_")
    return normalized.removeprefix("pdftype_") or "unknown"


def inspect_pdf(
    pdf_path: str | Path,
    force_ocr: bool = False,
    save_cache: bool = True,
) -> dict[str, Any]:
    """Inspect and route a PDF using `pdf_inspector.process_pdf`.

    Args:
        pdf_path: Path to the target PDF file.
        force_ocr: Whether the user manually requested OCR regardless of classification.
        save_cache: Whether to persist the inspection result to data/cache/last_inspect.json.

    Returns:
        Normalized inspection data containing classification, native Markdown,
        routing decision, and human-readable route reason.

    Raises:
        FileNotFoundError: If `pdf_path` is not an existing file.
        Exception: If `pdf-inspector` cannot process the supplied PDF.
    """
    path = Path(pdf_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"PDF file not found: {path}")

    # Primary call: pdf_inspector.process_pdf(pdf_path)
    raw_result = pdf_inspector.process_pdf(str(path))

    pdf_type = _normalize_pdf_type(getattr(raw_result, "pdf_type", "unknown"))
    confidence = float(getattr(raw_result, "confidence", 0.0))
    page_count = int(getattr(raw_result, "page_count", 0))

    raw_md = getattr(raw_result, "markdown", None)
    if raw_md is None:
        markdown_str = ""
    else:
        markdown_str = str(raw_md).strip()

    pages_needing_ocr = [
        int(page) for page in getattr(raw_result, "pages_needing_ocr", [])
    ]
    markdown_usable = len(markdown_str) >= SUBSTANTIAL_MARKDOWN_CHARS

    if force_ocr:
        route = "ollama"
        route_reason = "Force OCR is enabled."
    elif pdf_type in {"scanned", "image_based"}:
        route = "ollama"
        route_reason = f"PDF type is {pdf_type}, so native text is insufficient."
    elif not markdown_usable:
        route = "ollama"
        route_reason = "Native Markdown is empty or too thin to use reliably."
    elif pdf_type == "mixed" and pages_needing_ocr:
        route = "ollama"
        route_reason = (
            "Mixed PDF has pages without usable native text: "
            + ", ".join(str(page) for page in pages_needing_ocr)
            + "."
        )
    else:
        route = "native"
        route_reason = "Text-based PDF has usable native Markdown, so OCR is skipped."

    result_dict: dict[str, Any] = {
        "path": str(path),
        "file_path": str(path),
        "filename": path.name,
        "pdf_type": pdf_type,
        "confidence": confidence,
        "page_count": page_count,
        "markdown": markdown_str,
        "markdown_usable": markdown_usable,
        "pages_needing_ocr": pages_needing_ocr,
        "has_encoding_issues": bool(getattr(raw_result, "has_encoding_issues", False)),
        "is_complex_layout": bool(getattr(raw_result, "is_complex_layout", False)),
        "title": getattr(raw_result, "title", None),
        "route": route,
        "route_reason": route_reason,
        "force_ocr": force_ocr,
    }

    if save_cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path = CACHE_DIR / "last_inspect.json"
        cache_path.write_text(json.dumps(result_dict, indent=2), encoding="utf-8")

    return result_dict
