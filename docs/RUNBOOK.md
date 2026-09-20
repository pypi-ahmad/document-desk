# Document Desk operations runbook

Use this runbook to operate and recover a local Document Desk instance on
Windows 11. For first-time setup, use [developer onboarding](ONBOARDING.md).
For code ownership and APIs, use the [developer guide](DEVELOPER_GUIDE.md).

## Operating constraints

- Run native Windows only; do not use WSL2 or Docker.
- Use one Streamlit or Qdrant-writing script process at a time.
- Keep `.env`, `.venv`, and `data/` local. They are intentionally gitignored.
- Do not log or share `AGNESAI_API_KEY`.

## Start and stop

Double-click `run.cmd` in the repository root. If `.env` is absent, the script
copies `.env.example`, opens Notepad, and exits. Save configuration, then run
the script again to create the environment, install dependencies, and start
Streamlit.

The service listens at `http://localhost:8592`. Stop it with `Ctrl+C`
in the terminal that started it. Do not start another instance while one is
using `data/qdrant`.

## Standard document workflow

1. **Upload** a PDF or image. This establishes the active `file_id`.
2. **Inspect** the PDF type, confidence, route, route reason, and Markdown.
3. **OCR** only when the route is `ollama`; native documents skip it.
4. **Extract** sends page text to Agnes and automatically indexes chunks for
   the active `file_id`.
5. **Ask** becomes available after Extract and retrieves only that file's
   chunks.
6. **Compare** selects two available file IDs and shows field-name and
   field-value differences.

## Service health and recovery

### Ollama offline or model missing

Health and OCR show the following exact recovery instruction:

```text
start Ollama, then: ollama pull AuditAid/PaddleOCR-VL-1.6-0.9B
```

Start Ollama, then run:

```powershell
ollama pull AuditAid/PaddleOCR-VL-1.6-0.9B
```

The Health page checks `http://127.0.0.1:11434/api/tags`. OCR uses `OCR:` and,
when selected, `Table Recognition:` at temperature `0`.

### Agnes key missing or rejected

Extract, Ask, and Compare require `AGNESAI_API_KEY`. Set it in the Windows user
environment or the ignored `.env` file. Restart the launcher after changing the
environment. The key is never displayed by Health.

HTTP 429 responses are retried with backoff by `src/agnes_client.py`. HTTP 401
or 403 means the configured key needs attention; do not paste it into logs or
issues.

### Qdrant is locked

Embedded Qdrant has a single-process storage lock. Stop Streamlit before
running a smoke that writes to `data/qdrant`, or wait for indexing to finish.
If a local process ended unexpectedly, close only the known Document Desk
Python process before retrying. Do not broadly terminate unrelated Python work.

## Smoke-test matrix

Run commands from the repository root with `.venv\Scripts\python.exe`.

| Command | Prerequisites | Output or coverage |
| --- | --- | --- |
| `scripts\smoke_inspect.py` | Local dependencies | Native PDF inspection and `data/cache/last_inspect.json`. |
| `scripts\smoke_workflow.py` | Local dependencies | Streamlit active-file flow, OCR skip, Ask gate, and exports. |
| `scripts\smoke_ocr.py` | Ollama and model | Fixture OCR and `data/cache/last_ocr.json`. |
| `scripts\smoke_ollama_route.py` | Ollama and model | Forced OCR route, pypdfium2 rendering, and OCR cache. |
| `scripts\smoke_extract.py` | Agnes key plus cached text | Extraction, Qdrant retrieval, Ask, and extract/ask caches. |
| `scripts\smoke_extract_ask.py` | Agnes key; Ollama if no OCR cache | OCR text through Extract, Ask, and Compare. |

Example local-only checks:

```powershell
.venv\Scripts\python.exe -c "import app, src.pdf_inspect, src.ollama_ocr, src.extract, src.store"
.venv\Scripts\python.exe scripts\smoke_inspect.py
.venv\Scripts\python.exe scripts\smoke_workflow.py
```

## Data recovery expectations

`data/` is working state, not a source-controlled backup. It contains uploads,
rendered PNGs, caches, fixtures, and Qdrant files. Preserve it when you need
local history; regenerate it through the app or smokes when it is safe to do so.
