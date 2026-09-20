"""Compare Page - Field-Level Version Comparison.

Compares two document versions by file_id:
1. Python-side set difference of field names (common_fields, only_in_a, only_in_b).
2. Agnes AI diffing field values only into a structured Markdown comparison table and analysis.
"""

from pathlib import Path
import json
import streamlit as st

from src.config import UPLOAD_DIR, FIXTURES_DIR, CACHE_DIR, is_agnes_key_set, AGNES_MODEL
from src.extract import ensure_sample_pdf, extract_document_pages, extract_with_agnes
from src.qa_service import compute_field_set_diff, diff_document_fields

st.title("⚖️ Compare Document Versions")
st.write(
    "Compare two document versions at the field level. "
    "Calculates exact Python set differences of field names and prompts Agnes AI "
    "to analyze changes in field values."
)

selected_provider = st.session_state.get("selected_provider", "Agnes AI")
selected_model = st.session_state.get("selected_model", AGNES_MODEL)

# Ensure sample fixture
sample_path = FIXTURES_DIR / "sample.pdf"
ensure_sample_pdf(sample_path)

# Discover available file_ids
documents = {path.stem: path for path in sorted(UPLOAD_DIR.glob("*.*"))}
if sample_path.exists():
    documents.setdefault("sample_fixture", sample_path)
sample_page = FIXTURES_DIR / "sample_page.png"
if sample_page.exists():
    documents.setdefault("sample_page", sample_page)
file_options = sorted(documents)

if len(file_options) < 1:
    st.info("No file IDs found. Upload documents on the Upload page first.")
    st.stop()

col_a, col_b = st.columns(2)

with col_a:
    st.subheader("Document A (Base Version)")
    file_id_a = st.selectbox("Select base file_id", options=file_options, index=0, key="select_doc_a")

with col_b:
    st.subheader("Document B (Comparison Version)")
    doc_b_idx = min(1, len(file_options) - 1)
    file_id_b = st.selectbox("Select comparison file_id", options=file_options, index=doc_b_idx, key="select_doc_b")


path_a = documents[file_id_a]
path_b = documents[file_id_b]


def get_or_extract_fields(file_id: str, path: Path) -> dict:
    """Load cached fields or extract fields for one comparison document.

    Args:
        file_id: Document identifier used to locate the extraction cache.
        path: Source document path when a fresh extraction is needed.

    Returns:
        Mapping of extracted field names to their values.

    Raises:
        Exception: If document extraction or Agnes structuring cannot complete.
    """
    cache_file = CACHE_DIR / f"{file_id}_extract.json"
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            fields_list = data.get("fields", [])
            return {f["name"]: f.get("value", "") for f in fields_list if "name" in f}
        except Exception:
            pass

    pages_info, _ = extract_document_pages(path, file_id=file_id)
    res = extract_with_agnes(pages_info, model=selected_model, provider_name=selected_provider, save_cache=True)
    cache_file.write_text(json.dumps(res, indent=2), encoding="utf-8")
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
                fields_a = get_or_extract_fields(file_id_a, path_a)
                fields_b = get_or_extract_fields(file_id_b, path_b)

                # 1. Python-side set difference of field names
                set_diff = compute_field_set_diff(fields_a, fields_b)

                st.divider()
                st.header("1. Field Name Set Differences (Python)")

                c1, c2, c3 = st.columns(3)
                c1.metric("Common Fields", len(set_diff["common_fields"]))
                c2.metric(f"Only in {file_id_a}", len(set_diff["only_in_a"]))
                c3.metric(f"Only in {file_id_b}", len(set_diff["only_in_b"]))

                col_comm, col_oa, col_ob = st.columns(3)
                with col_comm:
                    st.markdown("**Common Field Names:**")
                    if set_diff["common_fields"]:
                        for f in set_diff["common_fields"]:
                            st.markdown(f"- `{f}`")
                    else:
                        st.write("None")

                with col_oa:
                    st.markdown(f"**Only in {file_id_a}:**")
                    if set_diff["only_in_a"]:
                        for f in set_diff["only_in_a"]:
                            st.markdown(f"- `{f}`")
                    else:
                        st.write("None")

                with col_ob:
                    st.markdown(f"**Only in {file_id_b}:**")
                    if set_diff["only_in_b"]:
                        for f in set_diff["only_in_b"]:
                            st.markdown(f"- `{f}`")
                    else:
                        st.write("None")

                # 2. Model field-level diff
                st.divider()
                st.header("2. Field Value Comparison Report (Agnes AI)")

                diff_report = diff_document_fields(
                    doc_a_name=file_id_a,
                    fields_a=fields_a,
                    doc_b_name=file_id_b,
                    fields_b=fields_b,
                    model=selected_model,
                    provider_name=selected_provider,
                )

                st.markdown(diff_report)

            except Exception as e:
                st.error(f"Version comparison failed: {e}")
