"""Upload Page - Document Ingestion and Local Text Extraction.

Upload PDF or images to data/uploads/, extract per-page text via PyMuPDF,
and handle warnings for empty text pages (v1 text-first).
"""

from pathlib import Path
import streamlit as st

from src.config import UPLOAD_DIR, FIXTURES_DIR
from src.extract import ensure_sample_pdf, extract_pages_pymupdf

st.title("📤 Document Upload & Ingestion")
st.write(
    "Upload PDF or image files to `data/uploads/`. Text is extracted per page using PyMuPDF. "
    "If a page has no text, a warning is displayed and the rest of the document text is preserved."
)

sample_path = FIXTURES_DIR / "sample.pdf"
ensure_sample_pdf(sample_path)

col_up, col_exist = st.columns([1, 1])

with col_up:
    uploaded_file = st.file_uploader(
        "Upload PDF or image document",
        type=["pdf", "png", "jpg", "jpeg"],
        help="v1 is text-first. PyMuPDF extracts native text locally.",
    )

with col_exist:
    existing_files = sorted(list(UPLOAD_DIR.glob("*.*")))
    file_options = ["None"] + [f.name for f in existing_files]
    if sample_path.exists():
        file_options.append("Sample Invoice Fixture (sample.pdf)")

    selected_existing = st.selectbox(
        "Or choose an existing document",
        options=file_options,
        index=0,
    )

user_image_url = st.text_input(
    "Optional Public Image URL (Agnes vision requires a public URL; local PNGs cannot be passed as URLs):",
    value="",
    placeholder="https://example.com/document.png",
    help="Agnes vision models require a public HTTP/HTTPS URL. Local disk paths are never sent as image URLs.",
)

active_file_path: Path | None = None
active_file_id: str | None = None

if uploaded_file is not None:
    target_path = UPLOAD_DIR / uploaded_file.name
    with open(target_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    active_file_path = target_path
    active_file_id = target_path.stem
    st.success(f"Saved to uploads: `{uploaded_file.name}`")
elif selected_existing != "None":
    if selected_existing == "Sample Invoice Fixture (sample.pdf)":
        active_file_path = sample_path
        active_file_id = "sample_fixture"
    else:
        active_file_path = UPLOAD_DIR / selected_existing
        active_file_id = active_file_path.stem

if not active_file_path or not active_file_path.exists():
    st.info("Upload a document or select an existing document to begin.")
    st.stop()

# Perform per-page text extraction
with st.spinner("Extracting per-page text with PyMuPDF..."):
    pages_info, concat_text = extract_pages_pymupdf(
        active_file_path,
        user_image_url=user_image_url if user_image_url.strip() else None,
    )

# Store in session state for downstream pages
st.session_state["active_file_id"] = active_file_id
st.session_state["active_file_path"] = str(active_file_path)
st.session_state[f"pages_info_{active_file_id}"] = pages_info
st.session_state[f"concat_text_{active_file_id}"] = concat_text

# Check for empty text pages and display warnings
empty_pages = [p for p in pages_info if p.get("warning")]
if empty_pages:
    for ep in empty_pages:
        st.warning(f"⚠️ {ep['warning']}")
    st.caption("v1 is text-first. The app sends whatever text exists across the document.")

m1, m2, m3 = st.columns(3)
m1.metric("Pages Detected", len(pages_info))
m2.metric("Characters Extracted", len(concat_text))
m3.metric("Text Pages", sum(1 for p in pages_info if p.get("has_text", False)))

with st.expander("View Extracted Page Text", expanded=True):
    for p in pages_info:
        st.markdown(f"**Page {p['page_number']}**")
        st.text_area(
            f"Page {p['page_number']} Preview",
            value=p.get("text", ""),
            height=120,
            key=f"upload_preview_{p['page_number']}",
            disabled=True,
        )

st.success("Document text ready. Proceed to the Extract or Ask page.")
