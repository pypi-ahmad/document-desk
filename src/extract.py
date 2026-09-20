"""Document extraction module using Ollama PaddleOCR-VL, PyMuPDF, and Agnes AI.

Pipeline:
1. User uploads a PDF or image.
2. Local OCR / page parse via Ollama model AuditAid/PaddleOCR-VL-1.6-0.9B:
   - Uses task prefix 'OCR:'
   - Optional second pass 'Table Recognition:' if tables enabled
   - Renders PDF pages with pypdfium2/PyMuPDF to local PNG
   - Passes page images as local image attachments (path or bytes) to Ollama
   - Never sends local disk paths to Agnes as public image URLs
3. Agnes AI (agnes-3.0-flash via official openai SDK) structures fields, tables, summary, citations.
4. Cached extraction saved to data/cache/last_extract.json.
"""

from dataclasses import dataclass, field
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import pymupdf as fitz
from PIL import Image

from src.agnes_client import chat_completion_with_retry, AgnesClientError
from src.config import (
    CACHE_DIR,
    FIXTURES_DIR,
    PAGES_DIR,
    AGNES_MODEL,
    is_agnes_key_set,
    OLLAMA_OCR_MODEL,
    TASK_OCR,
    TASK_TABLE,
)
from src.ollama_ocr import check_ollama_status, run_page_ocr
from src.render_pages import render_page


@dataclass
class FieldItem:
    """Extracted key-value field with source page number."""
    name: str = "Field"
    value: Any = ""
    page: int = 1


@dataclass
class CitationItem:
    """Factual claim citation with page reference."""
    claim: str = ""
    page: int = 1


@dataclass
class TableItem:
    """Extracted table with title, column headers, and row data."""
    title: str = "Table"
    headers: List[str] = field(default_factory=list)
    rows: List[List[Any]] = field(default_factory=list)


