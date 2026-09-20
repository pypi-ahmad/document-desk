"""Compatibility wrappers for the canonical pypdfium2 renderer."""

from pathlib import Path
from typing import List, Optional, Union

from src.render_pages import render_all_pages, sanitize_file_id


def render_pdf_pages(
    file_path: Union[str, Path],
    file_id: Optional[str] = None,
    dpi: int = 150,
    route: Optional[str] = "ollama",
) -> List[Path]:
    """Compatibility wrapper for the canonical routed page renderer.

    Args:
        file_path: Existing PDF or supported image source.
        file_id: Optional output subdirectory identifier.
        dpi: Requested render DPI, clamped by the canonical renderer.
        route: Routing decision; only `ollama` produces PNGs.

    Returns:
        PNG paths from `src.render_pages.render_all_pages`.

    Raises:
        FileNotFoundError: If `file_path` does not exist.
        ValueError: If the source extension is unsupported.
    """
    return render_all_pages(
        pdf_path=file_path,
        file_id=file_id,
        dpi=dpi,
        route=route,
    )
