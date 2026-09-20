"""Document extraction module using pdf-inspector, pypdfium2, Ollama PaddleOCR-VL, and Agnes AI.

Pipeline:
1. User uploads a PDF or image.
2. PDF engine:
   - Primary: pdf-inspector (process_pdf) classifies document and extracts native markdown if text_based.
   - If scanned or image_based: renders pages with pypdfium2 to PNG under data/pages/<file_id>/page-0001.png
   - Local OCR via Ollama model AuditAid/PaddleOCR-VL-1.6-0.9B with task prefix 'OCR:' (and optional 'Table Recognition:')
   - Passes page images as local image attachments (path or bytes) to Ollama.
   - Never sends local disk paths to Agnes as public image URLs.
3. Agnes AI (agnes-3.0-flash via official openai SDK) structures fields, tables, summary, citations.
4. Cached extraction saved to data/cache/last_extract.json.
"""

from dataclasses import dataclass, field
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from PIL import Image, ImageDraw
from src.agnes_client import chat_completion_with_retry
from src.config import (
    AGNES_MODEL,
    CACHE_DIR,
    FIXTURES_DIR,
)
from src.ollama_ocr import check_ollama_status, run_page_ocr
from src.pdf_inspect import inspect_pdf
from src.render_pages import render_all_pages, render_page


@dataclass
class FieldItem:
    """Represent one extracted field and its source page.

    Attributes:
        name: Field label supplied or inferred by extraction.
        value: Extracted field value.
        page: One-based page supporting the value.
    """
    name: str = "Field"
    value: Any = ""
    page: int = 1


@dataclass
class CitationItem:
    """Represent one factual extraction claim and its source page.

    Attributes:
        claim: Factual statement from the document.
        page: One-based page supporting the claim.
    """
    claim: str = ""
    page: int = 1


@dataclass
class TableItem:
    """Represent an extracted table.

    Attributes:
        title: Human-readable table title.
        headers: Column header labels.
        rows: Row values in header order.
    """
    title: str = "Table"
    headers: List[str] = field(default_factory=list)
    rows: List[List[Any]] = field(default_factory=list)


