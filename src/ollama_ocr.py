"""Ollama OCR module stub for PaddleOCR-VL.

Provides health inspection via Ollama /api/tags and OCR task wrappers.
"""

from typing import Any, Dict, List, Optional, Tuple, Union
from pathlib import Path
import httpx
import ollama

from src.config import OLLAMA_HOST, OLLAMA_OCR_MODEL

TASK_OCR = "OCR:"
TASK_TABLE = "Table Recognition:"


def check_ollama_tags() -> Tuple[bool, bool, List[str], str]:
    """Query Ollama /api/tags endpoint to check server availability and model presence."""
    endpoint = f"{OLLAMA_HOST.rstrip('/')}/api/tags"
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(endpoint)
            if resp.status_code != 200:
                return False, False, [], f"Ollama HTTP error status: {resp.status_code}"
            
            data = resp.json()
            models = [m.get("name", "") for m in data.get("models", [])]
            has_model = any(OLLAMA_OCR_MODEL.lower() in m.lower() for m in models)
            
            msg = "Ollama is running."
            if not has_model:
                msg += f" Model '{OLLAMA_OCR_MODEL}' is missing. Run: ollama pull {OLLAMA_OCR_MODEL}"
            else:
                msg += f" Model '{OLLAMA_OCR_MODEL}' is ready."

            return True, has_model, models, msg
    except Exception as err:
        return False, False, [], f"Ollama unreachable at {endpoint}: {err}"


def run_ocr_page(image_input: Union[bytes, str, Path], task_prefix: str = TASK_OCR) -> str:
    """Stub for running Ollama OCR on page image."""
    raise NotImplementedError("OCR execution will be connected in subsequent stage.")
