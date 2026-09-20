"""Document processing pipeline using pdf-inspector, pypdfium2, and Ollama PaddleOCR-VL.

Rules:
- Native Windows 11. No WSL2. No Docker. No PaddlePaddle pip. No pymupdf / fitz.
- No process_pdf_with_ocr (pdf-inspector's internal OCR stack is forbidden; local Ollama serves VL).
- If PDF: call pdf_inspector.process_pdf(path). Use pdf_type, confidence, page_count, markdown.
- If pdf_type is text_based and markdown is usable: skip OCR.
- If scanned / image_based / mixed-with-empty-text / user forces OCR: render those pages with pypdfium2
  to PNG under data/pages/<file_id>/ at 150-200 dpi, then run Ollama VL with temperature 0.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid
from PIL import Image
import ollama
import pdf_inspector
import pypdfium2 as pdfium

from src.config import (
    OLLAMA_HOST,
    OLLAMA_OCR_MODEL,
    PAGES_DIR,
    TASK_OCR,
    TASK_TABLE,
)
from src.ollama_ocr import check_ollama_status


class ProcessingError(Exception):
    """Raised when document inspection, rasterization, or OCR fails."""
    pass


def inspect_pdf_file(pdf_path: Union[str, Path]) -> Dict[str, Any]:
    """Inspect and classify PDF using pdf-inspector.
    
    Extracts native Markdown without invoking internal OCR.
    """
    path_str = str(Path(pdf_path).resolve())
    result = pdf_inspector.process_pdf(path_str)

    # Clean markdown text if present
    md_text = result.markdown.strip() if (result.markdown and isinstance(result.markdown, str)) else ""

    # Determine if markdown is usable
    is_usable_markdown = len(md_text) >= 20 and not md_text.isspace()

    # Determine OCR pages needed (pdf-inspector provides 1-indexed pages_needing_ocr on PdfResult)
    pages_needing_ocr = list(getattr(result, "pages_needing_ocr", []))

    return {
        "pdf_type": result.pdf_type,
        "confidence": float(result.confidence),
        "page_count": int(result.page_count),
        "markdown": md_text,
        "is_usable": is_usable_markdown,
        "pages_needing_ocr": pages_needing_ocr,
        "has_encoding_issues": bool(getattr(result, "has_encoding_issues", False)),
        "is_complex_layout": bool(getattr(result, "is_complex_layout", False)),
        "title": getattr(result, "title", None),
    }


def render_pdf_page_pypdfium2(
    pdf_path: Union[str, Path],
    page_number_1based: int,
    file_id: str,
    dpi: int = 150,
) -> Path:
    """Render a single PDF page using pypdfium2 to PNG under data/pages/<file_id>/."""
    doc = pdfium.PdfDocument(str(Path(pdf_path).resolve()))
    page_idx = page_number_1based - 1

    if page_idx < 0 or page_idx >= len(doc):
        doc.close()
        raise ProcessingError(f"Page {page_number_1based} out of range (total: {len(doc)})")

    page = doc[page_idx]
    scale = dpi / 72.0
    image = page.render(scale=scale).to_pil()
    doc.close()

    target_dir = PAGES_DIR / file_id
    target_dir.mkdir(parents=True, exist_ok=True)
    out_file = target_dir / f"page_{page_number_1based}.png"
    image.save(out_file, format="PNG")
    return out_file


def run_ollama_vl_task(
    image_input: Union[bytes, str, Path],
    task_prefix: str = TASK_OCR,
) -> str:
    """Run PaddleOCR-VL model via official ollama Python client at temperature 0."""
    is_online, has_model, err_msg, _ = check_ollama_status()
    if not is_online or not has_model:
        raise ProcessingError(f"Ollama unavailable: {err_msg}")

    client = ollama.Client(host=OLLAMA_HOST)

    images: List[Union[str, bytes]] = []
    if isinstance(image_input, (str, Path)):
        images = [str(Path(image_input).resolve())]
    elif isinstance(image_input, bytes):
        images = [image_input]
    else:
        raise ValueError("image_input must be raw bytes or file path")

    response = client.generate(
        model=OLLAMA_OCR_MODEL,
        prompt=task_prefix,
        images=images,
        options={"temperature": 0},
    )
    return response.response.strip()


def run_page_ocr(
    image_input: Union[bytes, str, Path],
    include_tables: bool = False,
) -> Dict[str, str]:
    """Execute Ollama VL OCR on image.
    
    Default pass: OCR:
    Optional second pass: Table Recognition:
    """
    res_ocr = run_ollama_vl_task(image_input, task_prefix=TASK_OCR)
    output = {"ocr": res_ocr}

    if include_tables:
        res_table = run_ollama_vl_task(image_input, task_prefix=TASK_TABLE)
        output["tables"] = res_table

    return output


def process_document(
    file_path: Union[str, Path],
    file_id: Optional[str] = None,
    force_ocr: bool = False,
    include_tables: bool = True,
) -> Dict[str, Any]:
    """Execute complete Document Desk intake pipeline for PDF or image.
    
    1. Inspects PDF via pdf-inspector (if PDF).
    2. Routes to native Markdown if text_based and usable, unless force_ocr is True.
    3. If OCR needed, renders pages via pypdfium2 to data/pages/<file_id>/ and runs Ollama VL.
    4. Concatenates page text and returns structured record.
    """
    path = Path(file_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if not file_id:
        file_id = f"doc_{uuid.uuid4().hex[:8]}"

    suffix = path.suffix.lower()
    is_pdf = suffix == ".pdf"
    is_image = suffix in [".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"]

    if not (is_pdf or is_image):
        raise ValueError(f"Unsupported file type: {suffix}. Must be PDF or image.")

    pages_info: List[Dict[str, Any]] = []
    final_page_texts: List[str] = []

    if is_pdf:
        inspection = inspect_pdf_file(path)
        pdf_type = inspection["pdf_type"]
        is_usable = inspection["is_usable"]
        page_count = inspection["page_count"]
        pages_needing_ocr = inspection["pages_needing_ocr"]

        # Routing decision
        # Skip OCR if text_based and markdown is usable and user didn't force OCR
        should_skip_ocr = (pdf_type == "text_based") and is_usable and not force_ocr

        if should_skip_ocr:
            route = "native_markdown"
            concatenated_text = inspection["markdown"]
            pages_info.append({
                "page_number": 1,
                "text": concatenated_text,
                "method": "pdf-inspector-native",
                "image_path": None,
            })
            final_page_texts.append(concatenated_text)
        else:
            route = "pypdfium2_ollama_ocr"
            # Determine which pages to OCR
            # If force_ocr or scanned, OCR all pages
            if force_ocr or pdf_type in ["scanned", "image_based"] or not pages_needing_ocr:
                target_pages = list(range(1, page_count + 1))
            else:
                target_pages = pages_needing_ocr

            for p_num in range(1, page_count + 1):
                if p_num in target_pages or force_ocr:
                    # Raster page with pypdfium2
                    img_path = render_pdf_page_pypdfium2(path, p_num, file_id=file_id, dpi=150)
                    ocr_res = run_page_ocr(img_path, include_tables=include_tables)
                    
                    page_text = ocr_res["ocr"]
                    if include_tables and ocr_res.get("tables"):
                        page_text += f"\n\n[Tables / Structure]:\n{ocr_res['tables']}"

                    pages_info.append({
                        "page_number": p_num,
                        "text": page_text,
                        "method": "pypdfium2_paddleocr_vl",
                        "image_path": str(img_path),
                    })
                    final_page_texts.append(f"--- Page {p_num} ---\n{page_text}")
                else:
                    # Non-OCR page fallback
                    pages_info.append({
                        "page_number": p_num,
                        "text": f"[Page {p_num} native text]",
                        "method": "native_text",
                        "image_path": None,
                    })

            concatenated_text = "\n\n".join(final_page_texts)

        return {
            "file_id": file_id,
            "filename": path.name,
            "is_pdf": True,
            "pdf_type": pdf_type,
            "confidence": inspection["confidence"],
            "page_count": page_count,
            "route": route,
            "pages": pages_info,
            "concatenated_text": concatenated_text,
        }

    else:
        # User uploaded standalone image
        target_dir = PAGES_DIR / file_id
        target_dir.mkdir(parents=True, exist_ok=True)
        img_copy = target_dir / "page_1.png"
        img = Image.open(path)
        img.save(img_copy, format="PNG")

        ocr_res = run_page_ocr(img_copy, include_tables=include_tables)
        page_text = ocr_res["ocr"]
        if include_tables and ocr_res.get("tables"):
            page_text += f"\n\n[Tables / Structure]:\n{ocr_res['tables']}"

        pages_info.append({
            "page_number": 1,
            "text": page_text,
            "method": "image_paddleocr_vl",
            "image_path": str(img_copy),
        })

        return {
            "file_id": file_id,
            "filename": path.name,
            "is_pdf": False,
            "pdf_type": "standalone_image",
            "confidence": 1.0,
            "page_count": 1,
            "route": "image_ollama_ocr",
            "pages": pages_info,
            "concatenated_text": page_text,
        }
