# Contributing to Document Desk

Document Desk is a Windows-native Streamlit application. Keep the document
boundary intact when you contribute: inspect PDFs locally, send page images to
Ollama only for OCR, and send page text to Agnes.

## Before you begin

- Use native Windows 11. Do not introduce WSL2, Docker, PaddlePaddle, PyMuPDF,
  or `fitz`.
- Run only one Streamlit or script process against `data/qdrant` at a time.
- Keep `AGNESAI_API_KEY` private. Do not print it, add it to tests, or commit
  `.env`, `.venv`, or `data/`.
- Read the [developer guide](docs/DEVELOPER_GUIDE.md) for architecture and the
  [onboarding guide](docs/ONBOARDING.md) for first-run setup.

## Contribution workflow

Use a feature branch and a pull request. Do not make contribution changes
directly on `main`.

```powershell
git switch main
git pull --ff-only origin main
git switch -c your-short-change-name
```

Keep each change focused. Leave unrelated worktree changes alone and do not
stage them by accident.

Before opening a pull request:

1. Review `git diff` and `git status --short`.
2. Run the checks appropriate to the changed area.
3. Run `git diff --check`.
4. Commit only the intended paths with a clear imperative subject.
5. Push the branch and open a pull request that states the behavior changed,
   checks run, and any service prerequisites not exercised.

## Development conventions

- Keep PDF inspection on `pdf_inspector.process_pdf`; never call the package's
  `process_pdf_with_ocr` path.
- Use `pypdfium2` for routed PDF rasterization. Native-text PDFs must not be
  rasterized merely for convenience.
- Keep the Ollama model ID and task prefixes exact:
  `AuditAid/PaddleOCR-VL-1.6-0.9B`, `OCR:`, and `Table Recognition:`.
- Use the official `openai` SDK for Agnes calls, with
  `AGNESAI_API_KEY` and `agnes-3.0-flash`.
- Preserve the Qdrant payload contract: `{file_id, page, text}`.
- Add Google-style contracts when adding public `src` APIs. Explain meaningful
  inputs, outputs, side effects, and errors without narrating obvious code.

## Checks

Run commands from the repository root after activating or creating `.venv`:

```powershell
.venv\Scripts\python.exe -c "import app, src.pdf_inspect, src.ollama_ocr, src.extract, src.store"
.venv\Scripts\python.exe scripts\smoke_inspect.py
.venv\Scripts\python.exe scripts\smoke_workflow.py
git diff --check
```

The inspection and workflow smokes do not require live Agnes or Ollama calls.
See the [operations runbook](docs/RUNBOOK.md) before running OCR- or
Agnes-dependent smokes, because they access local services or embedded Qdrant.

## Documentation changes

Keep user-facing guidance aligned with the code in the same pull request. Update:

- `README.md` for discovery and first-run changes.
- `docs/RUNBOOK.md` for operations and recovery steps.
- `docs/DEVELOPER_GUIDE.md` for module, API, or storage contracts.
- `STATUS.md` only with checks actually run and outcomes actually observed.
