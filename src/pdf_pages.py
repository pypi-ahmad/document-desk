"""PDF and image page rendering module using PyMuPDF.

Renders each PDF page to PNG under data/pages/<file_id>/page-0001.png
at 150-200 dpi. Also accepts uploaded images and saves them into the
standard page naming format.
"""

from pathlib import Path
import re
from typing import List, Optional, Union
import pymupdf as fitz
from PIL import Image

from src.config import PAGES_DIR


def sanitize_file_id(filename_or_id: str) -> str:
    """Produce a safe filesystem identifier."""
    stem = Path(filename_or_id).stem
    return re.sub(r"[^\w\-]", "_", stem)


def render_pdf_pages(
    file_path: Union[str, Path],
    file_id: Optional[str] = None,
    dpi: int = 150,
) -> List[Path]:
    """Render each page of a PDF or image into PNGs under data/pages/<file_id>/page-0001.png.

    Args:
        file_path: Path to the PDF or image file.
        file_id: Optional directory identifier. Defaults to the sanitized file stem.
        dpi: Rendering resolution, 150 to 200 dpi (default 150).

    Returns:
        List of Path objects for each rendered page PNG.
    """
    path = Path(file_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Input file not found: {path}")

    if not file_id:
        file_id = sanitize_file_id(path.name)

    output_dir = PAGES_DIR / file_id
    output_dir.mkdir(parents=True, exist_ok=True)

    suffix = path.suffix.lower()
    rendered_pages: List[Path] = []

    if suffix == ".pdf":
        doc = fitz.open(str(path))
        # 72 points per inch standard PDF coordinate system (150-200 dpi)
        target_dpi = max(72, min(dpi, 300))
        zoom = target_dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)

        for idx, page in enumerate(doc):
            page_num = idx + 1
            page_filename = f"page-{page_num:04d}.png"
            page_path = output_dir / page_filename

            pix = page.get_pixmap(matrix=mat, alpha=False)
            pix.save(str(page_path))
            rendered_pages.append(page_path)

        doc.close()

    elif suffix in [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"]:
        page_filename = "page-0001.png"
        page_path = output_dir / page_filename
        with Image.open(path) as img:
            rgb_img = img.convert("RGB")
            rgb_img.save(str(page_path), format="PNG")
        rendered_pages.append(page_path)

    else:
        raise ValueError(f"Unsupported file format for page rendering: {suffix}")

    return rendered_pages
