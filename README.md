# Document Desk

Document Desk is a Windows-native Streamlit app for PDFs and document images.
It inspects, OCRs, structures, searches, and compares them locally where it can.

Each upload establishes one active `file_id` for the workflow:

1. **Upload** saves a PDF or image.
2. **Inspect** explains whether native Markdown or local OCR will be used.
3. **OCR** runs only for files routed to Ollama.
4. **Extract** sends page text to `agnes-3.0-flash`, saves structured JSON,
   and indexes page chunks in embedded Qdrant.
5. **Ask** retrieves chunks for that `file_id` and answers with page citations.
6. **Compare** reports field-name set differences and Agnes value differences.

Ollama receives local image paths only for OCR. Agnes receives native Markdown
and OCR page text, never local image paths.

## Requirements

- Windows 11
- Python available through `py -3`
- Ollama running at `http://127.0.0.1:11434`
- Agnes AI API key in `AGNESAI_API_KEY`

The environment variable is **`AGNESAI_API_KEY`**, not `AGNES_API_KEY`.
The application never prints or stores the key in generated artifacts.

Install the required local OCR model:

```powershell
ollama pull AuditAid/PaddleOCR-VL-1.6-0.9B
```

Ollama must be running on port `11434` before an OCR-routed file is processed.
See [Ollama setup and troubleshooting](docs/OLLAMA.md).

## Run the app

Double-click `run.cmd` in the repository root.

When you run it, the launcher:

1. Changes to the repository directory.
2. If `.env` is missing, copies `.env.example`, opens it in Notepad, and exits.
3. Creates `.venv` with `py -3 -m venv .venv` when needed.
4. Installs `requirements.txt` with the virtual-environment `pip`.
5. Stops an existing process listening on port `8592`, then starts Streamlit
   with `.venv\Scripts\streamlit run app.py --server.port 8592`.

The `.env.example` file contains these supported names:

```dotenv
AGNESAI_API_KEY=
AGNES_BASE_URL=https://apihub.agnes-ai.com/v1
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_OCR_MODEL=AuditAid/PaddleOCR-VL-1.6-0.9B
```

## PDF inspection and routing

The pip package `pdf-inspector` runs locally. Document Desk does not use
Firecrawl Cloud and does not require a Firecrawl API key.

PDF inspection calls only:

```python
pdf_inspector.process_pdf(path)
```

Document Desk uses native Markdown and skips OCR when the PDF has usable text.
It routes to local Ollama when any of these conditions apply:

- **Force OCR** is enabled.
- The PDF type is `scanned` or `image_based`.
- Native Markdown is empty or too thin.
- A `mixed` PDF contains pages that need OCR.
- The upload is an image.

See [pdf-inspector integration](docs/PDF_INSPECTOR.md).

## Models and storage

| Purpose | Runtime |
| --- | --- |
| Local OCR | Ollama model `AuditAid/PaddleOCR-VL-1.6-0.9B` |
| Structure, Ask, Compare | `agnes-3.0-flash` through the official `openai` SDK |
| Vector search | Embedded Qdrant collection `documents` |

Embedded Qdrant stores data under `data/qdrant`. Run only one Document Desk
Streamlit process at a time because embedded Qdrant uses an exclusive local
storage lock.

Qdrant payloads contain exactly:

```json
{
  "file_id": "document-id",
  "page": 1,
  "text": "page chunk"
}
```

## Exports

The app provides downloads for:

- Native or edited OCR Markdown
- Structured extraction JSON
- Ask result JSON, including the question, answer, and retrieved chunks

## Documentation

- [Developer onboarding](docs/ONBOARDING.md)
- [Developer guide](docs/DEVELOPER_GUIDE.md)
- [Zero-to-mastery tutorial](docs/TUTORIAL_ZERO_TO_MASTERY.md)
- [Contributor runbook](CONTRIBUTING.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Operations runbook](docs/RUNBOOK.md)
- [Ollama operations](docs/OLLAMA.md)
- [pdf-inspector integration](docs/PDF_INSPECTOR.md)
- [Implementation status](STATUS.md)
