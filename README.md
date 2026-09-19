# Document Desk

Document Desk is a Windows-native Streamlit application for parsing local documents, extracting text, structuring fields through Agnes AI, and querying or comparing files with an embedded vector store.

## Features

- Page text extraction: PyMuPDF reads text from digital PDFs page by page. If a page has fewer than 20 characters of text, the app flags a warning explaining that vision requires a public image URL and that v1 is text-first. The app sends whatever text exists across the document and never formats local file paths as image URLs.
- Structured extraction: `agnes-3.0-flash` converts document text into a JSON object with title, document type, fields, tables, summary, and citations. The client retries on HTTP 429 rate limits with exponential backoff.
- Provider discovery: The sidebar discovers available providers based on configured environment variables and hides missing ones. When present, options include Agnes AI, OpenAI Compatible (`gpt-5.6-luna`, `gpt-5.6-terra`), and Google Gemini (`gemini-3.5-flash-lite`, `gemini-3.7-flash`).
- Streamlit interface: Two-page navigation separating document processing from field-level comparison. Includes editable field tables through `st.data_editor` and raw JSON views.
- Semantic search and Q&A: Text chunks are stored in an embedded Qdrant collection (`documents`) located at `data/qdrant/`. Queries filter by `file_id` and return answers that cite page numbers directly (such as `[Page 1]`). If no chunks match, the interface displays an empty retrieval message.
- Field-level comparison: Compares two document IDs by running a Python set difference across field names (`common_fields`, `only_in_a`, `only_in_b`), then calling the model to compare values across shared fields.
- Key handling: Reads `AGNESAI_API_KEY` from the Windows user environment or `.env`. The key is never logged or shown in the UI.

## Storage layout

Local files are stored under `data/`:

| Path | Purpose |
| :--- | :--- |
| `data/uploads/` | Uploaded PDFs and images. |
| `data/pages/` | PNG previews of pages with low or empty text. |
| `data/fixtures/` | Sample files, such as `sample.pdf`. |
| `data/cache/` | Cached JSON results, including `last_extract.json`. |
| `data/qdrant/` | Embedded Qdrant storage for the `documents` collection, storing `{file_id, page, text}`. |

## Embedded Qdrant single-process rule

Embedded Qdrant stores its database directly on disk in `data/qdrant/` using SQLite and file locking via portalocker.

Only one process can access `data/qdrant/` at a time. While the Streamlit app is running, do not run background CLI scripts that write to `data/qdrant/`. The application opens and closes client connections around each read and write to reduce lock duration.

## How to run

### Prerequisites
- Windows 11 without WSL2 or Docker.
- Python 3.11 or newer, accessible via `py -3`.
- An `AGNESAI_API_KEY` set in your user environment or in `.env`.

### Start with run.cmd
Double-click `run.cmd` at the repository root. The script performs four tasks:
1. Copies `.env.example` to `.env` and opens Notepad if `.env` does not exist.
2. Creates `.venv` using `py -3 -m venv .venv` if missing.
3. Installs dependencies from `requirements.txt`.
4. Starts the application with `streamlit run app.py`.

### Start from the command line
```powershell
cd D:\AI\Github\document-desk
.venv\Scripts\streamlit run app.py
```

## Application pages

| Page | File | Purpose |
| :--- | :--- | :--- |
| Document Desk | `pages/1_Document_Desk.py` | Ingests documents, extracts per-page text, extracts structured JSON, and answers questions with page citations via Qdrant. |
| Compare Versions | `pages/2_Compare.py` | Computes Python set differences on field names and asks the model to compare field values. |

## Environment variables

| Variable | Purpose | Default |
| :--- | :--- | :--- |
| `AGNESAI_API_KEY` | Primary API key for Agnes AI. Required. | None |
| `AGNES_BASE_URL` | Base URL for Agnes AI. | `https://apihub.agnes-ai.com/v1` |
| `OPENAI_API_KEY` | Optional API key for OpenAI-compatible endpoints. | None |
| `OPENAI_BASE_URL` | Optional base URL for OpenAI-compatible endpoints. | None |
| `GOOGLE_API_KEY` | Optional API key for Google Gemini models. | None |

User-facing errors reference `AGNESAI_API_KEY`. Missing optional providers are hidden from the sidebar.

## Smoke tests

Run the test suite using Python from the virtual environment:

```cmd
.venv\Scripts\python.exe tests/smoke_extract.py
.venv\Scripts\python.exe tests/smoke_ask_fixture.py
.venv\Scripts\python.exe tests/smoke_compare.py
```

## Documentation

- [System architecture](file:///D:/AI/Github/document-desk/docs/ARCHITECTURE.md): Components, data flow, payload schemas, and storage.
- [Operations runbook](file:///D:/AI/Github/document-desk/docs/RUNBOOK.md): Setup, configuration, workflows, and troubleshooting.
- [Implementation status](file:///D:/AI/Github/document-desk/STATUS.md): Checklist and test results.
