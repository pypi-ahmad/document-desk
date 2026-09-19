"""Ask Page - Semantic Q&A with Embedded Qdrant.

Chunks extracted text with page metadata and upserts into Qdrant collection "documents"
with payload {file_id, page, text}.
Retrieves k chunks filtered by file_id, and calls Agnes AI to answer strictly from
retrieved chunks with explicit page citations (e.g. [Page 1]).
If retrieval is empty, states so explicitly.
"""

from pathlib import Path
import streamlit as st

from src.config import UPLOAD_DIR, FIXTURES_DIR, QDRANT_PATH, is_agnes_key_set
from src.extract import ensure_sample_pdf, extract_pages_pymupdf
from src.vector_store import get_qdrant_client, index_document_pages_or_text, search_document_chunks
from src.qa_service import answer_question_with_page_citations

st.title("💬 Grounded Document Q&A")
st.write(
    "Query document chunks in local embedded Qdrant (`data/qdrant`). "
    "Answers are strictly grounded in retrieved excerpts and cite specific page numbers."
)

selected_provider = st.session_state.get("selected_provider", "Agnes AI")
selected_model = st.session_state.get("selected_model", "agnes-3.0-flash")

# Discover files
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

selected_doc = st.selectbox("Select document to query", options=file_options, index=0)

if selected_doc == "Sample Invoice Fixture (sample.pdf)":
    doc_path = sample_path
    doc_id = "sample_fixture"
else:
    doc_path = UPLOAD_DIR / selected_doc
    doc_id = doc_path.stem

col_btn, col_k = st.columns([1, 1])

with col_btn:
    index_btn = st.button("Index / Re-Index Document into Qdrant", type="secondary")

with col_k:
    top_k = st.slider("Retrieval Limit (k chunks)", min_value=1, max_value=8, value=4)

if index_btn:
    with st.spinner("Chunking with page metadata and indexing into embedded Qdrant..."):
        try:
            pages_info, _ = extract_pages_pymupdf(doc_path)
            client = get_qdrant_client()
            num_points = index_document_pages_or_text(
                client=client,
                file_id=doc_id,
                filename=doc_path.name,
                content=pages_info,
            )
            client.close()
            st.success(f"Indexed {num_points} chunks into embedded Qdrant collection `documents`.")
        except Exception as e:
            st.error(f"Failed to index into Qdrant: {e}")

# Question Form
with st.form("ask_question_form"):
    question = st.text_input(
        "Enter your question about this document:",
        placeholder="e.g. What is the total amount due and what are the payment terms?",
    )
    submit_btn = st.form_submit_button("Submit Question", type="primary")

if submit_btn and question.strip():
    if not is_agnes_key_set() and selected_provider == "Agnes AI":
        st.error(
            "⚠️ `AGNESAI_API_KEY` is not configured in the environment or `.env`. "
            "Please configure `AGNESAI_API_KEY`."
        )
    else:
        with st.spinner(f"Retrieving chunks and generating cited answer with {selected_model}..."):
            try:
                # 1. Retrieve k chunks filtered by file_id
                client = get_qdrant_client()
                retrieved = search_document_chunks(
                    client=client,
                    query=question,
                    file_id=doc_id,
                    limit=top_k,
                )
                client.close()

                # If retrieval empty, say so explicitly
                if not retrieved:
                    st.warning(
                        "Retrieval returned empty. No relevant chunks found for this document in Qdrant. "
                        "Please click 'Index / Re-Index Document into Qdrant' first."
                    )
                else:
                    answer = answer_question_with_page_citations(
                        question=question,
                        chunks=retrieved,
                        model=selected_model,
                        provider_name=selected_provider,
                    )

                    st.markdown("### Grounded Answer")
                    st.info(answer)

                    with st.expander(f"Inspect {len(retrieved)} Retrieved Chunks", expanded=False):
                        for idx, ch in enumerate(retrieved, 1):
                            st.markdown(
                                f"**Chunk {idx}** | Page {ch.get('page')} | Score: `{ch.get('score', 0):.3f}`"
                            )
                            st.text(ch.get("text", ""))
                            st.divider()

            except Exception as e:
                st.error(f"Error during question answering: {e}")
