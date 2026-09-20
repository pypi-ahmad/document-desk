# Document Desk status

Last verified: September 20, 2026

Platform: Native Windows 11

Implementation status: Requested local pipeline complete

## Files created

| Area | Files |
| --- | --- |
| Launch and configuration | `app.py`, `run.cmd`, `requirements.txt`, `.env.example`, `.gitignore` |
| Streamlit pages | `pages/1_Health.py`, `pages/2_Upload.py`, `pages/3_Inspect.py`, `pages/3_OCR.py`, `pages/4_Extract.py`, `pages/5_Ask.py`, `pages/6_Compare.py` |
| Pipeline modules | `src/config.py`, `src/pdf_inspect.py`, `src/render_pages.py`, `src/ollama_ocr.py`, `src/extract.py`, `src/store.py`, `src/qa_service.py`, `src/agnes_client.py` |
| Compatibility modules | `src/pdf_pages.py`, `src/vector_store.py`, `src/document_processor.py` |
| Smokes | `scripts/smoke_inspect.py`, `scripts/smoke_ocr.py`, `scripts/smoke_ollama_route.py`, `scripts/smoke_extract.py`, `scripts/smoke_extract_ask.py`, `scripts/smoke_workflow.py` |
| Documentation | `README.md`, `CONTRIBUTING.md`, `docs/ONBOARDING.md`, `docs/DEVELOPER_GUIDE.md`, `docs/TUTORIAL_ZERO_TO_MASTERY.md`, `docs/ARCHITECTURE.md`, `docs/OLLAMA.md`, `docs/PDF_INSPECTOR.md`, `docs/RUNBOOK.md`, `STATUS.md` |

Generated fixtures, rendered pages, caches, and embedded Qdrant data are under
the gitignored `data/` directory.

## Verified integration facts

- `pdf_inspector.process_pdf(path)` is the only pdf-inspector processing call.
- `pdf_inspector.process_pdf_with_ocr` is not used.
- PDF rasterization uses `pypdfium2`; PyMuPDF and `fitz` are absent.
- OCR uses `AuditAid/PaddleOCR-VL-1.6-0.9B` with `OCR:` and optional
  `Table Recognition:` requests at temperature `0`.
- Agnes uses the official `openai` SDK, model `agnes-3.0-flash`, base URL
  `https://apihub.agnes-ai.com/v1`, and environment variable
  `AGNESAI_API_KEY`.
- Embedded Qdrant uses `data/qdrant`, collection `documents`, and exact payload
  keys `{file_id, page, text}`.
- Only one process may access embedded Qdrant at a time.

The installed pdf-inspector call signature observed during verification was
`process_pdf(path, pages=None)`. The returned type was `PdfResult` with the
attributes documented in [docs/PDF_INSPECTOR.md](docs/PDF_INSPECTOR.md).

## Cache-producing smokes

These commands produced the listed cache files.

| Command | Cache output actually produced |
| --- | --- |
| `.venv\Scripts\python.exe scripts\smoke_inspect.py` | `data/cache/last_inspect.json` |
| `.venv\Scripts\python.exe scripts\smoke_ocr.py` | `data/cache/last_ocr.json` |
| `.venv\Scripts\python.exe scripts\smoke_ollama_route.py` | `data/cache/last_ocr.json` |
| `.venv\Scripts\python.exe scripts\smoke_extract.py` | `data/cache/last_extract.json`, `data/cache/last_ask.json` |

The OCR smoke recognized all four fixture lines:

```text
Invoice 1042
Line A 10.00
Line B 16.00
Total 26.00
```

## Other successful checks

- `scripts/smoke_workflow.py`: verified one active `file_id`, native OCR skip,
  Ask gating, and Markdown/extract JSON/Ask JSON export controls.
- Repository-root import check:

  ```powershell
  .venv\Scripts\python -c "import app, src.pdf_inspect, src.ollama_ocr, src.extract, src.store"
  ```

- `pip check`: no broken requirements.
- Critical Ruff checks: passed.
- `git diff --check`: passed.
- Python compilation passed for `app.py`, `src/`, `pages/`, `scripts/`, and
  `tests/`. A documentation audit found Google-style docstrings on all 58
  top-level public Python symbols across those paths.

## Documentation coverage

- Public Python documentation baseline: 42 symbols in `src/`, including the
  public `ExtractionResult.to_dict` method.
- The broader application, page, script, and test surface has 58 top-level
  public symbols with docstrings. The 42-symbol `src/` baseline remains the
  production API contract.
- Public APIs use Google-style contracts for relevant arguments, return values,
  side effects, and meaningful errors.
- Documentation is organized for onboarding, operations, contribution, API
  reference, and the end-to-end tutorial.
- This documentation revision passed the 42-symbol AST contract audit, Markdown
  link validation, `git diff --check`, the repository-root import check,
  `scripts\smoke_inspect.py`, and `scripts\smoke_workflow.py` on
  September 20, 2026.

## Known failures

There are no unresolved failures in the latest verification.

The UI shows this expected Ollama prerequisite failure verbatim:

```text
start Ollama, then: ollama pull AuditAid/PaddleOCR-VL-1.6-0.9B
```

Two implementation-time failures were fixed and passed their reruns. Their
final error lines are retained verbatim for traceability:

```text
SyntaxError: invalid syntax. Perhaps you forgot a comma?
```

```text
AttributeError: 'dict' object has no attribute 'must'
```

The first came from malformed Python string concatenation in the Ollama retry
error. The second was a smoke-only Qdrant filter type mismatch. Both are fixed.
