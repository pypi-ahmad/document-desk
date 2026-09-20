"""Health Page - System Diagnostics and Service Health.

Verifies:
1. Ollama service status via GET /api/tags and confirms whether
   AuditAid/PaddleOCR-VL-1.6-0.9B is present.
2. Agnes AI ping with one word only if AGNESAI_API_KEY exists (never prints the key).
"""

import streamlit as st
import httpx

from src.config import (
    OLLAMA_HOST,
    OLLAMA_OCR_MODEL,
    AGNES_MODEL,
    AGNES_BASE_URL,
    is_agnes_key_set,
)
from src.agnes_client import get_llm_client
from src.ollama_ocr import OLLAMA_SETUP_MESSAGE, check_ollama_status

st.title("🩺 System Health & Connectivity")
st.write(
    "Checks the status of the local Ollama Vision-Language service "
    "and verifies Agnes AI API connectivity."
)

st.divider()

# ----------------- 1. Ollama Health Check -----------------
st.subheader("1. Local Ollama Service Status")
st.caption(f"Endpoint: `{OLLAMA_HOST}` | Expected OCR Model: `{OLLAMA_OCR_MODEL}`")

with st.spinner("Checking Ollama /api/tags..."):
    is_online, has_model, _status_msg, model_names = check_ollama_status()

col_ol1, col_ol2 = st.columns([1, 1])
with col_ol1:
    if is_online:
        st.success("✅ Ollama Service: **Online**")
    else:
        st.error("❌ Ollama Service: **Offline**")

with col_ol2:
    if has_model:
        st.success(f"✅ OCR Model: **`{OLLAMA_OCR_MODEL}` Present**")
    else:
        st.error(f"❌ OCR Model: **`{OLLAMA_OCR_MODEL}` Missing**")

if not is_online or not has_model:
    st.error(OLLAMA_SETUP_MESSAGE)

with st.expander("View Available Ollama Models", expanded=False):
    if model_names:
        for m in model_names:
            st.markdown(f"- `{m}`")
    else:
        st.info("No models discovered or Ollama is not running.")

st.divider()

# ----------------- 2. Agnes AI Connectivity Check -----------------
st.subheader("2. Agnes AI Connectivity")
st.caption(f"Base URL: `{AGNES_BASE_URL}` | Model: `{AGNES_MODEL}`")

key_configured = is_agnes_key_set()

if key_configured:
    st.success("✅ `AGNESAI_API_KEY` is present in the environment.")
    
    col_ping, _ = st.columns([1, 2])
    with col_ping:
        ping_btn = st.button("Ping Agnes AI (1-word ping)", type="primary")

    if ping_btn:
        with st.spinner("Pinging Agnes AI with one word..."):
            try:
                client = get_llm_client()
                response = client.chat.completions.create(
                    model=AGNES_MODEL,
                    messages=[{"role": "user", "content": "ping"}],
                    max_tokens=10,
                )
                one_word_reply = response.choices[0].message.content or ""
                st.success(f"Agnes AI responded: **`{one_word_reply.strip()}`**")
            except Exception as e:
                st.error(f"Agnes AI ping failed: {e}")
                st.info("Please verify your `AGNESAI_API_KEY` and network connection.")
else:
    st.warning(
        "⚠️ `AGNESAI_API_KEY` is not configured in the environment or `.env`.\n\n"
        "Please configure `AGNESAI_API_KEY` in your environment or `.env` file."
    )
