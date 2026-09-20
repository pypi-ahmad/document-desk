"""Configuration management for Document Desk.

Reads environment variable names only; never hardcodes, logs, or exposes secret values.
Supports provider discovery: Agnes AI (default), OpenAI Compatible, and Google Gemini.
Configures local Ollama VL integration for PaddleOCR-VL.
"""

import os
from pathlib import Path
from typing import Dict, Any, List
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
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
OPENAI_BASE_URL_ENV = "OPENAI_BASE_URL"
GOOGLE_API_KEY_ENV = "GOOGLE_API_KEY"
OLLAMA_HOST_ENV = "OLLAMA_HOST"
OLLAMA_OCR_MODEL_ENV = "OLLAMA_OCR_MODEL"

# Primary LLM defaults
AGNES_MODEL = "agnes-3.0-flash"
AGNES_BASE_URL = os.environ.get(AGNES_BASE_URL_ENV, "https://apihub.agnes-ai.com/v1").strip() or "https://apihub.agnes-ai.com/v1"

# Ollama OCR configuration
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
    """Return True if AGNESAI_API_KEY is configured in the environment."""
    return bool(os.environ.get(AGNESAI_API_KEY_ENV, "").strip())


def get_agnes_api_key() -> str:
    """Safely retrieve AGNESAI_API_KEY without logging or printing."""
    return os.environ.get(AGNESAI_API_KEY_ENV, "").strip()


def get_available_providers() -> Dict[str, Dict[str, Any]]:
    """Discover available providers based on existing environment variables.
    
    Hides any provider whose required environment variables are missing.
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

    # Optional: OpenAI Compatible (only if BOTH OPENAI_API_KEY and OPENAI_BASE_URL exist)
    openai_key = os.environ.get(OPENAI_API_KEY_ENV, "").strip()
    openai_url = os.environ.get(OPENAI_BASE_URL_ENV, "").strip()
    if openai_key and openai_url:
        providers["OpenAI Compatible"] = {
            "name": "OpenAI Compatible",
            "models": ["gpt-5.6-luna", "gpt-5.6-terra"],
            "default_model": "gpt-5.6-luna",
            "base_url": openai_url,
            "api_key_env": OPENAI_API_KEY_ENV,
            "is_configured": True,
        }

    # Optional: Google Gemini (only if GOOGLE_API_KEY exists)
    google_key = os.environ.get(GOOGLE_API_KEY_ENV, "").strip()
    if google_key:
        providers["Google Gemini"] = {
            "name": "Google Gemini",
            "models": ["gemini-3.5-flash-lite", "gemini-3.7-flash"],
            "default_model": "gemini-3.5-flash-lite",
            "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
            "api_key_env": GOOGLE_API_KEY_ENV,
            "is_configured": True,
        }

    return providers
