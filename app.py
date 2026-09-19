"""Document Desk - Windows-Native Document Intelligence Workstation.

Streamlit application entry point featuring:
- Provider discovery with hidden missing providers (Agnes AI, OpenAI, Google Gemini).
- Multi-page navigation: Upload, Extract, Ask, Compare.
- Pure-Python text-first processing, embedded Qdrant vector search, and field-level diffs.
"""

import streamlit as st
from src.config import (
    AGNES_MODEL,
    is_agnes_key_set,
    get_available_providers,
    QDRANT_PATH,
)

st.set_page_config(
    page_title="Document Desk",
    page_icon="📑",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----------------- Shared Sidebar -----------------
with st.sidebar:
    st.title("📑 Document Desk")
    st.caption("Windows-Native Document Intelligence")
    st.divider()

    st.subheader("⚙️ LLM Provider & Model")
    providers = get_available_providers()
    provider_names = list(providers.keys())

    if not provider_names:
        provider_names = ["Agnes AI"]

    selected_provider_name = st.selectbox(
        "Select Provider",
        options=provider_names,
        index=0,
        help="Providers are displayed only if their environment variables are configured. Missing providers are hidden.",
    )

    current_provider_info = providers.get(
        selected_provider_name,
        {"models": [AGNES_MODEL], "default_model": AGNES_MODEL},
    )
    available_models = current_provider_info.get("models", [AGNES_MODEL])
    default_model = current_provider_info.get("default_model", available_models[0])

    default_index = 0
    if default_model in available_models:
        default_index = available_models.index(default_model)

    selected_model = st.selectbox(
        "Select Model",
        options=available_models,
        index=default_index,
    )

    st.session_state["selected_provider"] = selected_provider_name
    st.session_state["selected_model"] = selected_model

    st.divider()

    # Environment and Storage Status
    st.subheader("🔒 Environment Status")
    if is_agnes_key_set():
        st.success("`AGNESAI_API_KEY` is configured.")
    else:
        st.error(
            "⚠️ `AGNESAI_API_KEY` is not set in the environment or `.env`."
        )

    st.caption(f"Embedded Qdrant: `{QDRANT_PATH}` (single-process local storage)")


# ----------------- Multi-Page Navigation -----------------
upload_page = st.Page(
    "pages/1_Upload.py",
    title="Upload",
    icon="📤",
    default=True,
)
extract_page = st.Page(
    "pages/2_Extract.py",
    title="Extract",
    icon="🔬",
)
ask_page = st.Page(
    "pages/3_Ask.py",
    title="Ask",
    icon="💬",
)
compare_page = st.Page(
    "pages/4_Compare.py",
    title="Compare",
    icon="⚖️",
)

pg = st.navigation(
    [upload_page, extract_page, ask_page, compare_page],
    position="sidebar",
)

pg.run()