@dataclass
class ExtractionResult:
    """Represent the normalized Agnes extraction schema.

    Attributes:
        title: Document title or main header.
        doc_type: Document classification.
        fields: Extracted key-value fields with page references.
        tables: Extracted tables.
        summary: Factual document summary.
        citations: Factual claims with page references.
    """
    title: str = "Untitled Document"
    doc_type: str = "General Document"
    fields: List[FieldItem] = field(default_factory=list)
    tables: List[TableItem] = field(default_factory=list)
    summary: str = ""
    citations: List[CitationItem] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the normalized extraction result.

        Returns:
            JSON-serializable mapping with title, doc_type, fields, tables,
            summary, and citations keys.
        """
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
        }


def ensure_sample_pdf(pdf_path: Optional[Path] = None) -> Path:
    """Return a local invoice-like PDF fixture, creating it when absent.

    Args:
        pdf_path: Optional fixture target. Defaults to `data/fixtures/sample.pdf`.

    Returns:
        Existing or newly generated PDF fixture path.

    Raises:
        OSError: If Pillow cannot create the target file.
    """
    target_path = Path(pdf_path) if pdf_path else (FIXTURES_DIR / "sample.pdf")
    if target_path.exists():
        return target_path

    target_path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (800, 1000), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

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
        draw.text((50, y_pos), line, fill=(0, 0, 0))
        y_pos += 26

    img.save(str(target_path), "PDF", resolution=150.0)
    return target_path


def parse_and_harden_json(raw_text: str) -> Dict[str, Any]:
    """Extract the first valid JSON object from an Agnes response.

    Args:
        raw_text: Model response that may include prose or Markdown fences.

    Returns:
        The first decoded JSON object found in response order.

    Raises:
        ValueError: If no valid JSON object can be decoded.
    """
    cleaned = raw_text.strip()
    cleaned = re.sub(r"```(?:json)?|```", "", cleaned, flags=re.IGNORECASE)
    decoder = json.JSONDecoder()

    for candidate in (cleaned, re.sub(r",\s*([}\]])", r"\1", cleaned)):
        for match in re.finditer(r"\{", candidate):
            try:
                data, _ = decoder.raw_decode(candidate[match.start():])
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                return data

    raise ValueError("Agnes response did not contain a valid JSON object")



def extract_document_pages(
    file_path: Union[str, Path],
    file_id: Optional[str] = None,
    force_ocr: bool = False,
    include_tables: bool = False,
) -> Tuple[List[Dict[str, Any]], str]:
    """Extract page text through native inspection or routed local OCR.

    Args:
        file_path: Existing PDF or supported image path.
        file_id: Optional active-document identifier for rendered pages.
        force_ocr: Whether a PDF must use OCR despite its inspection result.
        include_tables: Whether OCR runs the table-recognition second pass.

    Returns:
        Page dictionaries and concatenated text. Local image paths remain only
        in local page records and are never sent to Agnes.

    Raises:
        FileNotFoundError: If `file_path` does not exist.
        ValueError: If the source extension is unsupported.
        RuntimeError: If required Ollama OCR is unavailable.
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

    if suffix == ".pdf":
        inspection = inspect_pdf(path, force_ocr=force_ocr)
        pdf_type = inspection["pdf_type"]
        confidence = inspection["confidence"]
        page_count = inspection["page_count"]
        md_text = inspection["markdown"]

        if inspection["route"] == "native":
            pages_info.append({
                "page_number": 1,
                "text": md_text,
                "has_text": True,
                "image_path": None,
                "ocr_text": "",
                "table_text": "",
                "method": "pdf-inspector-native",
                "warning": None,
                "pdf_type": pdf_type,
                "confidence": confidence,
            })
            concatenated_blocks.append(f"--- Page 1 ---\n{md_text}")
        else:
            is_online, has_model, ollama_instruction, _ = check_ollama_status()
            if not (is_online and has_model):
                raise RuntimeError(ollama_instruction)

            pages_needing_ocr = inspection["pages_needing_ocr"]
            if force_ocr or pdf_type in {"scanned", "image_based"} or not pages_needing_ocr:
                target_pages = list(range(1, page_count + 1))
            else:
                target_pages = pages_needing_ocr

            if pdf_type == "mixed" and inspection["markdown_usable"] and not force_ocr:
                pages_info.append({
                    "page_number": 1,
                    "text": md_text,
                    "has_text": True,
                    "image_path": None,
                    "ocr_text": "",
                    "table_text": "",
                    "method": "pdf-inspector-native-mixed",
                    "warning": None,
                    "pdf_type": pdf_type,
                    "confidence": confidence,
                })
                concatenated_blocks.append(f"--- Native Markdown ---\n{md_text}")

            for page_num in target_pages:
                img_path = render_page(
                    path,
                    page_number_1based=page_num,
                    file_id=file_id,
                    dpi=150,
                    route="ollama",
                )
                if img_path is None:
                    raise RuntimeError(f"Failed to render page {page_num}")
                ocr_res = run_page_ocr(
                    image_input=img_path,
                    include_tables=include_tables,
                )
                page_text = ocr_res["combined_text"]
                pages_info.append({
                    "page_number": page_num,
                    "text": page_text,
                    "has_text": bool(page_text.strip()),
                    "image_path": str(img_path),
                    "ocr_text": ocr_res.get("ocr_text", ""),
                    "table_text": ocr_res.get("table_text", ""),
                    "method": "pypdfium2_ollama_paddleocr_vl",
                    "warning": None,
                    "pdf_type": pdf_type,
                    "confidence": confidence,
                })
                concatenated_blocks.append(f"--- Page {page_num} ---\n{page_text}")

    elif suffix in [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"]:
        is_online, has_model, ollama_instruction, _ = check_ollama_status()
        if not (is_online and has_model):
            raise RuntimeError(ollama_instruction)

        rendered_images = render_all_pages(
            path,
            file_id=file_id,
            dpi=150,
            route="ollama",
        )
        img_copy = rendered_images[0]
        ocr_res = run_page_ocr(
            image_input=img_copy,
            include_tables=include_tables,
        )
        page_text = ocr_res["combined_text"]
        pages_info.append({
            "page_number": 1,
            "text": page_text,
            "has_text": bool(page_text.strip()),
            "image_path": str(img_copy),
            "ocr_text": ocr_res.get("ocr_text", ""),
            "table_text": ocr_res.get("table_text", ""),
            "method": "image_ollama_paddleocr_vl",
            "warning": None,
        })
        concatenated_blocks.append(f"--- Page 1 ---\n{page_text}")
    else:
        raise ValueError(f"Unsupported document format: {suffix}")

    concatenated_text = "\n\n".join(concatenated_blocks)
    return pages_info, concatenated_text


def extract_pages(
    file_path: Union[str, Path],
    force_ocr: bool = False,
    include_tables: bool = False,
) -> Tuple[List[Dict[str, Any]], str]:
    """Extract pages through the compatibility extraction entry point.

    Args:
        file_path: Existing PDF or supported image path.
        force_ocr: Whether a PDF must use OCR regardless of classification.
        include_tables: Whether OCR runs table recognition.

    Returns:
        Page dictionaries and their concatenated text.

    Raises:
        FileNotFoundError: If `file_path` does not exist.
        ValueError: If the source extension is unsupported.
        RuntimeError: If required Ollama OCR is unavailable.
    """
    return extract_document_pages(
        file_path=file_path,
        force_ocr=force_ocr,
        include_tables=include_tables,
    )


def _build_extraction_prompt(text_content: str) -> List[Dict[str, str]]:
    """Build messages array enforcing the required JSON schema from concatenated OCR text."""
    system_prompt = (
        "You are an expert document understanding AI. Analyze the concatenated OCR page text and return ONLY "
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
        "- 'title': Document title or main header.\n"
        "- 'doc_type': Document classification (e.g. Invoice, Receipt, Contract, Agreement, Statement).\n"
        "- 'fields': Array of key-value pairs with exact page citations.\n"
        "- 'tables': Array of tables (or empty array [] if none).\n"
        "- 'summary': Concise factual summary of the document contents.\n"
        "- 'citations': Array of factual claims with page numbers.\n"
        "- Output strictly raw JSON without markdown code fences or explanatory text."
    )

    user_prompt = f"Document OCR Page Text:\n{text_content}\n\nReturn the structured JSON extraction now:"

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

    return ExtractionResult(
        title=str(parsed_json.get("title", "Untitled Document")),
        doc_type=str(parsed_json.get("doc_type", "General Document")),
        fields=fields_list,
        tables=tables_list,
        summary=str(parsed_json.get("summary", "")),
        citations=citations_list,
    )


def extract_with_agnes(
    content: Union[str, List[Dict[str, Any]]],
    model: str = AGNES_MODEL,
    provider_name: str = "Agnes AI",
    save_cache: bool = True,
    max_single_call_pages: int = 4,
    max_single_call_chars: int = 15000,
) -> Dict[str, Any]:
    """Structure document text with Agnes and normalize its JSON output.

    Args:
        content: Concatenated text or page dictionaries containing source text.
        model: Agnes model identifier.
        provider_name: Configured provider display name.
        save_cache: Whether to write `data/cache/last_extract.json`.
        max_single_call_pages: Page count above which extraction runs per page.
        max_single_call_chars: Character count above which extraction runs per page.

    Returns:
        Normalized title, doc_type, fields, tables, summary, and citations.

    Raises:
        AgnesClientError: If Agnes cannot complete an extraction request.
        ValueError: If an Agnes response contains no valid JSON object.
        OSError: If cache writing is requested but fails.
    """
    if isinstance(content, list):
        pages_info = content
        concatenated_blocks = []
        for i, p in enumerate(pages_info):
            p_num = p.get("page_number", p.get("page", i + 1))
            p_text = p.get("text", "") or p.get("combined_text", "") or p.get("ocr_text", "")
            concatenated_blocks.append(f"--- Page {p_num} ---\n{p_text}")
        concat_text = "\n\n".join(concatenated_blocks)
    else:
        concat_text = str(content)
        pages_info = None

    is_long = False
    if pages_info and len(pages_info) > max_single_call_pages:
        is_long = True
    elif len(concat_text) > max_single_call_chars:
        is_long = True

    if not is_long or not pages_info:
        messages = _build_extraction_prompt(concat_text[:25000])
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

        for i, p_data in enumerate(pages_info):
            p_num = p_data.get("page_number", p_data.get("page", i + 1))
            p_text = p_data.get("text", "") or p_data.get("combined_text", "") or p_data.get("ocr_text", "")
            if len(p_text.strip()) < 10:
                continue

            messages = _build_extraction_prompt(f"--- Page {p_num} ---\n{p_text}")
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
        )
        result_dict = combined.to_dict()

    if save_cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path = CACHE_DIR / "last_extract.json"
        cache_path.write_text(json.dumps(result_dict, indent=2), encoding="utf-8")

    return result_dict
