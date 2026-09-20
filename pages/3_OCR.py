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
    FIXTURES_DIR,
    CACHE_DIR,
    OLLAMA_OCR_MODEL,
)
from src.ollama_ocr import check_ollama_status, run_ollama_ocr_page
from src.pdf_pages import render_pdf_pages, sanitize_file_id

st.title("👁️ Local Vision-Language OCR")
st.write(
    f"Performs local OCR using Ollama model **`{OLLAMA_OCR_MODEL}`** "
    f"at temperature 0 with task prefixes."
)

# Ollama status check banner
is_online, has_model, status_msg, _ = check_ollama_status()
if not is_online or not has_model:
    st.error(
        f"⚠️ Action Required: **start Ollama Desktop, then ollama pull {OLLAMA_OCR_MODEL}**"
    )

st.divider()

# Select document / file_id
file_dirs = [d for d in PAGES_DIR.glob("*") if d.is_dir() and list(d.glob("page-*.png"))]
file_options = [d.name for d in file_dirs]

# Add fixture option if available
fixture_page = FIXTURES_DIR / "sample_page.png"
if fixture_page.exists() and "sample_page" not in file_options:
    file_options.insert(0, "sample_page (fixture)")

current_file_id = st.session_state.get("current_file_id", file_options[0] if file_options else None)

selected_file_id = st.selectbox(
    "Select Document to OCR",
    options=file_options if file_options else ["No rendered documents available"],
    index=file_options.index(current_file_id) if (file_options and current_file_id in file_options) else 0,
)

if not file_options or selected_file_id == "No rendered documents available":
    st.info("No rendered pages found. Upload a document on the **Upload** page first.")
    st.stop()

# Determine page paths
if "fixture" in selected_file_id:
    doc_pages = [fixture_page]
    doc_id = "sample_page"
else:
    doc_id = selected_file_id
    doc_pages = sorted(list((PAGES_DIR / doc_id).glob("page-*.png")))

st.subheader(f"Page Gallery ({len(doc_pages)} page(s))")

# Page gallery display
cols = st.columns(min(len(doc_pages), 4))
for idx, page_path in enumerate(doc_pages):
    with cols[idx % len(cols)]:
        st.image(str(page_path), caption=f"Page {idx + 1}: {page_path.name}", use_container_width=True)

st.divider()

# OCR Execution Controls
col_opts, col_run = st.columns([2, 1])
with col_opts:
    include_tables = st.checkbox(
        "Enable secondary Table Recognition pass (`Table Recognition:`)",
        value=False,
        help="Runs an additional pass specifically tuned for complex tables.",
    )
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

    # Save to session state and cache
    st.session_state[f"ocr_results_{doc_id}"] = ocr_results
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    last_ocr_file = CACHE_DIR / "last_ocr.json"
    last_ocr_file.write_text(
        json.dumps(ocr_results[0] if len(ocr_results) == 1 else ocr_results, indent=2),
        encoding="utf-8",
    )
    st.success(f"OCR complete! Results saved to `{last_ocr_file}`")

# Display OCR outputs (raw model text and editable text)
cached_results = st.session_state.get(f"ocr_results_{doc_id}", [])
if not cached_results and (CACHE_DIR / "last_ocr.json").exists():
    try:
        loaded = json.loads((CACHE_DIR / "last_ocr.json").read_text(encoding="utf-8"))
        cached_results = [loaded] if isinstance(loaded, dict) else loaded
    except Exception:
        cached_results = []

if cached_results:
    st.divider()
    st.subheader("OCR Results & Verification")

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
            edited_text = st.text_area(
                f"Editable Text (Page {p_num})",
                value=st.session_state.get(f"edited_text_{doc_id}_{p_num}", initial_edit_text),
                height=430,
                key=f"edited_text_{doc_id}_{p_num}",
            )
            st.session_state[f"page_text_{doc_id}_{p_num}"] = edited_text

    st.info("👉 Text is ready! Proceed to the **Extract** page to structure fields into JSON with Agnes AI.")
