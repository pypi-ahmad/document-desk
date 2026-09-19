"""Page rendering module stub using pypdfium2.

Renders PDF pages to PNG under data/pages/<file_id>/ at 150-200 dpi when OCR is routed.
"""

from pathlib import Path
from typing import Union


def render_page(
    pdf_path: Union[str, Path],
    page_number_1based: int,
    file_id: str,
    dpi: int = 150,
) -> Path:
    """Stub: Render PDF page to PNG using pypdfium2."""
    raise NotImplementedError("Page rasterization will be connected in subsequent stage.")
