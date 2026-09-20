# Document Desk

Document Desk is a Windows-native Streamlit application for parsing local documents, extracting text with local Vision-Language OCR, structuring fields through Agnes AI, and querying or comparing files with an embedded vector store.

## Features

- **Local OCR & Page Parsing**: Local Vision-Language inference via Ollama using model `AuditAid/PaddleOCR-VL-1.6-0.9B` (`http://127.0.0.1:11434`).
  - Pull and run:
    ```bash
    ollama pull AuditAid/PaddleOCR-VL-1.6-0.9B
    ollama run AuditAid/PaddleOCR-VL-1.6-0.9B
    ```
  - Standard VL task prefixes: `OCR:`, `Table Recognition:`, `Formula Recognition:`, `Chart Recognition:`, `Seal Recognition:`, `Spotting:`.
  - Default pass: `OCR:`. Optional second pass: `Table Recognition:` when table extraction is enabled.
  - Page images are rendered locally with `pypdfium2` and passed as local image attachments (path or bytes) to Ollama.
  - Non-crashing health checks: If Ollama is offline or the model is missing, the Upload page displays: `start Ollama Desktop, then ollama pull AuditAid/PaddleOCR-VL-1.6-0.9B`.
- **Structured Extraction**: `agnes-3.0-flash` (via official `openai` Python SDK at `https://apihub.agnes-ai.com/v1`) converts document text into structured JSON:
  ```json
  {
    "title": "string",
    "doc_type": "string",
    "fields": [{"name": "string", "value": "any", "page": 1}],
    "tables": [{"title": "string", "headers": ["..."], "rows": [["..."]]}],
    "summary": "string",
    "citations": [{"claim": "string", "page": 1}]
  }
  ```
  Client retries on HTTP 429 rate limits with exponential backoff.
- **Strict Image URL Policy**: Local disk paths are never sent to Agnes as public image URLs.
- **Provider Discovery**: Sidebar discovers available providers based on configured environment variables and hides missing ones. When present, options include Agnes AI, OpenAI Compatible (`gpt-5.6-luna`, `gpt-5.6-terra`), and Google Gemini (`gemini-3.5-flash-lite`, `gemini-3.7-flash`).
- **Streamlit Interface**: Clean 4-page navigation separating ingestion, structured extraction, vector Q&A, and field comparison.
- **Semantic Search and Q&A**: Text chunks are stored in an embedded Qdrant collection (`documents`) located at `data/qdrant/`. Queries filter by `file_id` and return answers that cite page numbers directly (e.g. `[Page 1]`). If retrieval is empty, it reports so explicitly.
- **Field-Level Comparison**: Compares two document versions with a Python set difference across field names (`common_fields`, `only_in_a`, `only_in_b`), then prompts the LLM to compare values across shared fields.
- **Key Handling**: Reads `AGNESAI_API_KEY` from the Windows user environment or `.env`. The key is never logged or written to disk or git. Every user-facing error message references `AGNESAI_API_KEY`.

## Storage Layout

Local files are stored under `data/`:

| Path | Purpose |
| :--- | :--- |
| `data/uploads/` | Uploaded PDFs and images. |
| `data/pages/` | Locally rendered page PNGs (e.g., `data/pages/<file_id>/page_<n>.png`). |
| `data/fixtures/` | Sample files, such as `sample.pdf`. |
| `data/cache/` | Cached JSON results, including `last_extract.json`. |
| `data/qdrant/` | Embedded Qdrant storage for the `documents` collection, storing `{file_id, page, text}`. |

## Embedded Qdrant Single-Process Rule

Embedded Qdrant stores its database directly on disk in `data/qdrant/` using SQLite and file locking via portalocker.

Only one process can access `data/qdrant/` at a time. While the Streamlit app is running, do not run background CLI scripts that write to `data/qdrant/`. The application opens and closes client connections around each read and write to prevent lingering locks.

## How to Run

### Prerequisites
- Native Windows 11 without WSL2 or Docker.
- Python 3.11 or newer, accessible via `py -3`.
- Ollama Desktop running with `AuditAid/PaddleOCR-VL-1.6-0.9B`:
  ```bash
  ollama pull AuditAid/PaddleOCR-VL-1.6-0.9B
  ```
- An `AGNESAI_API_KEY` set in your user environment or in `.env`.

### Start with run.cmd
Double-click `run.cmd` at the repository root. The script performs:
1. Copies `.env.example` to `.env` and opens Notepad if `.env` does not exist.
2. Creates `.venv` using `py -3 -m venv .venv` if missing.
3. Installs dependencies from `requirements.txt`.
4. Starts the application with `streamlit run app.py`.

### Start from the Command Line
```powershell
cd D:\AI\Github\document-desk
.venv\Scripts\streamlit run app.py
```

## Application Pages

| Page | File | Purpose |
| :--- | :--- | :--- |
| **Upload** | `pages/1_Upload.py` | Ingests documents, checks Ollama status, renders page PNGs, runs Ollama VL OCR (`OCR:` and `Table Recognition:`), or extracts native text via PyMuPDF. |
| **Extract** | `pages/2_Extract.py` | Produces structured JSON (fields, tables, summary, citations) via `agnes-3.0-flash` and displays an editable fields dataframe. |
| **Ask** | `pages/3_Ask.py` | Indexes chunks into embedded Qdrant with payload `{file_id, page, text}` and answers questions strictly citing page numbers. |
| **Compare** | `pages/4_Compare.py` | Computes Python set differences on field names and asks the model to diff field values. |

## Environment Variables

| Variable | Purpose | Default |
| :--- | :--- | :--- |
| `AGNESAI_API_KEY` | Primary API key for Agnes AI. Required. | None |
| `AGNES_BASE_URL` | Base URL for Agnes AI. | `https://apihub.agnes-ai.com/v1` |
| `OPENAI_API_KEY` | Optional API key for OpenAI-compatible endpoints. | None |
| `OPENAI_BASE_URL` | Optional base URL for OpenAI-compatible endpoints. | None |
| `GOOGLE_API_KEY` | Optional API key for Google Gemini models. | None |

User-facing errors reference `AGNESAI_API_KEY`. Missing optional providers are hidden from the sidebar.

## Smoke Tests

Run the test suite using Python from the virtual environment:

```cmd
.venv\Scripts\python.exe tests/smoke_ocr_agnes.py
.venv\Scripts\python.exe tests/smoke_extract.py
.venv\Scripts\python.exe tests/smoke_ask_fixture.py
.venv\Scripts\python.exe tests/smoke_compare.py
.venv\Scripts\python.exe tests/smoke_pipeline.py
```

## Documentation

- [System architecture](file:///D:/AI/Github/document-desk/docs/ARCHITECTURE.md): Components, data flow, payload schemas, and storage.
- [Operations runbook](file:///D:/AI/Github/document-desk/docs/RUNBOOK.md): Setup, configuration, workflows, and troubleshooting.
- [Implementation status](file:///D:/AI/Github/document-desk/STATUS.md): Checklist and test results.

## License

This project is licensed under the terms of the [MIT License](LICENSE).
