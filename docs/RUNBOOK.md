# Document Desk Runbook

This runbook covers installation, configuration, standard operations, testing, and troubleshooting for Document Desk on Windows 11.

## System Requirements

- Native Windows 11 without WSL2 or Docker.
- Python 3.11 or newer, accessible via `py -3`.
- Ollama Desktop running on `http://127.0.0.1:11434`.
- Model `AuditAid/PaddleOCR-VL-1.6-0.9B` installed in Ollama.
- An `AGNESAI_API_KEY` with access to `https://apihub.agnes-ai.com/v1`.
- Optional: `OPENAI_API_KEY` and `OPENAI_BASE_URL` or `GOOGLE_API_KEY` for alternate providers.

## Environment & Service Setup

### 1. Set Up Ollama Local Vision-Language Model

Open PowerShell and pull the model:
```powershell
ollama pull AuditAid/PaddleOCR-VL-1.6-0.9B
```
Verify the model is running:
```powershell
ollama run AuditAid/PaddleOCR-VL-1.6-0.9B "OCR:"
```

### 2. Configure the Agnes AI API Key

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

## Starting the Application

### Launch with run.cmd
Double-click `run.cmd` in Windows Explorer or run it from a terminal. The script will:
1. Create `.env` from `.env.example` and open Notepad if `.env` is missing, then exit.
2. Create `.venv` using `py -3 -m venv .venv` if needed.
3. Install packages listed in `requirements.txt`.
4. Run `streamlit run app.py`.

The app runs locally at `http://localhost:8501`.

## Workflows

### 1. Document Ingestion & Local OCR
Open the Upload page (`pages/1_Upload.py`).
- Displays Ollama status. If Ollama is offline or model missing, an informative banner appears: `start Ollama Desktop, then ollama pull AuditAid/PaddleOCR-VL-1.6-0.9B`. The app does not crash.
- Upload a PDF or image file (or select an existing document).
- For scanned pages or image uploads, `pypdfium2` renders page PNGs to `data/pages/<file_id>/page_<n>.png` and passes them as local image attachments to Ollama `AuditAid/PaddleOCR-VL-1.6-0.9B`.
- Default pass runs prompt prefix `OCR:`.
- If table extraction is enabled, a secondary pass runs `Table Recognition:`.

### 2. Structured Data Extraction
Open the Extract page (`pages/2_Extract.py`). Select an active provider and model in the sidebar. Click "Run Agnes Extraction" to generate document title, document type, fields, tables, summary, and citations. You can view or edit the fields dataframe directly in the interface or download the result as JSON.

### 3. Ask Questions with Page Citations
Open the Ask page (`pages/3_Ask.py`). Click "Index / Re-Index Document into Qdrant" to store text in embedded Qdrant (`path="data/qdrant"`). Submit a question to query chunks filtered by `file_id`. The response answers strictly from context and cites specific pages in brackets, such as `[Page 1]`. If no chunks match, the app displays an empty retrieval message.

### 4. Compare Document Versions
Open the Compare page (`pages/4_Compare.py`). Select Document A and Document B. Click "Compare Versions at Field Level". The page calculates a Python set difference of field names, then asks the model to compare the values of shared fields and output a comparison table.

## Automated Smoke Tests

Run the smoke tests directly from the virtual environment:

### 1. Smoke OCR on Fixture Page + Agnes Extraction
```cmd
.venv\Scripts\python.exe tests/smoke_ocr_agnes.py
```
Validates fixture PNG generation, Ollama VL dual-pass OCR (`OCR:` and `Table Recognition:`), and structured extraction with `agnes-3.0-flash`.

### 2. End-to-End Pipeline Smoke Test
```cmd
.venv\Scripts\python.exe tests/smoke_pipeline.py
```
Validates `pdf-inspector` classification, `pypdfium2` rendering, Ollama VL OCR, Agnes AI structuring, embedded Qdrant chunk indexing/retrieval, and document diffing.

### 3. Extraction Smoke Test
```cmd
.venv\Scripts\python.exe tests/smoke_extract.py
```
Verifies fixture generation, PyMuPDF extraction, JSON parsing with `agnes-3.0-flash`, schema conformance, and caching to `data/cache/last_extract.json`.

### 4. Qdrant and QA Smoke Test
```cmd
.venv\Scripts\python.exe tests/smoke_ask_fixture.py
```
Verifies chunk indexing into embedded Qdrant with payload `{file_id, page, text}`, filtered retrieval by `file_id`, and answer generation with `[Page 1]` citations.

### 5. Field Comparison Smoke Test
```cmd
.venv\Scripts\python.exe tests/smoke_compare.py
```
Verifies Python-side field set difference calculations and calls the model for field-level diff reporting.

## Troubleshooting

### Ollama Offline or Model Missing
If the Upload page displays:
`start Ollama Desktop, then ollama pull AuditAid/PaddleOCR-VL-1.6-0.9B`:
1. Ensure the Ollama service is active:
   ```powershell
   Get-Process ollama*
   ```
2. Pull the required model:
   ```powershell
   ollama pull AuditAid/PaddleOCR-VL-1.6-0.9B
   ```

### Missing AGNESAI_API_KEY
If you see an error indicating `AGNESAI_API_KEY is not set in the environment`:
1. Check that the variable exists in your Windows environment or `.env` file.
2. If setting via `setx`, restart your terminal session for the change to take effect.

### Authentication Errors (HTTP 401 or 403)
Verify that your API key is valid and active on the Agnes AI console.

### Rate Limits (HTTP 429)
The client in `src/agnes_client.py` retries automatically with exponential backoff.

### Database Locked in Qdrant
Embedded Qdrant locks its SQLite files in `data/qdrant/` during use.
1. Do not run CLI test scripts while Streamlit is performing an indexing operation.
2. If an earlier process terminated unexpectedly and held the lock, close remaining Python processes:
   ```powershell
   Stop-Process -Name "python" -Force -ErrorAction SilentlyContinue
   ```
