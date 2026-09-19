"""Extract Page - Structured Document Extraction.

Calls agnes-3.0-flash (or selected model) to produce structured JSON:
{title, doc_type, fields:[{name,value,page}], tables:[], summary, citations:[{claim,page}]}
Displays structured JSON, a dataframe of fields, tables, and page citations.
"""

from pathlib import Path
import json
import pandas as pd
import streamlit as st

from src.config import UPLOAD_DIR, FIXTURES_DIR, CACHE_DIR, is_agnes_key_set
from src.extract import ensure_sample_pdf, extract_pages_pymupdf, extract_with_agnes

st.title("🔬 Structured Extraction")
st.write(
    "Extract structured JSON data (title, document type, fields, tables, summary, citations) "
    "from uploaded documents using Agnes AI (`agnes-3.0-flash`) or your selected sidebar provider."
)

selected_provider = st.session_state.get("selected_provider", "Agnes AI")
selected_model = st.session_state.get("selected_model", "agnes-3.0-flash")

# Discover documents
sample_path = FIXTURES_DIR / "sample.pdf"
ensure_sample_pdf(sample_path)

existing_files = sorted(list(UPLOAD_DIR.glob("*.*")))
file_options = []
if sample_path.exists():
    file_options.append("Sample Invoice Fixture (sample.pdf)")
file_options.extend([f.name for f in existing_files])

if not file_options:
    st.info("No documents found. Please upload a document on the Upload page first.")
    st.stop()

selected_doc = st.selectbox("Select document to extract", options=file_options, index=0)

if selected_doc == "Sample Invoice Fixture (sample.pdf)":
    doc_path = sample_path
    doc_id = "sample_fixture"
else:
    doc_path = UPLOAD_DIR / selected_doc
    doc_id = doc_path.stem

# Optional image URL
user_image_url = st.text_input(
    "Optional Public Image URL (Agnes vision requires a public URL):",
    value="",
    placeholder="https://example.com/document.png",
)

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
                pages_info, _ = extract_pages_pymupdf(
                    doc_path,
                    user_image_url=user_image_url if user_image_url.strip() else None,
                )
                extracted_data = extract_with_agnes(
                    pages_info,
                    user_image_url=user_image_url if user_image_url.strip() else None,
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
    st.subheader(extracted_data.get("title", "Extracted Document"))
    st.caption(f"Document Type: **{extracted_data.get('doc_type', 'General Document')}**")

    if extracted_data.get("summary"):
        st.info(f"**Executive Summary:** {extracted_data['summary']}")

    # Dataframe of fields
    raw_fields = extracted_data.get("fields", [])
    if raw_fields:
        st.markdown("### Extracted Fields DataFrame")
        fields_df = pd.DataFrame(raw_fields)
        cols = [c for c in ["name", "value", "page"] if c in fields_df.columns]
        fields_df = fields_df[cols] if cols else fields_df

        st.dataframe(fields_df, use_container_width=True)

        with st.expander("Edit Fields", expanded=False):
            edited_df = st.data_editor(
                fields_df,
                num_rows="dynamic",
                use_container_width=True,
                key=f"fields_editor_{doc_id}",
            )

    # Tables
    raw_tables = extracted_data.get("tables", [])
    if raw_tables:
        st.markdown("### Extracted Tables")
        for idx, tbl in enumerate(raw_tables, 1):
            t_title = tbl.get("title", f"Table {idx}")
            t_headers = tbl.get("headers", [])
            t_rows = tbl.get("rows", [])
            st.markdown(f"**{t_title}**")
            if t_rows and t_headers:
                try:
                    tdf = pd.DataFrame(t_rows, columns=t_headers)
                    st.dataframe(tdf, use_container_width=True)
                except Exception:
                    st.json(tbl)
            else:
                st.json(tbl)

    # Citations
    raw_citations = extracted_data.get("citations", [])
    if raw_citations:
        st.markdown("### Page Citations")
        for cit in raw_citations:
            claim = cit.get("claim", "")
            page = cit.get("page", 1)
            st.markdown(f"- **[Page {page}]**: {claim}")

    # JSON View
    st.markdown("### Structured JSON Output")
    st.json(extracted_data)
    st.download_button(
        "Download JSON",
        data=json.dumps(extracted_data, indent=2),
        file_name=f"{doc_id}_structured.json",
        mime="application/json",
    )
