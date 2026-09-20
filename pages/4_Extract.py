"""Extract Page - Structured Document Extraction with Agnes AI.

Calls agnes-3.0-flash (or selected model) to produce structured JSON:
{title, doc_type, fields:[{name,value,page}], tables:[], summary, citations:[{claim,page}]}
Displays structured JSON, an editable dataframe of fields, tables, and page citations.
"""

from pathlib import Path
import json
import pandas as pd
import streamlit as st

from src.config import UPLOAD_DIR, FIXTURES_DIR, CACHE_DIR, is_agnes_key_set, AGNES_MODEL
from src.extract import ensure_sample_pdf, extract_document_pages, extract_with_agnes

st.title("🔬 Structured Extraction")
st.write(
    "Extract structured JSON data (title, document type, fields, tables, summary, citations) "
    "from OCR text or native PDFs using Agnes AI (`agnes-3.0-flash`)."
)

selected_provider = st.session_state.get("selected_provider", "Agnes AI")
selected_model = st.session_state.get("selected_model", AGNES_MODEL)

# Discover documents
sample_path = FIXTURES_DIR / "sample.pdf"
ensure_sample_pdf(sample_path)

existing_files = sorted(list(UPLOAD_DIR.glob("*.*")))
file_options = []
if sample_path.exists():
    file_options.append("Sample Invoice Fixture (sample.pdf)")
file_options.extend([f.name for f in existing_files])

# Check for OCR cache
sample_page_fixture = FIXTURES_DIR / "sample_page.png"
if sample_page_fixture.exists() and "sample_page (OCR Fixture)" not in file_options:
    file_options.append("sample_page (OCR Fixture)")

if not file_options:
    st.info("No documents found. Please upload a document on the **Upload** page first.")
    st.stop()

selected_doc = st.selectbox("Select document to extract", options=file_options, index=0)

if selected_doc == "Sample Invoice Fixture (sample.pdf)":
    doc_path = sample_path
    doc_id = "sample_fixture"
elif selected_doc == "sample_page (OCR Fixture)":
    doc_path = sample_page_fixture
    doc_id = "sample_page"
else:
    doc_path = UPLOAD_DIR / selected_doc
    doc_id = doc_path.stem

st.write(f"Active Provider: **{selected_provider}** | Model: `{selected_model}`")

extract_btn = st.button("Run Agnes Extraction", type="primary")

session_key = f"extract_data_{doc_id}"
extracted_data = st.session_state.get(session_key)

# Check cache if not in session state
cache_file = CACHE_DIR / f"{doc_id}_extract.json"
if extracted_data is None and cache_file.exists():
    try:
        extracted_data = json.loads(cache_file.read_text(encoding="utf-8"))
        st.session_state[session_key] = extracted_data
    except Exception:
        pass

if extract_btn:
    if not is_agnes_key_set() and selected_provider == "Agnes AI":
        st.error(
            "⚠️ `AGNESAI_API_KEY` is not set in the environment or `.env`. "
            "Please configure `AGNESAI_API_KEY` before running extraction."
        )
    else:
        with st.spinner(f"Running structured extraction with {selected_model}..."):
            try:
                # Check if we have pre-extracted OCR text in session state
                cached_ocr = st.session_state.get(f"ocr_results_{doc_id}")
                if cached_ocr and isinstance(cached_ocr, list):
                    pages_info = [
                        {
                            "page_number": item.get("page", 1),
                            "text": item.get("text", "") or item.get("combined_text", ""),
                            "char_count": len(item.get("text", "")),
                            "image_path": None,
                        }
                        for item in cached_ocr
                    ]
                else:
                    pages_info = st.session_state.get(f"pages_info_{doc_id}")
                    if not pages_info:
                        pages_info, _ = extract_document_pages(
                            doc_path,
                            file_id=doc_id,
                        )

                extracted_data = extract_with_agnes(
                    pages_info,
                    model=selected_model,
                    provider_name=selected_provider,
                    save_cache=True,
                )
                cache_file.write_text(json.dumps(extracted_data, indent=2), encoding="utf-8")
                st.session_state[session_key] = extracted_data
                st.success("Extraction completed successfully!")
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
        edited_df = st.data_editor(df_fields, use_container_width=True, num_rows="dynamic")
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
                    st.dataframe(df_tbl, use_container_width=True)
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

    # Raw JSON
    with st.expander("💻 Raw Structured JSON", expanded=False):
        st.json(extracted_data)
        st.download_button(
            "Download Extracted JSON",
            data=json.dumps(extracted_data, indent=2),
            file_name=f"{doc_id}_extract.json",
            mime="application/json",
        )
