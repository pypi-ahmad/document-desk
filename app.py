"""Document Desk - Windows-Native Document Intelligence Workstation.

Streamlit application entry point:
- Sidebar: Agnes model fixed default agnes-3.0-flash; OCR model name shown read-only.
- Multi-page navigation: Health, Upload, OCR, Extract, Ask, Compare.
"""

import streamlit as st
from src.config import (
    AGNES_MODEL,
    OLLAMA_OCR_MODEL,
    is_agnes_key_set,
    QDRANT_PATH,
)

st.set_page_config(
    page_title="Document Desk",
    page_icon="📑",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----------------- Shared Sidebar -----------------
with st.sidebar:
    st.title("📑 Document Desk")
    st.caption("Windows-Native Document Intelligence")
    st.divider()

    st.subheader("⚙️ Models & Configuration")

    # Agnes model fixed default agnes-3.0-flash
    st.text_input(
        "Agnes Reasoning Model",
        value=AGNES_MODEL,
        disabled=True,
        help="Fixed default reasoning model: agnes-3.0-flash via official openai SDK.",
    )
    st.session_state["selected_model"] = AGNES_MODEL
    st.session_state["selected_provider"] = "Agnes AI"

    # OCR model shown read-only
    st.text_input(
        "Local Vision-Language OCR Model",
        value=OLLAMA_OCR_MODEL,
        disabled=True,
        help="Read-only: Local Ollama model AuditAid/PaddleOCR-VL-1.6-0.9B.",
    )

    st.divider()

    # Environment and Storage Status
    st.subheader("🔒 Environment Status")
    if is_agnes_key_set():
        st.success("`AGNESAI_API_KEY` is configured.")
    else:
        st.error("⚠️ `AGNESAI_API_KEY` is not set in environment or `.env`.")

    st.caption(f"Embedded Qdrant: `{QDRANT_PATH}` (single-process local storage)")


# ----------------- Multi-Page Navigation -----------------
health_page = st.Page(
    "pages/1_Health.py",
    title="Health",
    icon="🩺",
    default=True,
)
upload_page = st.Page(
    "pages/2_Upload.py",
    title="Upload",
    icon="📤",
)
ocr_page = st.Page(
    "pages/3_OCR.py",
    title="OCR",
    icon="👁️",
)
extract_page = st.Page(
    "pages/4_Extract.py",
    title="Extract",
    icon="🔬",
)
ask_page = st.Page(
    "pages/5_Ask.py",
    title="Ask",
    icon="💬",
)
compare_page = st.Page(
    "pages/6_Compare.py",
    title="Compare",
    icon="⚖️",
)

pg = st.navigation(
    [health_page, upload_page, ocr_page, extract_page, ask_page, compare_page],
    position="sidebar",
)

pg.run()
