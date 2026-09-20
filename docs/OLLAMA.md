# Ollama OCR operations

Document Desk calls Ollama only for files routed to local OCR.

## Required service and model

Ollama must be running at `http://127.0.0.1:11434` before OCR begins.

Install the fixed model:

```powershell
ollama pull AuditAid/PaddleOCR-VL-1.6-0.9B
```

The app does not substitute another model ID.

## Health check

The Health page and `src/ollama_ocr.py` call:

```text
GET http://127.0.0.1:11434/api/tags
```

The check confirms both conditions:

1. Ollama responds successfully.
2. `AuditAid/PaddleOCR-VL-1.6-0.9B` appears in the installed model list.

This health check does not make Streamlit fail at import time.

## Missing service or model

When Ollama is unavailable or the model is missing, the UI displays this exact
recovery instruction:

```text
start Ollama, then: ollama pull AuditAid/PaddleOCR-VL-1.6-0.9B
```

On Windows, start the Ollama application or an existing Ollama service, then run
the pull command in PowerShell or Command Prompt.

## OCR requests

The Python package `ollama` sends local PNG attachments through the message
`images` field. Requests use temperature `0`, a client timeout, and one retry.

### Text pass

Every page receives a first request whose content starts exactly with:

```text
OCR:
```

### Optional table pass

When **Table recognition** is enabled in the sidebar, the same page image gets a
second request whose content starts exactly with:

```text
Table Recognition:
```

The returned OCR and table text remain editable on the OCR page. Extract uses
the edited page text. It never receives the PNG path.

## Page rendering

PDF pages are rendered only after the file is routed to Ollama. The renderer is
`pypdfium2`; PyMuPDF and `fitz` are not used.

Output pattern:

```text
data/pages/<file_id>/page-0001.png
```

Rendering resolution is clamped to a range of 150 to 200 DPI.
