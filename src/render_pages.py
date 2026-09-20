"""Page rendering module using pypdfium2.

Renders PDF pages to PNG under data/pages/<file_id>/ at 150-200 dpi
for Ollama PaddleOCR-VL local vision inference.
"""

from pathlib import Path
from typing import List, Union
import pypdfium2 as pdfium

from src.config import PAGES_DIR


def render_page(
    pdf_path: Union[str, Path],
    page_number_1based: int,
    file_id: str,
    dpi: int = 150,
) -> Path:
    """Render a single PDF page to PNG using pypdfium2."""
    doc = pdfium.PdfDocument(str(Path(pdf_path).resolve()))
    page_idx = page_number_1based - 1

    if page_idx < 0 or page_idx >= len(doc):
        doc.close()
        raise IndexError(f"Page {page_number_1based} out of range (total pages: {len(doc)})")

    page = doc[page_idx]
    scale = dpi / 72.0
    image = page.render(scale=scale).to_pil()
    doc.close()

    target_dir = PAGES_DIR / file_id
    target_dir.mkdir(parents=True, exist_ok=True)
    out_file = target_dir / f"page_{page_number_1based}.png"
    image.save(out_file, format="PNG")
    return out_file


def render_all_pages(
    pdf_path: Union[str, Path],
    file_id: str,
    dpi: int = 150,
) -> List[Path]:
    """Render all pages of a PDF to PNG under data/pages/<file_id>/."""
    doc = pdfium.PdfDocument(str(Path(pdf_path).resolve()))
    page_count = len(doc)
    doc.close()

    rendered_paths: List[Path] = []
    for p_num in range(1, page_count + 1):
        rendered_paths.append(render_page(pdf_path, p_num, file_id=file_id, dpi=dpi))

    return rendered_paths
