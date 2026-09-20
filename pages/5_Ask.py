"""Grounded Q&A for the active extracted file_id."""

import json

import streamlit as st

from src.config import AGNES_MODEL, CACHE_DIR, is_agnes_key_set
from src.qa_service import answer_question_with_page_citations
from src.store import get_qdrant_client, search_document_chunks


st.title("Grounded document Q&A")

file_id = st.session_state.get("current_file_id")
if not file_id:
    st.info("Upload a document first. Upload establishes the active file_id.")
    st.stop()

st.caption(f"Active file_id: `{file_id}`")
extracted_data = st.session_state.get(f"extract_data_{file_id}")
ask_disabled = extracted_data is None
if ask_disabled:
    st.info("Ask is disabled until Extract has run for this file_id.")

top_k = st.slider("Retrieval limit (k chunks)", 1, 8, 4)
with st.form("ask_question_form"):
    question = st.text_input(
        "Question",
        placeholder="What is the invoice number and total amount due?",
        disabled=ask_disabled,
    )
    submit_btn = st.form_submit_button(
        "Ask",
        type="primary",
        disabled=ask_disabled,
    )

if submit_btn and question.strip():
    if not is_agnes_key_set():
        st.error("AGNESAI_API_KEY is not configured.")
    else:
        with st.spinner("Retrieving file-scoped chunks and generating a cited answer..."):
            try:
                client = get_qdrant_client()
                try:
                    chunks = search_document_chunks(
                        client=client,
                        query=question,
                        file_id=file_id,
                        limit=top_k,
                    )
                finally:
                    client.close()

                answer = answer_question_with_page_citations(
                    question=question,
                    chunks=chunks,
                    model=st.session_state.get("selected_model", AGNES_MODEL),
                    provider_name=st.session_state.get(
                        "selected_provider", "Agnes AI"
                    ),
                )
                ask_data = {
                    "file_id": file_id,
                    "question": question,
                    "answer": answer,
                    "chunks": chunks,
                }
                st.session_state[f"ask_data_{file_id}"] = ask_data
                cache_path = CACHE_DIR / f"{file_id}_ask.json"
                cache_path.write_text(json.dumps(ask_data, indent=2), encoding="utf-8")
            except Exception as exc:
                st.error(f"Ask failed: {exc}")

ask_data = st.session_state.get(f"ask_data_{file_id}")
if ask_data:
    if ask_data["chunks"]:
        st.subheader("Answer")
        st.markdown(ask_data["answer"])
    else:
        st.warning(ask_data["answer"])

    with st.expander(f"Retrieved chunks ({len(ask_data['chunks'])})"):
        for index, hit in enumerate(ask_data["chunks"], 1):
            st.markdown(
                f"**Chunk {index} — Page {hit.get('page', 1)} "
                f"(score {hit.get('score', 0.0):.2f})**"
            )
            st.text(hit.get("text", ""))

    st.download_button(
        "Download ask JSON",
        data=json.dumps(ask_data, indent=2),
        file_name=f"{file_id}_ask.json",
        mime="application/json",
    )
