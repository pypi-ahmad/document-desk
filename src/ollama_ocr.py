"""Ollama OCR module for PaddleOCR-VL (AuditAid/PaddleOCR-VL-1.6-0.9B).

Runs local VL inference via the official `ollama` Python client.
Enforces VL task prefixes:
  OCR:
  Table Recognition:
  Formula Recognition:
  Chart Recognition:
  Seal Recognition:
  Spotting:
Default page pass is OCR: followed by Table Recognition: if enabled.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import ollama

from src.config import (
    OLLAMA_HOST,
    OLLAMA_OCR_MODEL,
    TASK_OCR,
    TASK_TABLE,
    TASK_FORMULA,
    TASK_CHART,
    TASK_SEAL,
    TASK_SPOTTING,
    TASK_PREFIXES,
)


def check_ollama_status() -> Tuple[bool, bool, str, List[str]]:
    """Check whether Ollama is running and whether the required PaddleOCR-VL model is present.
    
    Returns:
        (is_running, has_model, user_message, model_names)
        
    If Ollama is down or model missing, user_message contains the required instruction:
    'start Ollama Desktop, then ollama pull AuditAid/PaddleOCR-VL-1.6-0.9B'
    """
    required_instruction = f"start Ollama Desktop, then ollama pull {OLLAMA_OCR_MODEL}"
    try:
        client = ollama.Client(host=OLLAMA_HOST)
        tags = client.list()
        models = [m.model for m in tags.models]
        has_model = any(OLLAMA_OCR_MODEL.lower() in m.lower() for m in models)
        if not has_model:
            return True, False, required_instruction, models
        return True, True, f"Ollama is running with {OLLAMA_OCR_MODEL}.", models
    except Exception:
        return False, False, required_instruction, []


def run_ollama_vl_task(
    image_input: Union[str, Path, bytes],
    task_prefix: str = TASK_OCR,
    options: Optional[Dict[str, Any]] = None,
) -> str:
    """Run a single VL task on an image with a specific task prefix at temperature 0."""
    if options is None:
        options = {"temperature": 0}

    client = ollama.Client(host=OLLAMA_HOST)

    images: List[Union[str, bytes]] = []
    if isinstance(image_input, (str, Path)):
        resolved = Path(image_input).resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Image not found at {resolved}")
        images = [str(resolved)]
    elif isinstance(image_input, bytes):
        images = [image_input]
    else:
        raise ValueError("image_input must be a file path or raw bytes")

    response = client.generate(
        model=OLLAMA_OCR_MODEL,
        prompt=task_prefix,
        images=images,
        options=options,
    )
    return response.response.strip()


def run_page_ocr(
    image_input: Union[str, Path, bytes],
    include_tables: bool = False,
    task_prefix: str = TASK_OCR,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """Execute Ollama VL OCR on image.
    
    Default pass: OCR:
    Second pass: Table Recognition: if include_tables=True.
    
    Returns:
        dict with keys:
          'ocr_text': output of OCR:
          'table_text': output of Table Recognition: (if enabled)
          'combined_text': unified text representation for Agnes extraction
    """
    ocr_text = run_ollama_vl_task(image_input, task_prefix=task_prefix, options=options)

    result = {
        "ocr": ocr_text,
        "tables": "",
        "ocr_text": ocr_text,
        "table_text": "",
        "combined_text": ocr_text,
    }

    if include_tables:
        table_text = run_ollama_vl_task(image_input, task_prefix=TASK_TABLE, options=options)
        result["tables"] = table_text
        result["table_text"] = table_text
        if table_text:
            result["combined_text"] = f"{ocr_text}\n\n[Table Structure]:\n{table_text}"

    return result
