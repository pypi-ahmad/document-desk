"""Upload Page - Document Intake and Page Rendering.

Ingests PDFs or images, renders pages to PNG under data/pages/<file_id>/page-0001.png
using PyMuPDF (150-200 dpi), and prepares documents for OCR.
"""

from pathlib import Path
import re
import streamlit as st

from src.config import UPLOAD_DIR, FIXTURES_DIR, PAGES_DIR, OLLAMA_OCR_MODEL
from src.pdf_pages import render_pdf_pages, sanitize_file_id
from src.ollama_ocr import check_ollama_status

st.title("📤 Document Ingestion & Page Rendering")
st.write(
    "Upload PDFs or document images. Pages will be rendered to "
    "`data/pages/<file_id>/page-0001.png` at 150-200 DPI via PyMuPDF."
)

# Ollama status check banner
is_online, has_model, status_msg, _ = check_ollama_status()
if not is_online or not has_model:
    st.error(
        f"⚠️ Action Required: **start Ollama Desktop, then ollama pull {OLLAMA_OCR_MODEL}**"
    )

st.divider()

# File upload or fixture selection
tab_upload, tab_fixtures = st.tabs(["Upload New Document", "Select Fixture / Sample"])

active_path = None
active_filename = None

with tab_upload:
    uploaded_file = st.file_uploader(
        "Choose a PDF or image file",
        type=["pdf", "png", "jpg", "jpeg", "webp", "bmp", "tiff"],
        help="Upload a PDF or image file for OCR and extraction.",
    )
    if uploaded_file is not None:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        save_path = UPLOAD_DIR / uploaded_file.name
        with open(save_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        active_path = save_path
        active_filename = uploaded_file.name
        st.success(f"Uploaded and saved to `{save_path}`")

with tab_fixtures:
    fixtures = list(FIXTURES_DIR.glob("*.*")) if FIXTURES_DIR.exists() else []
    if fixtures:
        fixture_names = [f.name for f in fixtures]
        chosen_fixture = st.selectbox("Select existing sample fixture", fixture_names)
        if st.button("Load Selected Sample"):
            active_path = FIXTURES_DIR / chosen_fixture
            active_filename = chosen_fixture
            st.info(f"Loaded sample: `{active_filename}`")
    else:
        st.info("No sample files found in data/fixtures/.")

# Render pages when document is selected
if active_path and active_path.exists():
    file_id = sanitize_file_id(active_filename)
    st.session_state["current_file_id"] = file_id
    st.session_state["current_filename"] = active_filename
    st.session_state["current_file_path"] = str(active_path)

    st.subheader(f"Rendering Pages for: `{active_filename}`")
    col_dpi, col_btn = st.columns([1, 1])
    with col_dpi:
        dpi = st.slider("Rendering DPI", min_value=150, max_value=200, value=150, step=10)
    with col_btn:
        st.write("")
        st.write("")
        render_btn = st.button("Render Pages to PNG", type="primary")

    if render_btn:
        with st.spinner("Rendering document pages with PyMuPDF..."):
            try:
                page_paths = render_pdf_pages(active_path, file_id=file_id, dpi=dpi)
                st.session_state[f"pages_{file_id}"] = [str(p) for p in page_paths]
                st.success(f"Rendered {len(page_paths)} page(s) to `data/pages/{file_id}/`")
            except Exception as e:
                st.error(f"Page rendering failed: {e}")

    # Check if pages already exist
    existing_pages = sorted(list((PAGES_DIR / file_id).glob("page-*.png")))
    if existing_pages:
        st.write(f"**Rendered Page Files ({len(existing_pages)} total):**")
        st.session_state[f"pages_{file_id}"] = [str(p) for p in existing_pages]
        
        cols = st.columns(min(len(existing_pages), 4))
        for idx, p in enumerate(existing_pages[:8]):
            with cols[idx % len(cols)]:
                st.image(str(p), caption=p.name, use_container_width=True)
        
        st.info("👉 Pages are rendered and ready. Proceed to the **OCR** page to run local OCR!")
