# Developer onboarding

Use this guide to get from a fresh checkout to a safe first local run. For the
full system reference, see the [developer guide](DEVELOPER_GUIDE.md).

## 1. Prepare the machine

Document Desk runs on native Windows 11. Install Python so `py -3` works in
PowerShell or Command Prompt. Ollama is needed only for OCR-routed documents;
Agnes credentials are needed for Extract, Ask, and Compare.

Pull the local OCR model before processing scanned PDFs or images:

```powershell
ollama pull AuditAid/PaddleOCR-VL-1.6-0.9B
```

Keep Ollama running at `http://127.0.0.1:11434` when using OCR.

## 2. Configure secrets safely

Double-click `run.cmd` from the repository root. On its first run it copies
`.env.example` to `.env`, opens Notepad, and exits so you can configure it.

Set `AGNESAI_API_KEY` if you will use Agnes-backed features. The supported
names are already present in `.env.example`:

```dotenv
AGNESAI_API_KEY=
AGNES_BASE_URL=https://apihub.agnes-ai.com/v1
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_OCR_MODEL=AuditAid/PaddleOCR-VL-1.6-0.9B
```

Do not commit `.env`. The key name is `AGNESAI_API_KEY`, not `AGNES_API_KEY`.

## 3. Start the app

After saving `.env`, double-click `run.cmd` again. It creates `.venv` when
needed, installs `requirements.txt`, and starts Streamlit.

Open the local address Streamlit prints: `http://localhost:8592`.
Embedded Qdrant locks `data/qdrant`, so run one app process at a time.

## 4. Check Health

Open **Health** first.

- Confirm whether `AGNESAI_API_KEY` is configured. The value is never shown.
- Confirm whether Ollama is online and whether the exact OCR model is present.
- If OCR cannot start, follow the displayed recovery message:

  ```text
  start Ollama, then: ollama pull AuditAid/PaddleOCR-VL-1.6-0.9B
  ```

## 5. Take the first safe path

Upload a small text-based PDF on **Upload**, then open **Inspect**. A usable
native Markdown result routes to `native`, skips OCR, and can proceed directly
to **Extract** once an Agnes key is available.

Use a scanned PDF or image to test local OCR. Inspect shows the route reason
when Ollama is required. The [zero-to-mastery tutorial](TUTORIAL_ZERO_TO_MASTERY.md)
has more exercises.

## 6. Verify the checkout

From the repository root, run:

```powershell
.venv\Scripts\python.exe -c "import app, src.pdf_inspect, src.ollama_ocr, src.extract, src.store"
.venv\Scripts\python.exe scripts\smoke_inspect.py
.venv\Scripts\python.exe scripts\smoke_workflow.py
```

The second command writes an inspection cache beneath the gitignored `data/`
directory. The workflow smoke tests Streamlit page-state gates without calling
Ollama or Agnes.
