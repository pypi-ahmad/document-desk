"""Upload Page - Document Intake, PDF Inspection, and Page Rendering.

Ingests PDFs or images, calls pdf_inspector.process_pdf(path) first to classify
the document, renders pages to PNG under data/pages/<file_id>/page-0001.png
using pypdfium2 (150-200 dpi), and prepares documents for OCR or native extraction.
"""

from pathlib import Path
import streamlit as st

from src.config import UPLOAD_DIR, FIXTURES_DIR, PAGES_DIR, OLLAMA_OCR_MODEL
from src.pdf_inspect import inspect_pdf
from src.pdf_pages import render_pdf_pages, sanitize_file_id
from src.ollama_ocr import check_ollama_status

st.title("📤 Document Ingestion & Page Rendering")
st.write(
    "Upload PDFs or document images. Document Desk inspects PDF structure via "
    "`pdf-inspector`, renders pages to `data/pages/<file_id>/page-0001.png` at 150-200 DPI "
    "via `pypdfium2`, and routes to native text or local Ollama Vision OCR."
)

st.divider()

# File upload or fixture selection
tab_upload, tab_fixtures = st.tabs(["Upload New Document", "Select Fixture / Sample"])

saved_active_path = st.session_state.get("current_file_path")
active_path = Path(saved_active_path) if saved_active_path else None
active_filename = st.session_state.get("current_filename")

with tab_upload:
    uploaded_file = st.file_uploader(
        "Choose a PDF or image file",
        type=["pdf", "png", "jpg", "jpeg", "webp", "bmp", "tiff"],
        help="Upload a PDF or image file for inspection and extraction.",
    )
    if uploaded_file is not None:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        save_path = UPLOAD_DIR / uploaded_file.name
        with open(save_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        active_path = save_path
        active_filename = uploaded_file.name
        file_id = sanitize_file_id(active_filename)
        st.session_state["current_file_id"] = file_id
        st.session_state["current_file_path"] = str(save_path)
        st.session_state["current_filename"] = uploaded_file.name
        st.success(f"Uploaded and saved to `{save_path}`")

with tab_fixtures:
    fixtures = list(FIXTURES_DIR.glob("*.*")) if FIXTURES_DIR.exists() else []
    if fixtures:
        fixture_names = [f.name for f in fixtures]
        chosen_fixture = st.selectbox("Select existing sample fixture", fixture_names)
        if st.button("Load Selected Sample"):
            active_path = FIXTURES_DIR / chosen_fixture
            active_filename = chosen_fixture
            file_id = sanitize_file_id(active_filename)
            st.session_state["current_file_id"] = file_id
            st.session_state["current_file_path"] = str(active_path)
            st.session_state["current_filename"] = chosen_fixture
            st.info(f"Loaded sample: `{active_filename}`")
    else:
        st.info("No sample files found in data/fixtures/.")

# Render pages when document is selected
if active_path and active_path.exists():
    file_id = sanitize_file_id(active_filename)
    st.session_state["current_file_id"] = file_id
    st.session_state["current_filename"] = active_filename
    st.session_state["current_file_path"] = str(active_path)

    suffix = active_path.suffix.lower()

    # Step 1: Run pdf-inspector if PDF
    force_ocr = bool(st.session_state.get("force_ocr", False))
    st.caption(f"Force OCR: {'on' if force_ocr else 'off'}")
    route = "ollama"

    if suffix == ".pdf":
        st.subheader("📑 PDF Inspection (pdf-inspector)")
        with st.spinner("Analyzing PDF with pdf-inspector..."):
            try:
                insp = inspect_pdf(active_path, force_ocr=force_ocr)
                pdf_type = insp["pdf_type"]
                confidence = insp["confidence"]
                page_count = insp["page_count"]
                route = insp["route"]
                st.session_state[f"inspect_{file_id}"] = insp

                col_t, col_c, col_r = st.columns(3)
                col_t.metric("PDF Type", pdf_type)
                col_c.metric("Confidence", f"{confidence:.2f}")
                col_r.metric("Routing Decision", route.upper())
                st.info(f"Route reason: {insp['route_reason']}")

                st.text_area(
                    "Native Markdown preview",
                    value=insp["markdown"][:4000],
                    height=220,
                    disabled=True,
                )

                if route == "native":
                    st.success(
                        f"✅ Classified as **{pdf_type}** (confidence {confidence:.2f}) with usable markdown text. "
                        "**Ollama OCR skipped**: Native markdown will be processed directly."
                    )
                else:
                    st.warning(
                        f"👁️ Routing to **Ollama PaddleOCR-VL**: Document is **{pdf_type}** "
                        f"(confidence {confidence:.2f})"
                        + (" (forced by user checkbox)." if force_ocr else " or has empty/near-empty text.")
                    )
            except Exception as exc:
                st.warning(f"pdf-inspector analysis note: {exc}")
    else:
        image_route = {
            "path": str(active_path.resolve()),
            "file_path": str(active_path.resolve()),
            "filename": active_path.name,
            "pdf_type": "image",
            "confidence": 1.0,
            "page_count": 1,
            "markdown": "",
            "markdown_usable": False,
            "pages_needing_ocr": [1],
            "route": "ollama",
            "route_reason": "Uploaded images have no native PDF text and require OCR.",
            "force_ocr": force_ocr,
        }
        st.session_state[f"inspect_{file_id}"] = image_route
        st.info(f"Route reason: {image_route['route_reason']}")

    if route == "ollama":
        is_online, has_model, _status_msg, _ = check_ollama_status()
        if not is_online or not has_model:
            st.error(
                f"start Ollama, then: ollama pull {OLLAMA_OCR_MODEL}"
            )

    st.subheader(f"Rendering Pages for: `{active_filename}`")
    col_dpi, col_btn = st.columns([1, 1])
    with col_dpi:
        dpi = st.slider("Rendering DPI", min_value=150, max_value=200, value=150, step=10)
    with col_btn:
        st.write("")
        st.write("")
        render_btn = st.button(
            "Render pages to PNG (pypdfium2)",
            type="primary",
            disabled=route != "ollama",
        )

    if route != "ollama":
        st.info("Native Markdown is usable. Page rasterization is skipped.")

    if render_btn:
        with st.spinner("Rendering document pages with pypdfium2..."):
            try:
                page_paths = render_pdf_pages(
                    active_path,
                    file_id=file_id,
                    dpi=dpi,
                    route=route,
                )
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
                st.image(str(p), caption=p.name, width="stretch")

        st.info("👉 Pages are rendered and ready. Proceed to the **OCR** or **Extract** page!")
