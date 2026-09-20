"""Headless check for the single-file Streamlit workflow state."""

from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "data" / "fixtures" / "text.pdf"


def open_page(page: str, extracted: bool = False, answered: bool = False) -> AppTest:
    """Open one Streamlit page with deterministic active-document state.

    Args:
        page: Repository-relative Streamlit page path to load.
        extracted: Whether to seed completed extraction state.
        answered: Whether to seed an Ask result in addition to extraction state.

    Returns:
        Executed Streamlit app test instance for page assertions.
    """
    app = AppTest.from_file(ROOT / "app.py", default_timeout=20).run()
    app.session_state["current_file_id"] = "text"
    app.session_state["current_file_path"] = str(FIXTURE)
    app.session_state["current_filename"] = FIXTURE.name
    app.session_state["inspect_text"] = {
        "pdf_type": "text_based",
        "confidence": 1.0,
        "page_count": 1,
        "markdown": "Document Desk workflow fixture text.",
        "route": "native",
        "route_reason": "Text-based PDF has usable native Markdown, so OCR is skipped.",
    }
    if extracted:
        app.session_state["extract_data_text"] = {
            "title": "Fixture",
            "doc_type": "Test",
            "fields": [],
            "tables": [],
            "summary": "Fixture",
            "citations": [],
        }
        app.session_state["source_markdown_text"] = "Fixture"
    if answered:
        app.session_state["ask_data_text"] = {
            "file_id": "text",
            "question": "Fixture?",
            "answer": "Fixture [Page 1]",
            "chunks": [{"page": 1, "text": "Fixture", "score": 1.0}],
        }
    return app.switch_page(page).run(timeout=20)


if __name__ == "__main__":
    assert FIXTURE.is_file()

    inspect_app = open_page("pages/3_Inspect.py")
    assert not inspect_app.exception
    assert any("Route reason:" in item.value for item in inspect_app.info)
    assert len(inspect_app.get("download_button")) == 1

    ocr_app = open_page("pages/3_OCR.py")
    assert not ocr_app.exception
    assert any("OCR skipped" in item.value for item in ocr_app.success)

    ask_locked = open_page("pages/5_Ask.py")
    assert not ask_locked.exception
    assert ask_locked.button[0].disabled

    ask_ready = open_page("pages/5_Ask.py", extracted=True)
    assert not ask_ready.exception
    assert not ask_ready.button[0].disabled

    extract_ready = open_page("pages/4_Extract.py", extracted=True)
    assert not extract_ready.exception
    assert len(extract_ready.get("download_button")) == 2

    ask_export = open_page("pages/5_Ask.py", extracted=True, answered=True)
    assert not ask_export.exception
    assert len(ask_export.get("download_button")) == 1

    print("PASS: Upload file_id gates Inspect, OCR, Extract, and Ask")
