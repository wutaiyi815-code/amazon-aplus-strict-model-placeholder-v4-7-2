#!/usr/bin/env python
"""Repair a non-authoritative field after strict cross-section ownership failure."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import requests

from build_creative_module_prompts import (
    excel_value_language,
    normalized_section_text,
    parse_sections,
    read_excel_section_copy,
    read_text,
)


ENDPOINT = "https://toapis.com/v1/chat/completions"
MODEL = "gemini-3.1-flash-lite"


def response_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if not choices:
        return ""
    return str(((choices[0].get("message") or {}).get("content")) or "").strip()


def extract_json_value(text: str, field: str) -> str:
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        raise RuntimeError(f"Analysis model returned no JSON object: {text[:300]}")
    payload = json.loads(match.group(0))
    value = str(payload.get(field.casefold()) or payload.get(field) or "").strip()
    if not value:
        raise RuntimeError(f"Analysis model returned an empty {field}")
    return value


def replace_section_field(text: str, section_index: int, field: str, value: str) -> str:
    section_re = re.compile(
        rf"(?ims)(^##\s+Section\s+0?{section_index}\b.*?$)(.*?)(?=^##\s+Section\s+\d+\b|\Z)"
    )
    match = section_re.search(text)
    if not match:
        raise RuntimeError(f"Section {section_index} not found in creative brief")
    block = match.group(2)
    field_re = re.compile(rf"(?im)^{re.escape(field)}\s*:\s*.*$")
    if not field_re.search(block):
        raise RuntimeError(f"{field} field not found in Section {section_index}")
    updated_block = field_re.sub(f"{field}: {value}", block, count=1)
    return text[: match.start(2)] + updated_block + text[match.end(2) :]


def main() -> int:
    global MODEL
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--creative-brief", required=True)
    parser.add_argument("--section", required=True, type=int)
    parser.add_argument("--field", required=True, choices=["Headline", "Copy"])
    parser.add_argument("--api-key", default=os.getenv("TOAPIS_API_KEY") or os.getenv("OPENAI_API_KEY"))
    parser.add_argument("--model", default=os.getenv("APLUS_ANALYSIS_MODEL") or MODEL)
    args = parser.parse_args()
    MODEL = args.model
    if not args.api_key:
        raise SystemExit("Missing TOAPIS_API_KEY")

    brief_path = Path(args.creative_brief).expanduser().resolve()
    product_dir = brief_path.parent.parent
    text = read_text(brief_path)
    overrides = read_excel_section_copy(product_dir)
    if str(overrides.get(args.section, {}).get(args.field) or "").strip():
        raise SystemExit(
            f"Refusing to repair Excel-authored Section {args.section} {args.field}; authoritative text may not be rewritten."
        )

    sections = parse_sections(text, None)
    section = next((item for item in sections if int(item.get("index", 0)) == args.section), None)
    if section is None:
        raise SystemExit(f"Section {args.section} not found")
    forbidden = sorted(
        {
            str(fields.get(key) or "").strip()
            for fields in overrides.values()
            for key in ("Headline", "Copy")
            if str(fields.get(key) or "").strip()
        }
    )
    language = excel_value_language(product_dir)
    length_rule = "3-6 words" if args.field == "Headline" else "6-14 words"
    prompt = f"""Return JSON only with key {args.field.casefold()}.
Write one concise shopper-facing Amazon A+ {args.field} for Section {args.section} of this product creative brief.
Language: {language}. Length: {length_rule}. Use a product-specific benefit, not camera, layout, module, or reference language.
Do not reuse, paraphrase, contain, or overlap any authoritative spreadsheet text listed below.

CREATIVE BRIEF
{text[:12000]}

FORBIDDEN AUTHORITATIVE TEXT
{json.dumps(forbidden, ensure_ascii=False, indent=2)}
"""
    response = requests.post(
        ENDPOINT,
        headers={"Authorization": f"Bearer {args.api_key}", "Content-Type": "application/json"},
        json={"model": MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 120, "temperature": 0.25},
        timeout=120,
    )
    payload = response.json()
    if response.status_code >= 400:
        raise RuntimeError(json.dumps(payload, ensure_ascii=False)[:1000])
    value = extract_json_value(response_text(payload), args.field)
    value_key = normalized_section_text(value)
    if any(value_key == normalized_section_text(item) or value_key in normalized_section_text(item) for item in forbidden):
        raise RuntimeError("Analysis-model replacement still overlaps authoritative spreadsheet text")

    updated = replace_section_field(text, args.section, args.field, value)
    brief_path.write_text(updated, encoding="utf-8-sig")
    log_path = brief_path.parent / "gemini_cross_section_repair.jsonl"
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "model": MODEL,
                    "section": args.section,
                    "field": args.field,
                    "replacement": value,
                    "forbidden_authoritative_text": forbidden,
                },
                ensure_ascii=False,
            )
            + "\n"
        )
    print(value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
