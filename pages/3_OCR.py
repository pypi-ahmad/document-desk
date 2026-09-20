"""OCR Page - Local Vision-Language OCR with Ollama PaddleOCR-VL.

Features:
- Page gallery showing rendered page images
- Pass 1: "OCR:" prompt prefix at temperature 0
- Optional Pass 2: "Table Recognition:" prompt prefix
- Raw model text output view
- Editable page text editor with persistent state for Extract and Ask
"""

import json
from pathlib import Path
import streamlit as st

from src.config import (
    PAGES_DIR,
    CACHE_DIR,
    OLLAMA_OCR_MODEL,
)
from src.ollama_ocr import (
    OLLAMA_SETUP_MESSAGE,
    check_ollama_status,
    run_ollama_ocr_page,
)
from src.render_pages import render_all_pages

st.title("👁️ Local Vision-Language OCR")
st.write(
    f"Performs local OCR using Ollama model **`{OLLAMA_OCR_MODEL}`** "
    f"at temperature 0 with task prefixes."
)

st.divider()

doc_id = st.session_state.get("current_file_id")
file_path = st.session_state.get("current_file_path")
if not doc_id or not file_path or not Path(file_path).is_file():
    st.info("Upload a document first. Upload establishes the active file_id.")
    st.stop()

inspection = st.session_state.get(f"inspect_{doc_id}")
if not inspection:
    st.info("Inspect the active document before OCR.")
    st.stop()
if inspection.get("route") != "ollama":
    st.success(f"OCR skipped for `{doc_id}`. {inspection.get('route_reason', '')}")
    st.stop()

is_online, has_model, _status_msg, _ = check_ollama_status()
if not is_online or not has_model:
    st.error(OLLAMA_SETUP_MESSAGE)

st.caption(f"Active file_id: `{doc_id}`")
st.info(f"OCR route reason: {inspection.get('route_reason', '')}")

doc_pages = sorted((PAGES_DIR / doc_id).glob("page-*.png"))
if not doc_pages:
    with st.spinner("Rendering routed pages with pypdfium2..."):
        try:
            doc_pages = render_all_pages(
                file_path,
                file_id=doc_id,
                dpi=150,
                route="ollama",
            )
            st.session_state[f"pages_{doc_id}"] = [str(path) for path in doc_pages]
        except Exception as exc:
            st.error(f"Page rendering failed: {exc}")
            st.stop()

st.subheader(f"Page Gallery ({len(doc_pages)} page(s))")

# Page gallery display
cols = st.columns(min(len(doc_pages), 4))
for idx, page_path in enumerate(doc_pages):
    with cols[idx % len(cols)]:
        st.image(str(page_path), caption=f"Page {idx + 1}: {page_path.name}", width="stretch")

st.divider()

# OCR Execution Controls
col_opts, col_run = st.columns([2, 1])
with col_opts:
    include_tables = bool(st.session_state.get("include_tables", False))
    st.caption(f"Table recognition: {'on' if include_tables else 'off'} (sidebar)")
    selected_page_idx = st.selectbox(
        "Select specific page to process (or process all)",
        options=["All Pages"] + [f"Page {i+1} ({p.name})" for i, p in enumerate(doc_pages)],
    )

with col_run:
    st.write("")
    st.write("")
    run_ocr_btn = st.button("Run Ollama OCR", type="primary", disabled=not (is_online and has_model))

# Run OCR on click
if run_ocr_btn:
    pages_to_process = (
        doc_pages
        if selected_page_idx == "All Pages"
        else [doc_pages[int(selected_page_idx.split()[1]) - 1]]
    )

    ocr_results = []
    progress_bar = st.progress(0)

    for i, p_path in enumerate(pages_to_process):
        page_num = i + 1 if selected_page_idx == "All Pages" else int(selected_page_idx.split()[1])
        with st.spinner(f"Running Ollama OCR on {p_path.name}..."):
            try:
                res = run_ollama_ocr_page(
                    image_input=p_path,
                    page=page_num,
                    include_tables=include_tables,
                    timeout=60.0,
                )
                ocr_results.append(res)
            except Exception as e:
                st.error(f"OCR failed for {p_path.name}: {e}")
        progress_bar.progress((i + 1) / len(pages_to_process))

    if ocr_results:
        st.session_state[f"ocr_results_{doc_id}"] = ocr_results
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        last_ocr_file = CACHE_DIR / "last_ocr.json"
        last_ocr_file.write_text(
            json.dumps(ocr_results[0] if len(ocr_results) == 1 else ocr_results, indent=2),
            encoding="utf-8",
        )
        st.success(f"OCR complete! Results saved to `{last_ocr_file}`")
    else:
        st.error(OLLAMA_SETUP_MESSAGE)

# Display OCR outputs (raw model text and editable text)
cached_results = st.session_state.get(f"ocr_results_{doc_id}", [])

if cached_results:
    st.divider()
    st.subheader("OCR Results & Verification")

    editable_pages = []
    for idx, item in enumerate(cached_results):
        p_num = item.get("page", idx + 1)
        st.markdown(f"### Page {p_num}")

        col_raw, col_edit = st.columns([1, 1])

        with col_raw:
            st.markdown("**Raw Model Text (Pass 1 - `OCR:`):**")
            st.text_area(
                f"Raw Text (Page {p_num})",
                value=item.get("text", ""),
                height=250,
                disabled=True,
                key=f"raw_text_{doc_id}_{p_num}",
            )
            if item.get("table_text"):
                st.markdown("**Raw Table Recognition (`Table Recognition:`):**")
                st.text_area(
                    f"Raw Table (Page {p_num})",
                    value=item.get("table_text", ""),
                    height=150,
                    disabled=True,
                    key=f"raw_table_{doc_id}_{p_num}",
                )

        with col_edit:
            st.markdown("**Editable Page Text:**")
            initial_edit_text = item.get("combined_text") or item.get("text", "")
            edit_key = f"edited_text_{doc_id}_{p_num}"
            if edit_key not in st.session_state:
                st.session_state[edit_key] = initial_edit_text
            edited_text = st.text_area(
                f"Editable Text (Page {p_num})",
                height=430,
                key=edit_key,
            )
            st.session_state[f"page_text_{doc_id}_{p_num}"] = edited_text
            editable_pages.append(f"--- Page {p_num} ---\n{edited_text}")

    st.download_button(
        "Download Markdown",
        data="\n\n".join(editable_pages),
        file_name=f"{doc_id}.md",
        mime="text/markdown",
    )
    st.info("👉 Text is ready! Proceed to the **Extract** page to structure fields into JSON with Agnes AI.")
