"""Compare Page - Field-Level Version Comparison.

Compares two document versions by file_id:
1. Python-side set difference of field names (common_fields, only_in_a, only_in_b).
2. Agnes AI diffing field values only into a structured Markdown comparison table and analysis.
"""

from pathlib import Path
import json
import streamlit as st

from src.config import UPLOAD_DIR, FIXTURES_DIR, CACHE_DIR, is_agnes_key_set
from src.extract import ensure_sample_pdf, extract_document_pages, extract_with_agnes
from src.qa_service import compute_field_set_diff, diff_document_fields

st.title("⚖️ Compare Document Versions")
st.write(
    "Compare two document versions at the field level. "
    "Calculates exact Python set differences of field names and prompts Agnes AI "
    "to analyze changes in field values."
)

selected_provider = st.session_state.get("selected_provider", "Agnes AI")
selected_model = st.session_state.get("selected_model", "agnes-3.0-flash")

# Ensure sample fixture
sample_path = FIXTURES_DIR / "sample.pdf"
ensure_sample_pdf(sample_path)

# Discover available files
available_files = sorted(list(UPLOAD_DIR.glob("*.*")))
file_options = [f.name for f in available_files]
if sample_path.exists():
    file_options.append("sample.pdf (Fixture)")

if len(file_options) < 1:
    st.info("No documents found in `data/uploads/` or `data/fixtures/`. Please upload documents on the Upload page first.")
    st.stop()

col_a, col_b = st.columns(2)

with col_a:
    st.subheader("Document A (Base Version)")
    doc_a_choice = st.selectbox("Select Base Document", options=file_options, index=0, key="select_doc_a")

with col_b:
    st.subheader("Document B (Comparison Version)")
    doc_b_idx = min(1, len(file_options) - 1)
    doc_b_choice = st.selectbox("Select Comparison Document", options=file_options, index=doc_b_idx, key="select_doc_b")


def resolve_file_path(choice: str) -> Path:
    if "sample.pdf" in choice:
        return sample_path
    return UPLOAD_DIR / choice


path_a = resolve_file_path(doc_a_choice)
path_b = resolve_file_path(doc_b_choice)


def get_or_extract_fields(path: Path) -> dict:
    """Load cached fields or run extraction."""
    stem = path.stem
    cache_file = CACHE_DIR / f"{stem}_extract.json"
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            fields_list = data.get("fields", [])
            return {f["name"]: f.get("value", "") for f in fields_list if "name" in f}
        except Exception:
            pass

    pages_info, _ = extract_document_pages(path, file_id=stem)
    res = extract_with_agnes(pages_info, model=selected_model, provider_name=selected_provider, save_cache=True)
    return {f["name"]: f.get("value", "") for f in res.get("fields", []) if "name" in f}


compare_btn = st.button("Compare Versions at Field Level", type="primary")

if compare_btn:
    if not is_agnes_key_set() and selected_provider == "Agnes AI":
        st.error(
            "⚠️ `AGNESAI_API_KEY` is not configured in the environment or `.env`. "
            "Please configure `AGNESAI_API_KEY` before comparing."
        )
    else:
        with st.spinner("Extracting and analyzing field differences..."):
            try:
                fields_a = get_or_extract_fields(path_a)
                fields_b = get_or_extract_fields(path_b)

                # 1. Python-side set difference of field names
                set_diff = compute_field_set_diff(fields_a, fields_b)

                st.divider()
                st.header("1. Field Name Set Differences (Python)")

                c1, c2, c3 = st.columns(3)
                c1.metric("Common Fields", len(set_diff["common_fields"]))
                c2.metric("Only in Doc A", len(set_diff["only_in_a"]))
                c3.metric("Only in Doc B", len(set_diff["only_in_b"]))

                with st.expander("View Field Name Breakdown", expanded=True):
                    col_s1, col_s2, col_s3 = st.columns(3)
                    with col_s1:
                        st.markdown("**Common Field Names:**")
                        for f in set_diff["common_fields"]:
                            st.write(f"- `{f}`")
                    with col_s2:
                        st.markdown(f"**Only in {path_a.name}:**")
                        for f in set_diff["only_in_a"]:
                            st.write(f"- `{f}`")
                    with col_s3:
                        st.markdown(f"**Only in {path_b.name}:**")
                        for f in set_diff["only_in_b"]:
                            st.write(f"- `{f}`")

                # 2. LLM Fields-Only Diff
                st.divider()
                st.header(f"2. Field Values Diff ({selected_model})")

                diff_report = diff_document_fields(
                    doc_a_name=path_a.name,
                    fields_a=fields_a,
                    doc_b_name=path_b.name,
                    fields_b=fields_b,
                    model=selected_model,
                    provider_name=selected_provider,
                )

                st.markdown(diff_report)

            except Exception as e:
                st.error(f"Comparison error: {e}")
