"""Configuration management for Document Desk.

Reads environment variable names only; never hardcodes, logs, or exposes secret values.
Configures Agnes AI and local Ollama endpoints.
Configures local Ollama VL integration for PaddleOCR-VL.
"""

import os
from pathlib import Path
from typing import Any, Dict
from dotenv import load_dotenv

# Load .env without overriding active process environment
load_dotenv(override=False)

# Directory layout under data/
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
PAGES_DIR = DATA_DIR / "pages"
EXTRACTED_DIR = DATA_DIR / "extracted"
FIXTURES_DIR = DATA_DIR / "fixtures"
CACHE_DIR = DATA_DIR / "cache"
QDRANT_PATH = str(DATA_DIR / "qdrant")
QDRANT_COLLECTION = "documents"

for directory in (UPLOAD_DIR, PAGES_DIR, EXTRACTED_DIR, FIXTURES_DIR, CACHE_DIR, Path(QDRANT_PATH)):
    directory.mkdir(parents=True, exist_ok=True)

# Environment variable names
AGNESAI_API_KEY_ENV = "AGNESAI_API_KEY"
AGNES_BASE_URL_ENV = "AGNES_BASE_URL"
OLLAMA_HOST_ENV = "OLLAMA_HOST"
OLLAMA_OCR_MODEL_ENV = "OLLAMA_OCR_MODEL"

# Primary LLM defaults
AGNES_MODEL = "agnes-3.0-flash"
AGNES_BASE_URL = os.environ.get(AGNES_BASE_URL_ENV, "https://apihub.agnes-ai.com/v1").strip() or "https://apihub.agnes-ai.com/v1"

# Ollama OCR configuration. The model ID is fixed by the product contract.
OLLAMA_HOST = os.environ.get(OLLAMA_HOST_ENV, "http://127.0.0.1:11434").strip() or "http://127.0.0.1:11434"
OLLAMA_OCR_MODEL = "AuditAid/PaddleOCR-VL-1.6-0.9B"

# Task prefixes from PaddleOCR-VL llama.cpp / Ollama readme
TASK_OCR = "OCR:"
TASK_TABLE = "Table Recognition:"
TASK_FORMULA = "Formula Recognition:"
TASK_CHART = "Chart Recognition:"
TASK_SEAL = "Seal Recognition:"
TASK_SPOTTING = "Spotting:"

TASK_PREFIXES = {
    "OCR": TASK_OCR,
    "Table Recognition": TASK_TABLE,
    "Formula Recognition": TASK_FORMULA,
    "Chart Recognition": TASK_CHART,
    "Seal Recognition": TASK_SEAL,
    "Spotting": TASK_SPOTTING,
}


def is_agnes_key_set() -> bool:
    """Report whether the Agnes API key is configured.

    Returns:
        True when `AGNESAI_API_KEY` has a non-whitespace value; otherwise False.
    """
    return bool(os.environ.get(AGNESAI_API_KEY_ENV, "").strip())


def get_agnes_api_key() -> str:
    """Retrieve the Agnes API key without logging or printing it.

    Returns:
        The stripped `AGNESAI_API_KEY` value, or an empty string when unset.
    """
    return os.environ.get(AGNESAI_API_KEY_ENV, "").strip()


def get_available_providers() -> Dict[str, Dict[str, Any]]:
    """Describe configured LLM providers without exposing secret values.

    Returns:
        Provider metadata keyed by display name. Each record identifies the
        model, base URL, key environment-variable name, and configuration
        status, but never includes the secret itself.
    """
    providers: Dict[str, Dict[str, Any]] = {}

    # Primary provider: Agnes AI
    providers["Agnes AI"] = {
        "name": "Agnes AI",
        "models": ["agnes-3.0-flash"],
        "default_model": "agnes-3.0-flash",
        "base_url": AGNES_BASE_URL,
        "api_key_env": AGNESAI_API_KEY_ENV,
        "is_configured": is_agnes_key_set(),
    }

    return providers
