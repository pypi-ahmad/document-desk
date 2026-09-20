"""Upload Page - Document Ingestion and Local Ollama PaddleOCR-VL Extraction.

Upload PDF or images to data/uploads/, extract text per page via:
- Ollama PaddleOCR-VL (AuditAid/PaddleOCR-VL-1.6-0.9B) for local OCR
- Default pass: OCR:
- Second pass: Table Recognition: if enabled
- Native PyMuPDF text fallback for digital PDFs when OCR is not forced
- Strict non-crash error handling if Ollama is down or model missing:
  'start Ollama Desktop, then ollama pull AuditAid/PaddleOCR-VL-1.6-0.9B'
"""

from pathlib import Path
import streamlit as st

from src.config import UPLOAD_DIR, FIXTURES_DIR, OLLAMA_OCR_MODEL
from src.extract import ensure_sample_pdf, extract_document_pages
from src.ollama_ocr import check_ollama_status

st.title("Document Upload & Ingestion")
st.write(
    "Upload PDFs or images to `data/uploads/`. Local vision OCR runs via Ollama "
    f"(`{OLLAMA_OCR_MODEL}`) using task prefixes like `OCR:` and optional `Table Recognition:`."
)

# 1. Ollama Health & Model Status Check
is_online, has_model, ollama_instruction, models = check_ollama_status()
if not is_online or not has_model:
    st.error("start Ollama Desktop, then ollama pull AuditAid/PaddleOCR-VL-1.6-0.9B")
else:
    st.success(f"Ollama is running with model `{OLLAMA_OCR_MODEL}`")

sample_path = FIXTURES_DIR / "sample.pdf"
ensure_sample_pdf(sample_path)

col_up, col_exist = st.columns([1, 1])

with col_up:
    uploaded_file = st.file_uploader(
        "Upload PDF or image document",
        type=["pdf", "png", "jpg", "jpeg", "webp", "bmp", "tiff"],
        help="Local OCR runs via Ollama PaddleOCR-VL. Local paths are never sent to Agnes as URLs.",
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

# OCR Configuration options
st.markdown("### OCR Options")
col_opt1, col_opt2 = st.columns(2)
with col_opt1:
    force_ocr = st.checkbox(
        "Force Ollama VL OCR on all pages",
        value=False,
        help="Renders all PDF pages to PNG and executes Ollama PaddleOCR-VL (useful for scanned documents).",
    )
with col_opt2:
    enable_tables = st.checkbox(
        "Enable Table Recognition pass (`Table Recognition:`)",
        value=True,
        help="Runs a secondary pass using prompt 'Table Recognition:' to extract table structures.",
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

# Perform document extraction
with st.spinner("Extracting text and running local OCR if required..."):
    pages_info, concat_text = extract_document_pages(
        file_path=active_file_path,
        file_id=active_file_id,
        force_ocr=force_ocr,
        include_tables=enable_tables,
        user_image_url=user_image_url if user_image_url.strip() else None,
    )

# Store in session state for downstream pages
st.session_state["active_file_id"] = active_file_id
st.session_state["active_file_path"] = str(active_file_path)
st.session_state[f"pages_info_{active_file_id}"] = pages_info
st.session_state[f"concat_text_{active_file_id}"] = concat_text

# Check for warnings or empty pages
warnings = [p for p in pages_info if p.get("warning")]
if warnings:
    for w in warnings:
        st.warning(f"Warning: {w['warning']}")

m1, m2, m3 = st.columns(3)
m1.metric("Pages Detected", len(pages_info))
m2.metric("Characters Extracted", len(concat_text))
vl_count = sum(1 for p in pages_info if p.get("method") == "ollama_paddleocr_vl")
m3.metric("Ollama VL OCR Pages", vl_count)

with st.expander("View Extracted Page Text & Details", expanded=True):
    for p in pages_info:
        st.markdown(f"**Page {p['page_number']}** (Method: `{p.get('method', 'native')}`)")
        if p.get("image_path") and Path(p["image_path"]).exists():
            st.image(p["image_path"], caption=f"Page {p['page_number']} rendered image", width=350)
        st.text_area(
            f"Page {p['page_number']} Extracted Content",
            value=p.get("text", ""),
            height=140,
            key=f"upload_preview_{p['page_number']}",
            disabled=True,
        )

st.success("Document text ready. Proceed to the Extract, Ask, or Compare page.")
