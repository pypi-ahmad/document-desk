"""Inspect the active upload and explain its routing decision."""

from pathlib import Path

import streamlit as st

from src.pdf_inspect import inspect_pdf


st.title("Inspect document")

file_id = st.session_state.get("current_file_id")
file_path = st.session_state.get("current_file_path")
if not file_id or not file_path or not Path(file_path).is_file():
    st.info("Upload a document first. Upload establishes the active file_id.")
    st.stop()

path = Path(file_path)
state_key = f"inspect_{file_id}"
result = st.session_state.get(state_key)

st.caption(f"Active file_id: `{file_id}` | File: `{path.name}`")

if path.suffix.lower() == ".pdf":
    if st.button("Inspect active PDF", type="primary"):
        with st.spinner("Inspecting PDF locally..."):
            try:
                result = inspect_pdf(
                    path,
                    force_ocr=bool(st.session_state.get("force_ocr", False)),
                )
                st.session_state[state_key] = result
            except Exception as exc:
                st.error(f"PDF inspection failed: {exc}")
else:
    st.info("This upload is an image, so it is routed directly to local OCR.")

if not result:
    st.info("Return to Upload or inspect the active PDF to determine its route.")
    st.stop()

type_col, confidence_col, route_col = st.columns(3)
type_col.metric("Document type", result["pdf_type"])
confidence_col.metric("Confidence", f"{result['confidence']:.2f}")
route_col.metric("Route", result["route"].upper())
route_reason = result.get("route_reason") or (
    "Native Markdown is usable, so OCR is skipped."
    if result["route"] == "native"
    else "Native text is unavailable or insufficient, so local OCR is required."
)
st.info(f"Route reason: {route_reason}")
st.caption(f"Pages: {result['page_count']}")

markdown = result.get("markdown", "")
if markdown:
    st.text_area(
        "Native Markdown preview",
        value=markdown[:4000],
        height=320,
        disabled=True,
    )
    st.download_button(
        "Download Markdown",
        data=markdown,
        file_name=f"{file_id}.md",
        mime="text/markdown",
    )
