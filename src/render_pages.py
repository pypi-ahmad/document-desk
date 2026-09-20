"""Page rendering module using pypdfium2.

Renders PDF pages to PNG under data/pages/<file_id>/page-XXXX.png at 150-200 dpi
for Ollama PaddleOCR-VL local vision inference.

Rule:
- Render only when route == "ollama".
"""

from pathlib import Path
import re
from typing import List, Optional, Union
from PIL import Image
import pypdfium2 as pdfium

from src.config import PAGES_DIR


def sanitize_file_id(filename_or_id: str) -> str:
    """Convert a filename or identifier into a safe page-directory name.

    Args:
        filename_or_id: Source filename or caller-supplied identifier.

    Returns:
        The filename stem with unsupported characters replaced by underscores.
    """
    stem = Path(filename_or_id).stem
    return re.sub(r"[^\w\-]", "_", stem)


def render_page(
    pdf_path: Union[str, Path],
    page_number_1based: int,
    file_id: str,
    dpi: int = 150,
    route: Optional[str] = "ollama",
) -> Optional[Path]:
    """Render one routed PDF page to a local PNG with pypdfium2.

    Args:
        pdf_path: Existing PDF to rasterize.
        page_number_1based: One-based PDF page number.
        file_id: Output subdirectory identifier.
        dpi: Requested DPI, clamped to 150 through 200.
        route: Current routing decision; non-Ollama routes skip rendering.

    Returns:
        PNG path in `data/pages/<file_id>/page-XXXX.png`, or None when the
        route is not `ollama`.

    Raises:
        IndexError: If `page_number_1based` is outside the PDF page range.
        Exception: If pypdfium2 cannot open or render the PDF.
    """
    if route and route != "ollama":
        return None

    path = Path(pdf_path).resolve()
    doc = pdfium.PdfDocument(str(path))
    page_idx = page_number_1based - 1

    if page_idx < 0 or page_idx >= len(doc):
        doc.close()
        raise IndexError(f"Page {page_number_1based} out of range (total pages: {len(doc)})")

    page = doc[page_idx]
    target_dpi = max(150, min(dpi, 200))
    scale = target_dpi / 72.0
    image = page.render(scale=scale).to_pil()
    doc.close()

    target_dir = PAGES_DIR / file_id
    target_dir.mkdir(parents=True, exist_ok=True)
    out_file = target_dir / f"page-{page_number_1based:04d}.png"
    image.save(out_file, format="PNG")
    return out_file


def render_all_pages(
    pdf_path: Union[str, Path],
    file_id: Optional[str] = None,
    dpi: int = 150,
    route: Optional[str] = "ollama",
) -> List[Path]:
    """Render every routed PDF page or copy one routed image as PNG.

    Args:
        pdf_path: Existing PDF or supported image file.
        file_id: Optional output subdirectory identifier.
        dpi: Requested PDF render DPI, clamped to 150 through 200.
        route: Current routing decision; non-Ollama routes skip rendering.

    Returns:
        Rendered PNG paths, or an empty list when the route is not `ollama`.

    Raises:
        FileNotFoundError: If `pdf_path` does not exist.
        ValueError: If the file extension is not a supported PDF or image type.
        Exception: If pypdfium2 or Pillow cannot render the source.
    """
    if route and route != "ollama":
        return []

    path = Path(pdf_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Input file not found: {path}")

    if not file_id:
        file_id = sanitize_file_id(path.name)

    target_dir = PAGES_DIR / file_id
    target_dir.mkdir(parents=True, exist_ok=True)

    suffix = path.suffix.lower()
    rendered_paths: List[Path] = []

    if suffix == ".pdf":
        doc = pdfium.PdfDocument(str(path))
        page_count = len(doc)
        target_dpi = max(150, min(dpi, 200))
        scale = target_dpi / 72.0

        for idx in range(page_count):
            p_num = idx + 1
            page = doc[idx]
            out_file = target_dir / f"page-{p_num:04d}.png"
            image = page.render(scale=scale).to_pil()
            image.save(out_file, format="PNG")
            rendered_paths.append(out_file)

        doc.close()

    elif suffix in [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"]:
        out_file = target_dir / "page-0001.png"
        with Image.open(path) as img:
            rgb_img = img.convert("RGB")
            rgb_img.save(out_file, format="PNG")
        rendered_paths.append(out_file)

    else:
        raise ValueError(f"Unsupported file format for rendering: {suffix}")

    return rendered_paths
