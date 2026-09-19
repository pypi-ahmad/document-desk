# Document Desk runbook

This runbook covers installation, configuration, standard operations, testing, and troubleshooting for Document Desk on Windows 11.

## System requirements

- Windows 11 without WSL2 or Docker.
- Python 3.11 or newer, accessible via `py -3`.
- An `AGNESAI_API_KEY` with access to `https://apihub.agnes-ai.com/v1`.
- Optional: `OPENAI_API_KEY` and `OPENAI_BASE_URL` or `GOOGLE_API_KEY` for alternate providers.

## Environment setup

### Configure the Agnes AI API key
Set `AGNESAI_API_KEY` in your Windows user profile using PowerShell:

```powershell
[System.Environment]::SetEnvironmentVariable('AGNESAI_API_KEY', 'your-secret-key-here', 'User')
```

Alternatively, add it to `.env` in the repository root:

```ini
AGNESAI_API_KEY=your-secret-key-here
AGNES_BASE_URL=https://apihub.agnes-ai.com/v1
```

Optional providers can be configured in `.env` if desired:
```ini
OPENAI_API_KEY=your-openai-key
OPENAI_BASE_URL=https://api.openai.com/v1
GOOGLE_API_KEY=your-gemini-key
```

Do not commit `.env` or write API keys into source files. The `.gitignore` file excludes `.env`.

## Starting the application

### Launch with run.cmd
Double-click `run.cmd` in Windows Explorer or run it from a terminal. The script will:
1. Create `.env` from `.env.example` and open Notepad if `.env` is missing, then exit.
2. Create `.venv` using `py -3 -m venv .venv` if needed.
3. Install packages listed in `requirements.txt`.
4. Run `streamlit run app.py`.

The app runs locally at `http://localhost:8501`.

## Workflows

### 1. Document ingestion and text extraction
Open the Document Desk page (`pages/1_Document_Desk.py`). Upload a PDF or image file, or select an existing document from `data/uploads/` or `data/fixtures/sample.pdf`. PyMuPDF extracts text per page. If a page has fewer than 20 characters of text, the app shows a warning that vision models require a public image URL and that v1 is text-first.

### 2. Structured data extraction
Select an active provider and model in the sidebar. Click "Run Structured Extraction" to generate document title, document type, fields, tables, summary, and citations. You can edit the fields and tables directly in the interface or download the result as JSON.

### 3. Ask questions with page citations
Click "Index / Re-Index Document Chunks" to store text in embedded Qdrant (`path="data/qdrant"`). Submit a question to query chunks filtered by `file_id`. The response answers strictly from context and cites specific pages in brackets, such as `[Page 1]`. If no chunks match, the app displays an empty retrieval message.

### 4. Compare document versions
Open the Compare Versions page (`pages/2_Compare.py`). Select Document A and Document B. Click "Compare Versions at Field Level". The page calculates a Python set difference of field names, then asks the model to compare the values of shared fields and output a comparison table.

## Automated smoke tests

Run the smoke tests directly from the virtual environment:

### Extraction smoke test
```cmd
.venv\Scripts\python.exe tests/smoke_extract.py
```
Verifies fixture generation, PyMuPDF extraction, JSON parsing with `agnes-3.0-flash`, schema conformance, and caching to `data/cache/last_extract.json`.

### Qdrant and QA smoke test
```cmd
.venv\Scripts\python.exe tests/smoke_ask_fixture.py
```
Verifies chunk indexing into embedded Qdrant with payload `{file_id, page, text}`, filtered retrieval by `file_id`, and answer generation with `[Page 1]` citations.

### Field comparison smoke test
```cmd
.venv\Scripts\python.exe tests/smoke_compare.py
```
Verifies Python-side field set difference calculations and calls the model for field-level diff reporting.

## Troubleshooting

### Missing AGNESAI_API_KEY
If you see an error indicating `AGNESAI_API_KEY is not set in the environment`:
1. Check that the variable exists in your Windows environment or `.env` file.
2. If setting via `setx`, restart your terminal session for the change to take effect.

### Authentication errors (HTTP 401 or 403)
Verify that your API key is valid and active on the Agnes AI console.

### Rate limits (HTTP 429)
The client in `src/agnes_client.py` retries automatically with exponential backoff. If rate limits continue, pause operations briefly before submitting further requests.

### Database locked in Qdrant
Embedded Qdrant locks its SQLite files in `data/qdrant/` during use.
1. Do not run CLI test scripts while Streamlit is performing an indexing operation.
2. If an earlier process terminated unexpectedly and held the lock, close remaining Python processes:
   ```powershell
   Get-Process python | Stop-Process -Force
   ```
3. Restart `run.cmd`.

### Empty text on scanned pages
If a page has fewer than 20 characters of extractable text, PyMuPDF notes the empty text and displays a warning. The application still sends whatever text exists across the rest of the document. If you have a public URL for an image-only document, you may paste it into the optional URL field.
