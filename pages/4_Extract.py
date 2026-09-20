"""Extract Page - Structured Document Extraction with Agnes AI.

Calls agnes-3.0-flash (or selected model) to produce structured JSON:
{title, doc_type, fields:[{name,value,page}], tables:[], summary, citations:[{claim,page}]}
Displays structured JSON, an editable dataframe of fields, tables, and page citations.
"""

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from src.config import AGNES_MODEL, CACHE_DIR, is_agnes_key_set
from src.extract import extract_with_agnes
from src.store import get_qdrant_client, index_document_pages_or_text

st.title("🔬 Structured Extraction")
st.write(
    "Extract structured JSON data (title, document type, fields, tables, summary, citations) "
    "from OCR text or native PDFs using Agnes AI (`agnes-3.0-flash`)."
)

selected_provider = st.session_state.get("selected_provider", "Agnes AI")
selected_model = st.session_state.get("selected_model", AGNES_MODEL)

doc_id = st.session_state.get("current_file_id")
file_path = st.session_state.get("current_file_path")
if not doc_id or not file_path or not Path(file_path).is_file():
    st.info("Upload a document first. Upload establishes the active file_id.")
    st.stop()

doc_path = Path(file_path)
inspection = st.session_state.get(f"inspect_{doc_id}")
if not inspection:
    st.info("Inspect the active document before extraction.")
    st.stop()

st.caption(f"Active file_id: `{doc_id}` | Route: `{inspection['route']}`")
st.write(f"Active Provider: **{selected_provider}** | Model: `{selected_model}`")

session_key = f"extract_data_{doc_id}"
extracted_data = st.session_state.get(session_key)
cache_file = CACHE_DIR / f"{doc_id}_extract.json"
ocr_required = inspection["route"] == "ollama"
ocr_results = st.session_state.get(f"ocr_results_{doc_id}", [])
extract_disabled = ocr_required and not ocr_results

if extract_disabled:
    st.info("This file is routed to OCR. Run OCR for this file_id before extraction.")

extract_btn = st.button(
    "Run Agnes Extraction",
    type="primary",
    disabled=extract_disabled,
)

if extract_btn:
    if not is_agnes_key_set() and selected_provider == "Agnes AI":
        st.error(
            "⚠️ `AGNESAI_API_KEY` is not set in the environment or `.env`. "
            "Please configure `AGNESAI_API_KEY` before running extraction."
        )
    else:
        with st.spinner(f"Running structured extraction with {selected_model}..."):
            try:
                if ocr_required:
                    pages_info = []
                    for item in ocr_results:
                        page_number = item.get("page", 1)
                        page_text = st.session_state.get(
                            f"page_text_{doc_id}_{page_number}"
                        ) or item.get("combined_text", "") or item.get("text", "")
                        pages_info.append(
                            {
                                "page_number": page_number,
                                "text": page_text,
                                "char_count": len(page_text),
                                "image_path": None,
                            }
                        )
                else:
                    pages_info = [
                        {
                            "page_number": 1,
                            "text": inspection.get("markdown", ""),
                            "image_path": None,
                        }
                    ]

                if not any(page.get("text", "").strip() for page in pages_info):
                    raise ValueError("No page text is available for extraction")

                extracted_data = extract_with_agnes(
                    pages_info,
                    model=selected_model,
                    provider_name=selected_provider,
                    save_cache=True,
                )
                cache_file.write_text(json.dumps(extracted_data, indent=2), encoding="utf-8")
                st.session_state[session_key] = extracted_data
                st.session_state[f"pages_info_{doc_id}"] = pages_info
                st.session_state[f"source_markdown_{doc_id}"] = "\n\n".join(
                    f"--- Page {page.get('page_number', page.get('page', 1))} ---\n{page['text']}"
                    for page in pages_info
                )

                client = get_qdrant_client()
                try:
                    chunk_count = index_document_pages_or_text(
                        client=client,
                        file_id=doc_id,
                        filename=doc_path.name,
                        content=pages_info,
                    )
                finally:
                    client.close()
                st.success(
                    f"Extraction completed and indexed {chunk_count} chunk(s) for Ask."
                )
            except Exception as e:
                st.error(f"Extraction failed: {e}")

if extracted_data:
    st.divider()
    st.subheader(f"Extraction Results: {extracted_data.get('title', 'Document')}")
    st.markdown(f"**Document Type:** `{extracted_data.get('doc_type', 'Unknown')}`")

    # Summary
    with st.expander("📝 Executive Summary", expanded=True):
        st.write(extracted_data.get("summary", "No summary provided."))

    # Fields Dataframe
    st.subheader("📋 Extracted Key-Value Fields")
    fields = extracted_data.get("fields", [])
    if fields:
        df_fields = pd.DataFrame(fields)
        edited_df = st.data_editor(df_fields, width="stretch", num_rows="dynamic")
    else:
        st.info("No structured fields were extracted.")

    # Tables
    tables = extracted_data.get("tables", [])
    if tables:
        st.subheader("📊 Extracted Tables")
        for idx, tbl in enumerate(tables):
            tbl_title = tbl.get("title", f"Table {idx + 1}")
            st.markdown(f"**{tbl_title}**")
            headers = tbl.get("headers", [])
            rows = tbl.get("rows", [])
            if headers and rows:
                try:
                    df_tbl = pd.DataFrame(rows, columns=headers)
                    st.dataframe(df_tbl, width="stretch")
                except Exception:
                    st.json(tbl)
            else:
                st.json(tbl)

    # Citations
    citations = extracted_data.get("citations", [])
    if citations:
        with st.expander("🔍 Citations & Grounding", expanded=False):
            for cite in citations:
                st.markdown(f"- **[Page {cite.get('page', '?')}]**: {cite.get('claim', '')}")

    markdown_export = st.session_state.get(f"source_markdown_{doc_id}", "")
    markdown_col, json_col = st.columns(2)
    with markdown_col:
        st.download_button(
            "Download Markdown",
            data=markdown_export,
            file_name=f"{doc_id}.md",
            mime="text/markdown",
            disabled=not markdown_export,
        )
    with json_col:
        st.download_button(
            "Download extract JSON",
            data=json.dumps(extracted_data, indent=2),
            file_name=f"{doc_id}_extract.json",
            mime="application/json",
        )

    # Raw JSON
    with st.expander("💻 Raw Structured JSON", expanded=False):
        st.json(extracted_data)
