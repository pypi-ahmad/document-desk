# Document Desk: zero to mastery

This tutorial starts with a local launch and ends with a complete document
workflow. Use your own non-sensitive documents. Model output varies, so the
tutorial checks each stage by its observable application state.

## What you need

- Native Windows 11 and Python available as `py -3`.
- Ollama running on port `11434` and the OCR model installed for OCR exercises.
- `AGNESAI_API_KEY` configured for Extract, Ask, and Compare.
- Two related PDFs or images if you want to complete Compare.

Follow [developer onboarding](ONBOARDING.md) first if `.env` and `run.cmd` are
new to you.

## Level 1: launch and health

1. Double-click `run.cmd`.
2. If it opens `.env`, configure it, save it, and run `run.cmd` again.
3. Open **Health** in the Streamlit app.

You should see a configured Agnes-key indicator and, if you plan to use OCR, an
online Ollama indicator with the required model. A missing model shows:

```text
start Ollama, then: ollama pull AuditAid/PaddleOCR-VL-1.6-0.9B
```

## Level 2: native PDF path

1. On **Upload**, choose a small text-based PDF.
2. Leave **Force OCR** unchecked.
3. Open **Inspect**.

Substantial native Markdown routes to `native`. Read the route reason and
Markdown preview. This path does not render pages or call Ollama.

## Level 3: local OCR path

1. Return to **Upload** and choose a scanned PDF or an image.
2. Open **Inspect** and confirm the route is `ollama`.
3. On **OCR**, render pages if needed, then run OCR. Enable table recognition
   only when you want the second `Table Recognition:` pass.
4. Correct any page text in the editable controls.

The rendered files appear under `data/pages/<file_id>/` as PNGs. They are local
working files, not Agnes inputs.

## Level 4: structured extraction

1. Open **Extract** for the active file.
2. Click **Run Agnes Extraction**.
3. Inspect the title, document type, fields, tables, summary, and citations.
4. Download Markdown or extraction JSON when needed.

Extract uses native Markdown on the native path and your editable OCR text on
the OCR path. It also indexes the current page text in embedded Qdrant, so Ask
becomes available for this same `file_id`.

## Level 5: grounded questions

1. Open **Ask**.
2. Enter a question whose answer should appear in the document.
3. Review the answer and the retrieved chunks.

Ask is disabled until Extract completes for the active file. Answers come from
file-scoped chunks and include page citations. If retrieval finds no chunks, the
app says so instead of asking Agnes to invent an answer.

## Level 6: compare versions

1. Upload or load a second related document.
2. Open **Compare**.
3. Select the base and comparison `file_id` values.
4. Run the comparison.

The page first calculates exact Python set differences for field names, then
uses Agnes to describe differences in field values. Treat the model prose as a
review aid and verify material changes against the cited source documents.

## Level 7: understand the code

Trace a document through the code in this order:

1. `pages/2_Upload.py` establishes `current_file_id` and inspection data.
2. `src/pdf_inspect.py` selects the native or Ollama route.
3. `src/render_pages.py` and `src/ollama_ocr.py` handle only OCR-routed pages.
4. `src/extract.py` sends text to Agnes and normalizes the JSON result.
5. `src/store.py` chunks page text and filters retrieval by `file_id`.
6. `src/qa_service.py` grounds Ask and Compare behavior.

Use the [developer guide](DEVELOPER_GUIDE.md) for contracts and the
[contributor runbook](../CONTRIBUTING.md) before changing code.

## Mastery checks

You are ready to contribute when you can explain:

- Why a text PDF skips OCR while an image cannot.
- Why Agnes never receives a local image path.
- Why Ask is disabled before extraction.
- Why only one process may access embedded Qdrant.
- Which smoke needs Ollama, Agnes, both, or neither.