@dataclass
class ExtractionResult:
    """Normalized output schema from Agnes AI."""
    title: str = "Untitled Document"
    doc_type: str = "General Document"
    fields: List[FieldItem] = field(default_factory=list)
    tables: List[TableItem] = field(default_factory=list)
    summary: str = ""
    citations: List[CitationItem] = field(default_factory=list)
    page_citations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Return as a standard serializable dictionary matching the required schema."""
        return {
            "title": self.title,
            "doc_type": self.doc_type,
            "fields": [
                {"name": f.name, "value": f.value, "page": f.page}
                for f in self.fields
            ],
            "tables": [
                {"title": t.title, "headers": t.headers, "rows": t.rows}
                for t in self.tables
            ],
            "summary": self.summary,
            "citations": [
                {"claim": c.claim, "page": c.page}
                for c in self.citations
            ],
            "page_citations": self.page_citations,
        }


def ensure_sample_pdf(pdf_path: Optional[Path] = None) -> Path:
    """Ensure data/fixtures/sample.pdf exists with a clean invoice-like layout."""
    target_path = Path(pdf_path) if pdf_path else (FIXTURES_DIR / "sample.pdf")
    if target_path.exists():
        return target_path

    target_path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)  # Standard Letter

    content_lines = [
        "INVOICE & CONSULTING SERVICES AGREEMENT",
        "Invoice Number: INV-2026-9042",
        "Date: September 19, 2026",
        "Due Date: October 19, 2026",
        "",
        "Bill To: Acme Global Logistics Inc.",
        "From: Apex AI Strategy LLC",
        "",
        "Itemized Billing & Services:",
        "Description | Hours | Rate | Total",
        "AI Workflow Automation Architecture | 15 | $180.00 | $2,700.00",
        "Document Desk Integration & Testing | 10 | $150.00 | $1,500.00",
        "Local Pipeline Tuning | 5 | $140.00 | $700.00",
        "",
        "Financial Totals:",
        "Subtotal: $4,900.00",
        "Tax Rate: 8.0%",
        "Tax Amount: $392.00",
        "Total Amount Due: $5,292.00",
        "",
        "Terms and Conditions:",
        "Payment Terms: Net 30 days. Late fee of 1.5% applies after due date.",
        "Status: Approved & Issued.",
    ]

    y_pos = 50
    for line in content_lines:
        font_size = 14 if "INVOICE" in line else 11
        page.insert_text((50, y_pos), line, fontsize=font_size)
        y_pos += 24

    doc.save(str(target_path))
    doc.close()
    return target_path


def parse_and_harden_json(raw_text: str) -> Dict[str, Any]:
    """Robustly parse JSON response from LLM, fixing markdown fences and common issues."""
    cleaned = raw_text.strip()

    # 1. Strip markdown code fences
    if "```" in cleaned:
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE)
        cleaned = cleaned.strip()

    # 2. Direct JSON parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 3. Search for outermost JSON object { ... }
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        candidate = match.group(0)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            # 4. Clean trailing commas before closing braces/brackets
            fixed = re.sub(r",\s*([\]}])", r"\1", candidate)
            try:
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass

    raise ValueError(f"Failed to parse valid JSON from LLM response:\n{raw_text[:500]}")


def extract_document_pages(
    file_path: Union[str, Path],
    file_id: Optional[str] = None,
    force_ocr: bool = False,
    include_tables: bool = False,
    user_image_url: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], str]:
    """Extract per-page text from PDF or image using local Ollama VL or native text.
    
    Hard rules:
    - Ollama model: AuditAid/PaddleOCR-VL-1.6-0.9B
    - Page images are local PNG/JPEG passed as Ollama image attachments (path or bytes).
    - Never send local disk paths to Agnes as public image URLs.
    - Default OCR pass: 'OCR:'
    - Second pass: 'Table Recognition:' if include_tables=True.
    - If Ollama is down or model missing: clear error message:
      'start Ollama Desktop, then ollama pull AuditAid/PaddleOCR-VL-1.6-0.9B'.
    
    Returns:
      (pages_info, concatenated_text)
    """
    path = Path(file_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    stem = re.sub(r"[^\w\-]", "_", path.stem)
    if not file_id:
        file_id = stem

    suffix = path.suffix.lower()
    pages_info: List[Dict[str, Any]] = []
    concatenated_blocks: List[str] = []

    # Check Ollama status
    is_online, has_model, ollama_instruction, _ = check_ollama_status()
    ollama_ready = is_online and has_model

    if suffix == ".pdf":
        doc = fitz.open(str(path))
        page_count = len(doc)

        for idx in range(page_count):
            page_num = idx + 1
            page = doc[idx]
            raw_text = page.get_text().strip()
            has_native_text = len(raw_text) >= 20

            # Determine if this page should undergo Ollama VL OCR
            should_run_ocr = force_ocr or (not has_native_text)

            if should_run_ocr:
                # Render page to PNG using pypdfium2
                try:
                    img_path = render_page(path, page_num, file_id=file_id, dpi=150)
                except Exception:
                    # Fallback to PyMuPDF pixmap
                    target_dir = PAGES_DIR / file_id
                    target_dir.mkdir(parents=True, exist_ok=True)
                    img_path = target_dir / f"page_{page_num}.png"
                    pix = page.get_pixmap(dpi=150)
                    pix.save(str(img_path))

                if ollama_ready:
                    # Run Ollama VL: Pass 1: OCR: ; Pass 2: Table Recognition: (if enabled)
                    ocr_res = run_page_ocr(
                        image_input=img_path,
                        include_tables=include_tables,
                        task_prefix=TASK_OCR,
                    )
                    page_text = ocr_res["combined_text"]
                    pages_info.append({
                        "page_number": page_num,
                        "text": page_text,
                        "has_text": bool(page_text.strip()),
                        "image_path": str(img_path),
                        "ocr_text": ocr_res.get("ocr_text", ""),
                        "table_text": ocr_res.get("table_text", ""),
                        "method": "ollama_paddleocr_vl",
                        "warning": None,
                    })
                    concatenated_blocks.append(f"--- Page {page_num} ---\n{page_text}")
                else:
                    # Ollama down or model missing
                    warn_msg = ollama_instruction
                    fallback_text = raw_text if has_native_text else f"[Page {page_num}: No text extracted. {ollama_instruction}]"
                    pages_info.append({
                        "page_number": page_num,
                        "text": fallback_text,
                        "has_text": has_native_text,
                        "image_path": str(img_path),
                        "ocr_text": "",
                        "table_text": "",
                        "method": "native_fallback_ollama_offline",
                        "warning": warn_msg,
                    })
                    concatenated_blocks.append(f"--- Page {page_num} ---\n{fallback_text}")

            else:
                # Use native PyMuPDF text
                pages_info.append({
                    "page_number": page_num,
                    "text": raw_text,
                    "has_text": True,
                    "image_path": None,
                    "ocr_text": "",
                    "table_text": "",
                    "method": "pymupdf_native",
                    "warning": None,
                })
                concatenated_blocks.append(f"--- Page {page_num} ---\n{raw_text}")

        doc.close()

    elif suffix in [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"]:
        target_dir = PAGES_DIR / file_id
        target_dir.mkdir(parents=True, exist_ok=True)
        img_copy = target_dir / "page_1.png"
        img = Image.open(path)
        img.save(img_copy, format="PNG")

        if ollama_ready:
            ocr_res = run_page_ocr(
                image_input=img_copy,
                include_tables=include_tables,
                task_prefix=TASK_OCR,
            )
            page_text = ocr_res["combined_text"]
            pages_info.append({
                "page_number": 1,
                "text": page_text,
                "has_text": bool(page_text.strip()),
                "image_path": str(img_copy),
                "ocr_text": ocr_res.get("ocr_text", ""),
                "table_text": ocr_res.get("table_text", ""),
                "method": "ollama_paddleocr_vl",
                "warning": None,
            })
            concatenated_blocks.append(f"--- Page 1 ---\n{page_text}")
        else:
            warn_msg = ollama_instruction
            note = f"[Page 1 Image: {ollama_instruction}]"
            pages_info.append({
                "page_number": 1,
                "text": note,
                "has_text": False,
                "image_path": str(img_copy),
                "ocr_text": "",
                "table_text": "",
                "method": "image_ollama_offline",
                "warning": warn_msg,
            })
            concatenated_blocks.append(f"--- Page 1 ---\n{note}")
    else:
        raise ValueError(f"Unsupported document format: {suffix}")

    concatenated_text = "\n\n".join(concatenated_blocks)
    return pages_info, concatenated_text


def extract_pages_pymupdf(
    file_path: Union[str, Path],
    user_image_url: Optional[str] = None,
    force_ocr: bool = False,
    include_tables: bool = False,
) -> Tuple[List[Dict[str, Any]], str]:
    """Compatibility wrapper routing to extract_document_pages."""
    return extract_document_pages(
        file_path=file_path,
        force_ocr=force_ocr,
        include_tables=include_tables,
        user_image_url=user_image_url,
    )


def _build_extraction_prompt(text_content: str, user_image_url: Optional[str] = None) -> List[Dict[str, str]]:
    """Build messages array enforcing the required JSON schema."""
    system_prompt = (
        "You are an expert document understanding AI. Analyze the document text and return ONLY "
        "a valid JSON object matching this exact schema:\n"
        "{\n"
        '  "title": "string",\n'
        '  "doc_type": "string",\n'
        '  "fields": [\n'
        '    {"name": "string", "value": "string | number", "page": 1}\n'
        '  ],\n'
        '  "tables": [\n'
        '    {"title": "string", "headers": ["col1", "col2"], "rows": [["val1", "val2"]]}\n'
        '  ],\n'
        '  "summary": "string",\n'
        '  "citations": [\n'
        '    {"claim": "string", "page": 1}\n'
        '  ]\n'
        "}\n\n"
        "Rules:\n"
        "- 'fields' must be key-value pairs representing specific data points, dates, parties, amounts, identifiers.\n"
        "- 'tables' must capture any tabular structures with column headers and rows.\n"
        "- 'summary' must provide a factual summary of the document.\n"
        "- 'citations' must be factual claims with the source page number.\n"
        "- Output strictly raw JSON. Do not include markdown code fences or explanatory text."
    )

    user_prompt = f"Document Text:\n{text_content}\n\n"
    if user_image_url and (user_image_url.strip().startswith("http://") or user_image_url.strip().startswith("https://")):
        user_prompt += f"Associated Public Document Image URL: {user_image_url.strip()}\n\n"

    user_prompt += "Return the structured JSON extraction now:"

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _normalize_parsed_data(parsed_json: Dict[str, Any], default_page: int = 1) -> ExtractionResult:
    """Normalize fields, tables, and citations into strict typed structures."""
    fields_list: List[FieldItem] = []
    raw_fields = parsed_json.get("fields", [])
    if isinstance(raw_fields, list):
        for item in raw_fields:
            if isinstance(item, dict):
                p = item.get("page")
                try:
                    page_val = int(p) if p is not None else default_page
                except (ValueError, TypeError):
                    page_val = default_page
                fields_list.append(
                    FieldItem(
                        name=str(item.get("name", "Unknown")),
                        value=item.get("value", ""),
                        page=page_val,
                    )
                )
            elif isinstance(item, str):
                fields_list.append(FieldItem(name=item, value="", page=default_page))
    elif isinstance(raw_fields, dict):
        for k, v in raw_fields.items():
            fields_list.append(FieldItem(name=str(k), value=v, page=default_page))

    tables_list: List[TableItem] = []
    for t in parsed_json.get("tables", []):
        if isinstance(t, dict):
            tables_list.append(
                TableItem(
                    title=str(t.get("title", "Table")),
                    headers=[str(h) for h in t.get("headers", [])],
                    rows=[list(r) for r in t.get("rows", []) if isinstance(r, (list, tuple))],
                )
            )

    citations_list: List[CitationItem] = []
    raw_citations = parsed_json.get("citations", [])
    if isinstance(raw_citations, list):
        for c in raw_citations:
            if isinstance(c, dict):
                p = c.get("page")
                try:
                    page_val = int(p) if p is not None else default_page
                except (ValueError, TypeError):
                    page_val = default_page
                citations_list.append(
                    CitationItem(claim=str(c.get("claim", "")), page=page_val)
                )
            elif isinstance(c, str):
                m = re.search(r"Page\s*(\d+)", c, re.IGNORECASE)
                p_num = int(m.group(1)) if m else default_page
                citations_list.append(CitationItem(claim=c, page=p_num))

    page_citations_strings = [
        f"Page {c.page}: {c.claim}" for c in citations_list if c.claim
    ]
    if not page_citations_strings and isinstance(parsed_json.get("page_citations"), list):
        page_citations_strings = [str(x) for x in parsed_json.get("page_citations")]

    return ExtractionResult(
        title=str(parsed_json.get("title", "Untitled Document")),
        doc_type=str(parsed_json.get("doc_type", "General Document")),
        fields=fields_list,
        tables=tables_list,
        summary=str(parsed_json.get("summary", "")),
        citations=citations_list,
        page_citations=page_citations_strings,
    )


def extract_with_agnes(
    content: Union[str, List[Dict[str, Any]]],
    user_image_url: Optional[str] = None,
    model: str = AGNES_MODEL,
    provider_name: str = "Agnes AI",
    save_cache: bool = True,
    max_single_call_pages: int = 4,
    max_single_call_chars: int = 15000,
) -> Dict[str, Any]:
    """Call LLM (agnes-3.0-flash by default) to extract structured JSON.
    
    Supports:
    - One LLM call per document (default for typical documents).
    - Per-page extraction if document is long (> 4 pages or > 15,000 chars).
    
    Returns JSON dictionary with schema:
    {
      title,
      doc_type,
      fields: [{name, value, page}],
      tables: [{title, headers, rows}],
      summary,
      citations: [{claim, page}]
    }
    """
    if isinstance(content, list):
        pages_info = content
        concat_text = "\n\n".join(
            f"--- Page {p.get('page_number', i+1)} ---\n{p.get('text', '')}"
            for i, p in enumerate(pages_info)
        )
    else:
        concat_text = str(content)
        pages_info = None

    is_long = False
    if pages_info and len(pages_info) > max_single_call_pages:
        is_long = True
    elif len(concat_text) > max_single_call_chars:
        is_long = True

    if not is_long or not pages_info:
        messages = _build_extraction_prompt(concat_text[:25000], user_image_url=user_image_url)
        raw_response = chat_completion_with_retry(
            messages=messages,
            model=model,
            provider_name=provider_name,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        parsed_json = parse_and_harden_json(raw_response)
        validated = _normalize_parsed_data(parsed_json, default_page=1)
        result_dict = validated.to_dict()

    else:
        aggregated_fields: List[FieldItem] = []
        aggregated_tables: List[TableItem] = []
        aggregated_citations: List[CitationItem] = []
        doc_title = "Untitled Document"
        doc_type = "Multi-page Document"
        summaries: List[str] = []

        for p_data in pages_info:
            p_num = p_data.get("page_number", 1)
            p_text = p_data.get("text", "")
            if len(p_text.strip()) < 10:
                continue

            messages = _build_extraction_prompt(
                f"Page {p_num}:\n{p_text}",
                user_image_url=user_image_url,
            )
            raw_response = chat_completion_with_retry(
                messages=messages,
                model=model,
                provider_name=provider_name,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            p_json = parse_and_harden_json(raw_response)
            p_norm = _normalize_parsed_data(p_json, default_page=p_num)

            if doc_title == "Untitled Document" and p_norm.title != "Untitled Document":
                doc_title = p_norm.title
            if p_norm.doc_type != "General Document":
                doc_type = p_norm.doc_type

            aggregated_fields.extend(p_norm.fields)
            aggregated_tables.extend(p_norm.tables)
            aggregated_citations.extend(p_norm.citations)
            if p_norm.summary:
                summaries.append(f"Page {p_num}: {p_norm.summary}")

        combined = ExtractionResult(
            title=doc_title,
            doc_type=doc_type,
            fields=aggregated_fields,
            tables=aggregated_tables,
            summary=" ".join(summaries),
            citations=aggregated_citations,
            page_citations=[f"Page {c.page}: {c.claim}" for c in aggregated_citations],
        )
        result_dict = combined.to_dict()

    if save_cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path = CACHE_DIR / "last_extract.json"
        cache_path.write_text(json.dumps(result_dict, indent=2), encoding="utf-8")

    return result_dict
