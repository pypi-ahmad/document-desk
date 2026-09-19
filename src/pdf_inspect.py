"""PDF Inspection and Normalization module using pdf-inspector.

Wraps pdf_inspector.process_pdf(pdf_path) and produces normalized,
serializable Pydantic data structures for pipeline routing.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
import pdf_inspector


class PageOcrReasonItem(BaseModel):
    """Normalized OCR reason per page."""
    page: int
    reasons: List[str] = Field(default_factory=list)


class NormalizedPdfInspection(BaseModel):
    """Normalized representation of pdf_inspector.process_pdf output."""
    file_path: str
    filename: str
    pdf_type: str
    confidence: float
    page_count: int
    markdown: str = ""
    is_usable_markdown: bool = False
    pages_needing_ocr: List[int] = Field(default_factory=list)
    ocr_reasons_by_page: List[PageOcrReasonItem] = Field(default_factory=list)
    has_encoding_issues: bool = False
    is_complex_layout: bool = False
    pages_with_columns: List[int] = Field(default_factory=list)
    pages_with_tables: List[int] = Field(default_factory=list)
    processing_time_ms: int = 0
    title: Optional[str] = None
    should_skip_ocr: bool = False
    recommended_route: str = "paddleocr_vl"

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to standard Python dictionary."""
        return self.model_dump()


def inspect_pdf(pdf_path: Union[str, Path]) -> NormalizedPdfInspection:
    """Inspect and normalize PDF characteristics via pdf_inspector.process_pdf().
    
    Args:
        pdf_path: Local path to the PDF file.
        
    Returns:
        NormalizedPdfInspection containing typed, normalized metadata and routing advice.
        
    Raises:
        FileNotFoundError: If pdf_path does not exist on disk.
        ValueError: If file is not a valid PDF.
    """
    path = Path(pdf_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"PDF file not found: {path}")

    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Target file is not a PDF: {path.name}")

    # Invoke pdf_inspector built-in process_pdf
    raw_result = pdf_inspector.process_pdf(str(path))

    # Normalize fields
    pdf_type = str(getattr(raw_result, "pdf_type", "unknown")).strip().lower()
    confidence = float(getattr(raw_result, "confidence", 0.0))
    page_count = int(getattr(raw_result, "page_count", 0))

    # Normalize markdown text
    raw_md = getattr(raw_result, "markdown", None)
    markdown_str = str(raw_md).strip() if (raw_md is not None and isinstance(raw_md, str)) else ""
    is_usable_markdown = len(markdown_str) >= 20 and not markdown_str.isspace()

    # Pages needing OCR (ensure 1-indexed list of ints)
    raw_pages_needing_ocr = getattr(raw_result, "pages_needing_ocr", [])
    pages_needing_ocr = [int(p) for p in raw_pages_needing_ocr] if raw_pages_needing_ocr else []

    # OCR reasons per page
    ocr_reasons: List[PageOcrReasonItem] = []
    raw_reasons = getattr(raw_result, "ocr_reasons_by_page", [])
    if raw_reasons:
        for item in raw_reasons:
            page_num = int(getattr(item, "page", 0))
            reasons_list = [str(r) for r in getattr(item, "reasons", [])]
            ocr_reasons.append(PageOcrReasonItem(page=page_num, reasons=reasons_list))

    has_encoding_issues = bool(getattr(raw_result, "has_encoding_issues", False))
    is_complex_layout = bool(getattr(raw_result, "is_complex_layout", False))
    pages_with_columns = [int(p) for p in getattr(raw_result, "pages_with_columns", [])]
    pages_with_tables = [int(p) for p in getattr(raw_result, "pages_with_tables", [])]
    processing_time_ms = int(getattr(raw_result, "processing_time_ms", 0))
    title = getattr(raw_result, "title", None)
    if title is not None:
        title = str(title).strip() or None

    # Routing decision:
    # If text_based and markdown is usable -> skip OCR
    should_skip_ocr = (pdf_type == "text_based") and is_usable_markdown
    recommended_route = "native_markdown" if should_skip_ocr else "paddleocr_vl"

    return NormalizedPdfInspection(
        file_path=str(path),
        filename=path.name,
        pdf_type=pdf_type,
        confidence=confidence,
        page_count=page_count,
        markdown=markdown_str,
        is_usable_markdown=is_usable_markdown,
        pages_needing_ocr=pages_needing_ocr,
        ocr_reasons_by_page=ocr_reasons,
        has_encoding_issues=has_encoding_issues,
        is_complex_layout=is_complex_layout,
        pages_with_columns=pages_with_columns,
        pages_with_tables=pages_with_tables,
        processing_time_ms=processing_time_ms,
        title=title,
        should_skip_ocr=should_skip_ocr,
        recommended_route=recommended_route,
    )
