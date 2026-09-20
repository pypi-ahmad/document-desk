# pdf-inspector integration

Document Desk uses the pip package `pdf-inspector` locally. It has no Firecrawl
Cloud call and does not need a Firecrawl API key.

## Supported call

The integration calls only:

```python
result = pdf_inspector.process_pdf(path)
```

Document Desk does **not** call `process_pdf_with_ocr`. That function belongs to
the package's OCR stack. Document Desk routes OCR to the local Ollama model.

## Installed result attributes

The installed package returns `PdfResult`. Document Desk reads these attributes:

- `pdf_type`
- `confidence`
- `page_count`
- `markdown`
- `pages_needing_ocr`
- `has_encoding_issues`
- `is_complex_layout`
- `title`

`src/pdf_inspect.py` normalizes `pdf_type` to a lowercase string and returns a
dictionary containing the source path, classification data, Markdown, routing
decision, and a human-readable route reason.

## Routing rules

### Native Markdown

Native Markdown is used when the extracted Markdown is substantial and no OCR
condition applies. This avoids page rendering and skips Ollama entirely.

### Local Ollama OCR

The file is routed to Ollama when:

- The user enables **Force OCR**.
- `pdf_type` is `scanned` or `image_based`.
- Extracted Markdown is empty or thinner than the local usability threshold.
- `pdf_type` is `mixed` and `pages_needing_ocr` is not empty.

For mixed PDFs, the implementation can preserve usable native Markdown while
OCRing the pages identified as needing OCR.

## Cached inspection

The inspection smoke and default inspection path write the latest normalized
result to:

```text
data/cache/last_inspect.json
```

The cache contains text and metadata only. It neither invokes nor caches the
package's OCR runtime.
