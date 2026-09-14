#!/usr/bin/env python
"""Build premium creative-director module prompts from an A+ creative brief."""

from __future__ import annotations

import argparse
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from excel_reader import find_product_workbook, read_active_worksheet_rows


SECTION_RE = re.compile(r"(?im)^\s*(?:#{1,3}\s*)?Section\s+0?(\d+)\s*(?:[-—–:：/|?？�â€”â€“]\s*)?(.+?)\s*$")
FIELD_LINE_RE = re.compile(
    r"(?im)^[ \t]*(Headline|Copy|Visual Direction|Product Accuracy Notes|Text/Callouts|Negative Prompt|画面建议|产品准确性|文案标注|文案/标注)[ \t]*[:：]?[ \t]*(.*?)[ \t]*$"
)
SIZE_RE = re.compile(r"(\d{3,5})\s*[xX×*]\s*(\d{3,5})\s*px", re.IGNORECASE)
ABS_PATH_RE = re.compile(r"`?[A-Za-z]:\\[^`\n\r]+`?")
CJK_RE = re.compile(
    r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3040-\u30ff\uac00-\ud7af]"
)


DEFAULT_MODULES = [
    {"index": 1, "title": "Hero", "instruction": "Premium opening module with hero model or product-first composition."},
    {"index": 2, "title": "Fit", "instruction": "Fit and silhouette module with front/side/back views and restrained callouts."},
    {"index": 3, "title": "Signature Detail", "instruction": "Signature graphic, hardware, patch, logo, or construction detail."},
    {"index": 4, "title": "Fabric Construction", "instruction": "Material, stitching, texture, hem, neckline, waistband, or finishing module."},
    {"index": 5, "title": "Brand Finish", "instruction": "Branding, labels, logo placement, and refined finishing details."},
    {"index": 6, "title": "Styling", "instruction": "Lifestyle or styling module with commercial streetwear clarity."},
]

SECTION_COPY_RE = re.compile(r"section\s*0?(\d+)", re.IGNORECASE)
HEADLINE_RE = re.compile(r"(?:headline|title|标题|主标题)\s*[:：]\s*(.+?)(?=(?:subheading|copy|body|description|small\s+callouts?|文案|副标题)\s*[:：]|$)", re.IGNORECASE | re.DOTALL)
COPY_RE = re.compile(r"(?:subheading|copy|body|description|文案|副标题)\s*[:：]\s*(.+?)(?=(?:small\s+callouts?)\s*[:：]|$)", re.IGNORECASE | re.DOTALL)
VISUAL_BASELINE_HEADING_RE = re.compile(r"(?im)^\s*##\s+Suggested Visual Baseline\s*$")
NEXT_LEVEL_TWO_HEADING_RE = re.compile(r"(?im)^\s*##\s+")
VISUAL_BASELINE_FIELDS = ("Main color", "Supporting colors", "Background", "Texture", "Style balance")
FIXED_STYLE_BALANCE = "70% Amazon information clarity + 30% light streetwear editorial atmosphere"
POSE_PLAN = [
    "an upright front three-quarter editorial pose, one shoulder subtly advanced, both arms relaxed in a naturally asymmetrical arrangement, face and product silhouette fully visible",
    "a near-frontal stationary fashion pose, shoulders set at subtly different heights, one arm relaxed beside the body and the other softly angled away, with a calm direct gaze",
    "a controlled front-side editorial stance, torso gently rotated toward camera, arms held in a restrained asymmetrical composition, with the complete product front unobstructed",
    "an upright three-quarter magazine pose, head turned slightly off-camera, one shoulder closer to camera, both hands relaxed away from key product details",
    "a calm stationary fashion stance, one elbow softly angled while the opposite arm remains lowered, shoulders subtly asymmetrical, with hands kept away from the product's key design areas",
    "an upright near-frontal hero pose, direct eye contact, chin level, arms relaxed at different natural angles, creating confident streetwear presence without exaggerated movement",
    "a balanced front three-quarter magazine stance, chin raised slightly, gaze directed just past camera, one arm softly angled and the other resting naturally",
    "a refined editorial pose with one hand lightly arranging the hair beside the face, the other arm relaxed, torso facing camera and product silhouette unobstructed",
    "a clean stationary hero stance, both arms lowered in different relaxed positions, one shoulder subtly advanced, with a confident expression and clear product proportions",
]

PROHIBITED_POSE_RE = re.compile(
    r"(?i)(?:\blow[- ]angle\b|\bwalk(?:ing)?\b|\bstride\b|\bcross[- ]step\b|"
    r"\bcrossed legs?\b|\blegs? crossed\b|\bfeet apart\b|\bwide stance\b|"
    r"\bback[- ]turn\b|\brear[- ]facing\b|\bknee[- ]bend\b|\bknee bent\b|"
    r"\bone knee bent\b|\bfront foot crossing\b|\beditorial step\b)"
)

for _pose in POSE_PLAN:
    if PROHIBITED_POSE_RE.search(_pose):
        raise RuntimeError(f"Prohibited Section 1 pose template: {_pose}")

SECTION_HEADLINE_THEMES = {
    1: ("STREET PRESENCE", "A bold first look built around the real product attitude."),
    2: ("RELAXED PROPORTIONS", "Clean volume, easy movement, and everyday streetwear shape."),
    3: ("FRONT TO BACK", "On-body energy meets flat-lay product clarity."),
    4: ("DETAILS IN FOCUS", "Texture, stitching, and finish shown with close-up precision."),
    5: ("EVERYDAY SCENARIOS", "Reserved space for real-life styling moments."),
}

GERMAN_MARKER_RE = re.compile(
    r"[äöüÄÖÜß]|\b(?:und|oder|mit|ohne|für|damen|herren|mädchen|jungen|kapuze|baumwolle|"
    r"weich|bequem|lässig|alltag|tasche|reißverschluss|verstellbar|atmungsaktiv|stoff|"
    r"strick|hose|jacke|mütze|kappe|frühling|herbst|sommer|winter|schnitt|passform)\b",
    re.IGNORECASE,
)


def read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def read_analysis(path: Path | None) -> dict[str, object] | None:
    if not path:
        return None
    if not path.exists():
        raise SystemExit(f"Template analysis not found: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


NO_LOGO_TERMS = (
    "不要出现品牌logo",
    "不出现品牌logo",
    "不要出现logo",
    "不出现logo",
    "不露出logo",
    "无logo",
    "去logo",
    "禁止logo",
    "不要品牌标识",
    "不出现品牌标识",
    "不要出现品牌标识",
    "no logo",
    "logo-free",
    "do not show logo",
    "do not include logo",
    "do not display logo",
    "without logo",
    "no brand logo",
    "no wordmark",
    "hide logo",
    "remove logo",
)


def template_disables_logo_from_text(text: str) -> bool:
    compact = re.sub(r"\s+", "", text.casefold())
    lowered = text.casefold()
    chinese_no_logo_markers = (
        "\u4e0d",  # 不
        "\u65e0",  # 无
        "\u7981",  # 禁
        "\u53bb",  # 去
        "\u9690\u85cf",  # 隐藏
        "\u5220\u9664",  # 删除
        "\u907f\u514d",  # 避免
    )
    if "logo" in compact and any(marker in compact for marker in chinese_no_logo_markers):
        return True
    if any(term.casefold().replace(" ", "") in compact for term in NO_LOGO_TERMS):
        return True
    patterns = (
        r"\b(no|without|hide|remove)\s+(brand\s+)?(logo|wordmark|brand\s+mark)\b",
        r"\bdo\s+not\s+(show|include|display|use)\s+(brand\s+)?(logo|wordmark|brand\s+mark)\b",
    )
    return any(re.search(pattern, lowered) for pattern in patterns)


def analysis_disables_logo(analysis: dict[str, object] | None) -> bool:
    if not analysis:
        return False
    chunks: list[str] = []
    raw_requirements = analysis.get("design_requirements")
    if isinstance(raw_requirements, list):
        chunks.extend(str(item) for item in raw_requirements)
    raw_modules = analysis.get("modules")
    if isinstance(raw_modules, list):
        for module in raw_modules:
            if isinstance(module, dict):
                chunks.extend(str(module.get(key, "")) for key in ("title", "instruction"))
    return template_disables_logo_from_text("\n".join(chunks))


def section_disables_logo(global_context: str, section: dict[str, object]) -> bool:
    fields = section.get("fields") if isinstance(section.get("fields"), dict) else {}
    text = "\n".join(
        [
            global_context,
            str(section.get("title") or ""),
            str(section.get("block") or ""),
            *[str(value) for value in fields.values()],
        ]
    )
    return template_disables_logo_from_text(text)


def no_logo_instruction(visible_language: str) -> str:
    if visible_language == "German":
        return (
            "Keine Marken-LOGOs, Wortmarken, Brand Marks, Marken-Badges oder logoartigen Embleme als separate "
            "Layout-Designelemente hinzufügen, vergrößern, neu zeichnen oder dekorativ verwenden. Kleine Logos, "
            "Labels, Stickereien, Tags, Patches oder Markendetails, die bereits natürlich auf den Produktreferenzen "
            "vorhanden sind, als Teil des tatsächlichen Kleidungsstücks/Produkts erhalten."
        )
    return (
        "Do not add, enlarge, redesign, or use any brand LOGO, wordmark, brand mark, brand badge, or logo-like emblem "
        "as a separate layout design element. Preserve any small logo, label, embroidery, tag, patch, or brand detail "
        "that already exists naturally on the product reference images as part of the actual garment/product."
    )


def template_design_requirements(analysis: dict[str, object] | None, visible_language: str = "English") -> str:
    if not analysis:
        return ""
    raw = analysis.get("design_requirements")
    if not isinstance(raw, list):
        return ""
    requirements = [str(item).strip() for item in raw if str(item).strip()]
    if not requirements:
        return ""

    logo_disabled = analysis_disables_logo(analysis)
    translated: list[str] = []
    for requirement in requirements:
        lowered = requirement.lower()
        if logo_disabled and ("logo" in lowered or "品牌" in requirement or "标识" in requirement):
            if "poppins" in lowered or "字体" in requirement:
                translated.append("Use Poppins for all visible typography.")
            continue
        if "poppins" in lowered and ("logo" in lowered or "品牌logo" in lowered):
            if visible_language == "German":
                translated.append(
                    "Use Poppins for all visible typography. Match any visible brand LOGO exactly to the attached LOGO reference image; do not redesign, reinterpret, or invent the logo."
                )
            else:
                translated.append(
                    "Use Poppins for all visible typography. Match any visible brand LOGO exactly to the attached LOGO reference image; do not redesign, reinterpret, or invent the logo."
                )
        elif "poppins" in lowered or "字体" in requirement:
            translated.append("Use Poppins for all visible typography.")
        elif "logo" in lowered or "品牌logo" in lowered:
            translated.append(
                "Match any visible brand LOGO exactly to the attached LOGO reference image; do not redesign, reinterpret, or invent the logo."
            )
        else:
            translated.append(requirement)
    if logo_disabled:
        translated.append(no_logo_instruction(visible_language))

    unique: list[str] = []
    seen: set[str] = set()
    for item in translated:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return "\n".join(f"- {item}" for item in unique)


def find_excel(product_dir: Path) -> Path | None:
    return find_product_workbook(product_dir)


def cell_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def normalize_copy_text(value: str) -> str:
    value = re.sub(r"\s*/\s*", "\n", value.strip())
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def preserve_section_copy_text(value: str) -> str:
    """Keep spreadsheet Section n copy as authored for the final Copy field."""
    lines = [re.sub(r"[ \t]+", " ", line).rstrip() for line in value.strip().splitlines()]
    return "\n".join(line for line in lines if line.strip()).strip()


def split_section_copy_blob(value: str) -> dict[str, str]:
    normalized = normalize_copy_text(value)
    result: dict[str, str] = {}
    headline_match = HEADLINE_RE.search(normalized)
    copy_match = COPY_RE.search(normalized)
    if headline_match:
        result["Headline"] = headline_match.group(1).strip(" -/：:")
    if copy_match:
        result["Copy"] = copy_match.group(1).strip(" -/：:")
    if result:
        return result
    cleaned = re.sub(r"^(?:headline|title|copy|body|subheading|文案|标题|主标题|副标题)\s*[:：]\s*", "", normalized, flags=re.IGNORECASE)
    return {"Copy": cleaned}


def read_excel_section_copy(product_dir: Path) -> dict[int, dict[str, str]]:
    excel_path = find_excel(product_dir)
    if not excel_path:
        return {}
    result: dict[int, dict[str, str]] = {}
    try:
        _sheet_name, worksheet_rows, _dimensions = read_active_worksheet_rows(excel_path)
        for row in worksheet_rows:
            cells = [cell_text(value) for value in row]
            if not any(cells):
                continue
            key_index = next(
                (idx for idx, cell in enumerate(cells) if SECTION_COPY_RE.search(cell)),
                None,
            )
            if key_index is None:
                continue
            key = cells[key_index]
            values = [value for value in cells[key_index + 1 :] if value]
            match = SECTION_COPY_RE.search(key)
            if not match or not values:
                continue
            index = int(match.group(1))
            lowered = key.casefold()
            bucket = result.setdefault(index, {})
            value = " / ".join(values)
            plain_section_key = bool(re.fullmatch(r"\s*section\s*0?\d+\s*", key, flags=re.IGNORECASE))
            if plain_section_key:
                bucket["Copy"] = preserve_section_copy_text(value)
                bucket["Copy Source"] = "1-产品属性表.xlsx"
            elif any(term in lowered for term in ("headline", "title", "标题", "主标题")):
                bucket.update(split_section_copy_blob(value) if ("subheading" in value.lower() or "copy" in value.lower() or "description" in value.lower() or "small callout" in value.lower() or "文案" in value) else {"Headline": normalize_copy_text(value)})
                if bucket.get("Headline"):
                    bucket["Headline Source"] = "1-产品属性表.xlsx"
            elif any(term in lowered for term in ("callout", "label", "标注", "卖点")):
                bucket["Text/Callouts"] = normalize_copy_text(value)
            elif any(term in lowered for term in ("copy", "body", "description", "文案", "描述", "副标题")):
                bucket.update(split_section_copy_blob(value))
            else:
                bucket.update(split_section_copy_blob(value))
    except Exception:
        return {}
    return result


def excel_value_language(product_dir: Path) -> str:
    """Detect the language used in spreadsheet values, not field labels."""
    excel_path = find_excel(product_dir)
    if not excel_path:
        return "English"
    value_texts: list[str] = []
    marketplace = ""
    try:
        _sheet_name, worksheet_rows, _dimensions = read_active_worksheet_rows(excel_path)
        for row in worksheet_rows:
            cells = [cell_text(value) for value in row]
            if not any(cells):
                continue
            # Treat the first non-empty cell as a field/key and only analyze value cells.
            first = next((idx for idx, cell in enumerate(cells) if cell), None)
            if first is None:
                continue
            key = cells[first].strip().casefold()
            if key == "marketplace" and first + 1 < len(cells):
                marketplace = cells[first + 1].strip().upper()
            value_texts.extend(cell for cell in cells[first + 1 :] if cell)
    except Exception:
        return "English"
    if marketplace in {"DE", "AT", "CH"}:
        return "German"
    if marketplace in {"US", "UK", "CA", "AU"}:
        return "English"
    joined = " ".join(value_texts)
    marker_count = len(GERMAN_MARKER_RE.findall(joined))
    has_german_char = bool(re.search(r"[äöüÄÖÜß]", joined))
    if has_german_char or marker_count >= 3:
        return "German"
    return "English"


def batch_pose_for_product(product_dir: Path) -> str:
    siblings = sorted(
        [
            path
            for path in product_dir.parent.iterdir()
            if path.is_dir() and path.name.lower() != "logo"
        ],
        key=lambda item: item.name.casefold(),
    )
    try:
        index = siblings.index(product_dir)
    except ValueError:
        index = 0
    pose = POSE_PLAN[index % len(POSE_PLAN)]
    if PROHIBITED_POSE_RE.search(pose):
        raise RuntimeError(f"Prohibited Section 1 pose selected: {pose}")
    return pose


def apply_excel_copy_overrides(
    sections: list[dict[str, object]],
    overrides: dict[int, dict[str, str]],
) -> None:
    for section in sections:
        if section_requests_no_visible_copy(section):
            continue
        index = int(section.get("index", 0))
        fields = section.get("fields")
        if not isinstance(fields, dict):
            fields = {}
            section["fields"] = fields
        for key in ("Headline", "Copy", "Text/Callouts"):
            value = str(overrides.get(index, {}).get(key) or "").strip()
            if not value:
                continue
            fields[key] = value
            if key in {"Headline", "Copy"}:
                fields[f"{key} Source"] = "1-产品属性表.xlsx"


def normalized_section_text(value: str) -> str:
    value = sanitize_prompt_context(value).casefold()
    value = re.sub(r"[^0-9a-zäöüß]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def validate_excel_section_ownership(
    sections: list[dict[str, object]],
    overrides: dict[int, dict[str, str]],
) -> None:
    """Fail when Gemini moved an Excel Section N headline/copy to another Section."""
    for owner_index, fields in sorted(overrides.items()):
        for owner_field in ("Headline", "Copy"):
            authoritative = str(fields.get(owner_field) or "").strip()
            authoritative_key = normalized_section_text(authoritative)
            if not authoritative_key:
                continue
            for section in sections:
                candidate_index = int(section.get("index", 0))
                if candidate_index == owner_index:
                    continue
                candidate_fields = section.get("fields") if isinstance(section.get("fields"), dict) else {}
                for candidate_field in ("Headline", "Copy"):
                    candidate = str(candidate_fields.get(candidate_field) or "").strip()
                    candidate_key = normalized_section_text(candidate)
                    if not candidate_key:
                        continue
                    exact = candidate_key == authoritative_key
                    substantial_containment = (
                        len(authoritative_key) >= 30
                        and (authoritative_key in candidate_key or candidate_key in authoritative_key)
                        and min(len(candidate_key), len(authoritative_key)) / max(len(candidate_key), len(authoritative_key)) >= 0.80
                    )
                    if exact or substantial_containment:
                        raise SystemExit(
                            f"Excel Section {owner_index} {owner_field} was found in Section {candidate_index} {candidate_field}. "
                            "Excel Section N Headline/Copy may only appear in the matching Section N. "
                            "Correct the Gemini creative brief before building prompts."
                        )


def validate_cross_section_duplicates(sections: list[dict[str, object]]) -> None:
    """Reject duplicate resolved headlines/copy that remain after generated-text de-duplication."""
    for field in ("Headline", "Copy"):
        seen: list[tuple[int, str, str]] = []
        for section in sections:
            if section_requests_no_visible_copy(section):
                continue
            index = int(section.get("index", 0))
            fields = section.get("fields") if isinstance(section.get("fields"), dict) else {}
            value = str(fields.get(f"Resolved {field}") or fields.get(field) or "").strip()
            key = normalized_section_text(value)
            if not key:
                continue
            for previous_index, previous_key, previous_value in seen:
                exact = key == previous_key
                near = field == "Copy" and min(len(key), len(previous_key)) >= 40 and SequenceMatcher(None, key, previous_key).ratio() >= 0.92
                if exact or near:
                    raise SystemExit(
                        f"Cross-section duplicate {field} detected between Section {previous_index} and Section {index}: "
                        f"{previous_value!r}. Rewrite the generated field or correct its Excel ownership before image generation."
                    )
            seen.append((index, key, value))


def apply_section_one_pose(sections: list[dict[str, object]], pose: str) -> None:
    for section in sections:
        if int(section.get("index", 0)) != 1:
            continue
        fields = section.get("fields")
        if not isinstance(fields, dict):
            fields = {}
            section["fields"] = fields
        visual = str(fields.get("Visual Direction") or section.get("block") or "")
        fields["Visual Direction"] = (
            f"{visual}\n\nSection 1 unique pose direction for this batch: {pose}. "
            "Use this as a vivid fashion-magazine body language cue while preserving the supplied model identity and accurate product fit."
        ).strip()
        fields["Pose Direction"] = pose


def analysis_module_size(analysis: dict[str, object] | None, text: str) -> tuple[int, int]:
    if analysis:
        data = analysis.get("module_size")
        if isinstance(data, dict):
            return int(data.get("width", 1464)), int(data.get("height", 600))
    for line in text.splitlines():
        if any(label in line for label in ("单张模块尺寸", "module size", "Module size")):
            match = SIZE_RE.search(line)
            if match:
                return int(match.group(1)), int(match.group(2))
    return (1464, 600)


def canonical_field(label: str) -> str:
    mapping = {
        "headline": "Headline",
        "copy": "Copy",
        "visual direction": "Visual Direction",
        "画面建议": "Visual Direction",
        "product accuracy notes": "Product Accuracy Notes",
        "产品准确性": "Product Accuracy Notes",
        "text/callouts": "Text/Callouts",
        "文案标注": "Text/Callouts",
        "文案/标注": "Text/Callouts",
        "negative prompt": "Negative Prompt",
    }
    return mapping.get(label.strip().lower(), label.strip())


def parse_fields(block: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    matches = list(FIELD_LINE_RE.finditer(block))
    for idx, match in enumerate(matches):
        key = canonical_field(match.group(1))
        inline_value = match.group(2).strip()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(block)
        body = block[start:end].strip()
        value = "\n".join(part for part in [inline_value, body] if part).strip()
        if value:
            fields[key] = re.sub(r"\n{3,}", "\n\n", value)
    return fields


def parse_sections(text: str, analysis: dict[str, object] | None) -> list[dict[str, object]]:
    matches = list(SECTION_RE.finditer(text))
    sections: list[dict[str, object]] = []
    analysis_modules: dict[int, dict[str, object]] = {}
    if analysis:
        modules = analysis.get("modules") or []
        if isinstance(modules, list):
            for module in modules:
                try:
                    analysis_modules[int(module.get("index", 0))] = module
                except (TypeError, ValueError):
                    continue
    for idx, match in enumerate(matches):
        index = int(match.group(1))
        raw_title = match.group(2).strip()
        title = clean_section_title(raw_title, index)
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        block = text[start:end].strip()
        analysis_instruction = str(analysis_modules.get(index, {}).get("instruction") or "").strip()
        semantic_block = "\n".join(part for part in (raw_title, block, analysis_instruction) if part).strip()
        fields = parse_fields(block)
        if analysis_instruction and not fields.get("Visual Direction"):
            fields["Visual Direction"] = analysis_instruction
        sections.append({"index": index, "title": title, "block": semantic_block or block, "fields": fields})

    if sections:
        return sorted(sections, key=lambda item: int(item["index"]))

    if analysis:
        modules = analysis.get("modules") or []
        if isinstance(modules, list) and modules:
            return [
                {
                    "index": int(module.get("index", i + 1)),
                    "title": clean_section_title(str(module.get("title") or ""), int(module.get("index", i + 1))),
                    "block": str(module.get("instruction") or ""),
                    "fields": {"Visual Direction": str(module.get("instruction") or "")},
                }
                for i, module in enumerate(modules)
            ]

    return [
        {"index": item["index"], "title": item["title"], "block": item["instruction"], "fields": {"Visual Direction": item["instruction"]}}
        for item in DEFAULT_MODULES
    ]


def extract_global_context(text: str) -> str:
    first_section = SECTION_RE.search(text)
    global_text = text[: first_section.start()].strip() if first_section else text.strip()
    return sanitize_prompt_context(global_text)[:8000]


def clean_section_title(title: str, index: int) -> str:
    cleaned = sanitize_prompt_context(title)
    cleaned = re.sub(rf"(?i)^section\s*0?{index}\b", "", cleaned).strip()
    cleaned = re.sub(r"^[\s?？�\-—–:：/\\|.â€”â€“]+", "", cleaned).strip()
    cleaned = re.sub(r"[\s?？�\-—–:：/\\|.â€”â€“]+$", "", cleaned).strip()
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned or cleaned in {"?", "？", "�"} or not re.search(r"[A-Za-z0-9]", cleaned):
        return f"Section {index}"
    return cleaned


def sanitize_prompt_context(text: str) -> str:
    """Remove internal notes, local paths, and non-English text that confuse image models."""
    cleaned_lines: list[str] = []
    skip_patterns = [
        r"replace\s+the\s+template",
        r"original\s+men'?s\s+liquid\s+metal",
        r"liquid\s+metal\s+tee\s+direction",
        r"template'?s\s+original",
        r"module\s+purpose\s+from\s+template",
        r"use\s+only\s+verified\s+product\s+details\s+from\s+the\s+spreadsheet",
        r"\bspreadsheet\b",
        r"\bsource\s+references\b",
        r"\bverified\s+product\s+details\b",
    ]
    for line in text.splitlines():
        lowered = line.lower()
        if any(re.search(pattern, lowered) for pattern in skip_patterns):
            continue
        line = ABS_PATH_RE.sub("[attached reference image]", line)
        line = CJK_RE.sub("", line)
        line = re.sub(r"[ \t]{2,}", " ", line).strip()
        cleaned_lines.append(line)
    cleaned = "\n".join(cleaned_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def final_api_prompt_text(prompt: str) -> str:
    """Final prompt body intended to match the text submitted to image APIs before reference-map injection."""
    cleaned = prompt.replace("\ufeff", "")
    internal_blocks = (
        "Product Folder",
        "Reference Images To Inspect",
        "Logo References",
        "Visual Observations",
        "Template Excerpt",
        "Images To Inspect",
        "Reference Images",
    )
    for heading in internal_blocks:
        cleaned = re.sub(
            rf"(?ims)^##\s*{re.escape(heading)}\b.*?(?=^##\s+|\Z)",
            "\n",
            cleaned,
        )
    kept_lines: list[str] = []
    for line in cleaned.splitlines():
        stripped = line.strip()
        lower = stripped.casefold()
        if "\\\\" in stripped or re.search(r"[a-zA-Z]:\\", stripped):
            continue
        if lower.startswith(("## product folder", "## reference images to inspect", "## logo references", "## visual observations")):
            continue
        if stripped.startswith("`") and ("\\\\" in stripped or ":\\" in stripped):
            continue
        if stripped.startswith("- `") and ("\\\\" in stripped or ":\\" in stripped):
            continue
        if stripped in {"Fill this section after inspecting every distinct reference image:", "None found"}:
            continue
        kept_lines.append(line.rstrip())
    cleaned = "\n".join(kept_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned + "\n"


def strip_reference_claims_for_no_reference(prompt: str) -> str:
    prompt = re.sub(
        r"(?is)\n?Reference note:\s*.*?(?=\n(?:Negative Prompt|Attached Reference Image Map|Logo Reference Requirement|Text / Callouts|Product Accuracy|Visual Direction|No LOGO rule|No reference images rule)\s*:|\Z)",
        "\n",
        prompt,
    )
    prompt = re.sub(
        r"(?is)\n?Referenzhinweis:\s*.*?(?=\n(?:Negative Prompt|Attached Reference Image Map|LOGO-Referenz|Text / Callouts|Produktgenauigkeit|Visuelle Richtung|Keine LOGO-Regel|Keine Referenzbilder-Regel)\s*:|\Z)",
        "\n",
        prompt,
    )
    replacements = {
        r"\bthe attached product reference images\b": "the written product details in this prompt",
        r"\battached product reference images\b": "written product details in this prompt",
        r"\battached references\b": "the written prompt",
        r"\bsupplied references\b": "the written product details in this prompt",
        r"\bsupplied reference images\b": "the written product details in this prompt",
        r"\bangehängten Produktreferenzen\b": "Produktinformationen in diesem Prompt",
        r"\bangehängten Referenzen\b": "schriftlichen Prompt",
        r"\bReferenzbilder angehängt\b": "keine Referenzbilder angehängt",
    }
    for source, target in replacements.items():
        prompt = re.sub(source, target, prompt, flags=re.IGNORECASE)
    prompt = re.sub(r"\n{3,}", "\n\n", prompt)
    return prompt.strip() + "\n"


def image_prompt_accuracy(
    global_context: str,
    fallback: str = "",
    visible_language: str = "English",
    no_logo: bool = False,
    no_references: bool = False,
) -> str:
    """Return concrete product accuracy guidance the image model can actually use."""
    if no_references:
        if visible_language == "German":
            base = "Nutze nur die konkreten Produktinformationen in diesem Prompt. Es werden keine Referenzbilder angehängt; erwähne oder erwarte keine angehängten Referenzen."
            return f"{base} {no_logo_instruction(visible_language)}" if no_logo else base
        base = "Use only the concrete product information written in this prompt. No reference images are attached for this module; do not mention or rely on attached references."
        return f"{base} {no_logo_instruction(visible_language)}" if no_logo else base
    if visible_language == "German":
        fields = {
            "Produkttyp": product_fact(global_context, "Product type"),
            "Farbe": product_fact(global_context, "Color"),
            "Passform": product_fact(global_context, "Fit"),
            "Material": product_fact(global_context, "Fabric"),
            "Details": product_fact(global_context, "Key features"),
            "Muster/Grafik": product_fact(global_context, "Pattern / graphic"),
            "Marke": product_fact(global_context, "Brand"),
        }
    else:
        fields = {
            "product type": product_fact(global_context, "Product type"),
            "color": product_fact(global_context, "Color"),
            "fit": product_fact(global_context, "Fit"),
            "fabric": product_fact(global_context, "Fabric"),
            "features": product_fact(global_context, "Key features"),
            "pattern": product_fact(global_context, "Pattern / graphic"),
            "brand": product_fact(global_context, "Brand"),
        }
    details = [f"{label}: {value}" for label, value in fields.items() if value]
    if details:
        if visible_language == "German":
            base = "Erhalte das tatsächliche Kleidungsstück exakt: " + "; ".join(details[:6]) + ". Gleiche Farbe, Silhouette, Konstruktion und Print-Platzierung mit den angehängten Produktreferenzen ab."
            return f"{base} {no_logo_instruction(visible_language)}" if no_logo else base
        base = "Preserve the actual garment exactly: " + "; ".join(details[:6]) + ". Match the attached product reference images for color, silhouette, construction, and print placement."
        return f"{base} {no_logo_instruction(visible_language)}" if no_logo else base

    cleaned_fallback = sanitize_prompt_context(fallback)
    if cleaned_fallback:
        return f"{cleaned_fallback} {no_logo_instruction(visible_language)}".strip() if no_logo else cleaned_fallback
    if visible_language == "German":
        base = "Gleiche Farbe, Silhouette, Konstruktion und Print-Platzierung exakt mit den angehängten Produktreferenzen ab."
        return f"{base} {no_logo_instruction(visible_language)}" if no_logo else base
    base = "Match the attached product reference images exactly for garment color, silhouette, construction, and print placement."
    return f"{base} {no_logo_instruction(visible_language)}" if no_logo else base


def section_intent(section: dict[str, object], index: int) -> str:
    text = f"{section.get('title', '')}\n{section.get('block', '')}".lower()
    if section_requests_no_visible_copy(section) or any(term in text for term in ("用于后续替换为网红图", "background only", "text-free background")):
        return "replacement_background"
    if any(term in text for term in ("品牌banner", "banner", "hero", "brand banner", "首图", "主图")):
        return "hero"
    if any(term in text for term in ("版型", "廓形", "剪裁", "fit", "silhouette", "size", "尺寸", "adjustable")):
        return "fit"
    if any(term in text for term in ("正背面", "正反面", "平铺", "front and back", "front/back", "flat lay", "flat-lay")):
        if section_uses_model(section):
            return "model_flatlay"
        return "front_back"
    if any(term in text for term in ("细节", "工艺", "面料", "材质", "微距", "品质", "detail", "fabric", "material", "macro", "construction", "quality")):
        return "detail"
    if any(term in text for term in ("场景", "礼物", "gift", "occasion", "lifestyle", "scene")):
        return "lifestyle"
    if section_uses_model(section):
        return "model"
    return {1: "hero", 2: "fit", 3: "model_flatlay", 4: "detail"}.get(index, "overview")


def section_semantic_text(section: dict[str, object]) -> str:
    fields = section.get("fields") if isinstance(section.get("fields"), dict) else {}
    parts = [
        str(section.get("title") or ""),
        str(section.get("block") or ""),
        *[str(value) for value in fields.values()],
    ]
    return "\n".join(parts)


def has_any_term(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.casefold()
    return any(term.casefold() in lowered for term in terms)


def template_layout_task(
    section: dict[str, object],
    index: int,
    visible_language: str = "English",
    no_logo: bool = False,
) -> str:
    """Convert the root template's Section n purpose into a concrete composition task."""
    text = section_semantic_text(section)
    intent = section_intent(section, index)
    no_people = has_any_term(
        text,
        (
            "\u4e0d\u8981\u51fa\u73b0\u4eba\u7269",  # 不要出现人物
            "\u4e0d\u51fa\u73b0\u4eba\u7269",  # 不出现人物
            "\u65e0\u4eba\u7269",  # 无人物
            "\u4e0d\u8981\u6a21\u7279",  # 不要模特
            "no people",
            "no person",
            "no model",
            "without people",
        ),
    )
    multi_angle = has_any_term(
        text,
        (
            "\u591a\u89d2\u5ea6",  # 多角度
            "\u540c\u4e00\u5f20\u56fe",  # 同一张图
            "multi-angle",
            "multiple angles",
            "same image",
            "in one image",
        ),
    )
    flatlay = has_any_term(
        text,
        (
            "\u5e73\u94fa",  # 平铺
            "\u6b63\u80cc\u9762",  # 正背面
            "\u6b63\u53cd\u9762",  # 正反面
            "flat lay",
            "flat-lay",
            "front/back",
            "front and back",
        ),
    )
    detail = has_any_term(
        text,
        (
            "\u7ec6\u8282",  # 细节
            "\u5fae\u8ddd",  # 微距
            "\u5de5\u827a",  # 工艺
            "\u54c1\u8d28",  # 品质
            "\u9762\u6599",  # 面料
            "detail",
            "macro",
            "close-up",
            "construction",
            "fabric",
            "quality",
        ),
    )
    replacement_background = intent == "replacement_background" or has_any_term(
        text,
        (
            "\u7528\u4e8e\u540e\u7eed\u66ff\u6362\u4e3a\u7f51\u7ea2\u56fe",  # 用于后续替换为网红图
            "\u80cc\u666f\u56fe",  # 背景图
            "\u4e0d\u9700\u8981\u4efb\u4f55\u6587\u6848",  # 不需要任何文案
            "background only",
            "text-free background",
            "later replacement",
        ),
    )
    model = (not no_people) and (
        section_uses_model(section)
        or has_any_term(
            text,
            (
                "\u6a21\u7279",  # 模特
                "\u4eba\u7269",  # 人物
                "\u4eba\u6a21",  # 人模
                "\u4e0a\u8eab",  # 上身
                "\u7a7f\u7740",  # 穿着
                "\u7a7f\u642d",  # 穿搭
                "model",
                "person",
                "people",
                "on-body",
                "wearing",
            ),
        )
    )
    logo_phrase_en = " with a clean brand/LOGO zone if logo usage is allowed" if not no_logo else " without using a standalone logo as a layout element"
    logo_phrase_de = " mit sauberer Marken-/LOGO-Zone, falls Logo-Nutzung erlaubt ist" if not no_logo else " ohne ein separates Logo als Layout-Element zu verwenden"

    if visible_language == "German":
        prefix = "Kompositionsaufgabe:"
        if replacement_background:
            return (
                f"{prefix} Ein textfreies, menschenfreies, stilistisch passendes Hintergrundmodul fuer spaetere "
                "Influencer-Ersetzung gestalten; keine Social-UI, keine Platzhalter-Farbfelder, sofern nicht ausdruecklich verlangt."
            )
        if index == 1 or intent == "hero":
            return (
                f"{prefix} Ein horizontales Hero-/Brand-Banner mit einem klaren Hauptmodel im Produkt aufbauen"
                f"{logo_phrase_de}; der Schnitt und die erste Produktwirkung muessen sofort lesbar sein."
            )
        if model and multi_angle:
            return (
                f"{prefix} Ein Model-Fit-Board mit mehreren Modelwinkeln in derselben Modulflache gestalten, "
                "z. B. Front, Dreiviertel/Seite und Ruecken, damit Passform und Silhouette klar vergleichbar sind."
            )
        if model and flatlay:
            return (
                f"{prefix} Eine kombinierte Model-plus-Flat-Lay-Komposition erstellen: Model-Styling als Kontext, "
                "dazu klare Front- und Rueckseiten-/Flat-Lay-Produktansichten als Produktbeweis."
            )
        if flatlay:
            return (
                f"{prefix} Eine produktzentrierte Front-/Rueckseiten-Flat-Lay-Komposition ohne ablenkende Szene gestalten, "
                "damit Form, Proportion und Konstruktion sofort vergleichbar sind."
            )
        if detail or no_people:
            return (
                f"{prefix} Eine menschenfreie Detail-/Makro-Collage mit mehreren Produkt-Crops gestalten; "
                "Stoff, Naehte, Print, Stickerei, Taschen, Hardware oder Abschluesse klar und hochwertig zeigen."
            )
        if intent == "fit" or model:
            return (
                f"{prefix} Ein klares On-Body-Fit-Modul mit einem dominanten Modelmoment gestalten, "
                "damit Passform, Laenge, Volumen und Beweglichkeit des Produkts schnell verstaendlich sind."
            )
        return f"{prefix} Ein einzelnes, klares Amazon A+ Modul mit produktzentrierter Hierarchie und einer Hauptaussage gestalten."

    prefix = "Layout task:"
    if replacement_background:
        return (
            f"{prefix} Create a text-free, people-free, style-matched background module for later influencer replacement; "
            "no social UI and no color-block placeholders unless the template explicitly asks for them."
        )
    if index == 1 or intent == "hero":
        return (
            f"{prefix} Build a horizontal hero/brand banner around one clear main model wearing the product"
            f"{logo_phrase_en}; make the fit and first product impression immediately readable."
        )
    if model and multi_angle:
        return (
            f"{prefix} Create a model fit board with multiple model angles inside the same module, such as front, "
            "three-quarter/side, and back views, so the fit and silhouette are easy to compare."
        )
    if model and flatlay:
        return (
            f"{prefix} Create a combined model-plus-flat-lay composition: use the model as styling context and include "
            "clear front/back or flat-lay product views as the product proof."
        )
    if flatlay:
        return (
            f"{prefix} Create a product-centered front/back flat-lay composition with minimal distraction, so the shape, "
            "proportion, and construction can be compared clearly."
        )
    if detail or no_people:
        return (
            f"{prefix} Create a people-free detail/macro collage with multiple product crops; show fabric, stitching, "
            "print, embroidery, pockets, hardware, trims, or finish clearly and premiumly."
        )
    if intent == "fit" or model:
        return (
            f"{prefix} Create a clear on-body fit module with one dominant model moment, making the product's fit, "
            "length, volume, and movement easy to understand."
        )
    return f"{prefix} Create one clean Amazon A+ module with product-first hierarchy and a single clear selling idea."


def merge_layout_and_visual(layout_task: str, visual: str) -> str:
    layout = layout_task.strip()
    body = visual.strip()
    if not layout:
        return body
    if not body:
        return layout
    normalized_layout = re.sub(r"\s+", " ", layout).casefold()
    normalized_body = re.sub(r"\s+", " ", body).casefold()
    if normalized_layout in normalized_body:
        return body
    return f"{layout}\n{body}"


def product_phrase(global_context: str) -> str:
    color = product_fact(global_context, "Color")
    fit = product_fact(global_context, "Fit")
    product_type = product_fact(global_context, "Product type") or "apparel"
    parts = [part for part in (color, fit, product_type) if part]
    return " ".join(parts) if parts else product_type


def feature_phrase(global_context: str, fallback: str = "") -> str:
    features = product_feature_list(global_context)
    if not features:
        return fallback
    text = "; ".join(features)
    return text[:180].rstrip(" ;,")


def product_specific_visual_direction(
    intent: str,
    category: str,
    global_context: str,
    visible_language: str,
) -> str:
    if intent not in {"fit", "model_flatlay", "detail", "lifestyle"}:
        return ""

    product = product_phrase(global_context)
    product_type = product_fact(global_context, "Product type") or "apparel"
    blob = product_signal_blob(global_context)
    primary = select_feature(global_context, ("graphic", "embroidery", "print", "rhinestone", "pinstripe", "pleat", "pocket", "mesh", "zip", "fabric", "waist", "hem"), 0)
    secondary = select_feature(global_context, ("fit", "shape", "leg", "waist", "closure", "fabric", "texture", "pocket", "adjustable"), 1)
    if secondary.casefold() == primary.casefold():
        secondary = next(
            (item for item in feature_candidates(global_context) if item.casefold() != primary.casefold()),
            product_type,
        )

    if visible_language == "German":
        if intent == "fit":
            if "rhinestone" in blob or "cargo" in blob:
                return f"Zeige {product} als bewegliche Wide-Leg-Hose; elastischer Bund, Cargo-Struktur, Rhinestone-Akzente und verstellbarer Saum sollen lesbar bleiben."
            if "dachshund" in blob:
                return f"Zeige {product} mit lockerer Shorts-Proportion; Bund, Kordelzug, Sweatstoff und Dachshund-Stickerei klar, aber werblich inszenieren."
            if "pinstripe" in blob or "pleat" in blob:
                return f"Inszeniere {product} mit sichtbaren Frontfalten, Pinstripe-Webstruktur und weitem Beinvolumen in einer klaren Fashion-Komposition."
        if intent == "model_flatlay":
            return f"Verbinde Styling-Moment und Produktklarheit rund um {primary}; {secondary.lower()} soll die konkrete Produktstory tragen."
        if intent == "detail":
            return f"Nutze hochwertige Detailausschnitte fuer {primary}; Textur, Verarbeitung und echte Produktmerkmale von {product_type} muessen praezise bleiben."
        return f"Baue eine ruhige Lifestyle-Szene um {product}, abgeleitet von {primary}, mit kaufnaher A+ Ordnung."

    if intent == "fit":
        if "rhinestone" in blob or "cargo" in blob:
            return f"Show {product} in an upright near-frontal stationary product pose; keep the elastic waist, cargo structure, rhinestone accents, and adjustable hems clearly readable."
        if "dachshund" in blob:
            return f"Show {product} with relaxed shorts proportion; make the drawstring waist, sweat texture, side pocket, and dachshund embroidery easy to read."
        if "pinstripe" in blob or "pleat" in blob:
            return f"Show {product} with visible front pleats, woven pinstripe texture, back-pocket structure, and curved wide-leg volume in a clean fashion composition."
        if category == "cap":
            return f"Show the cap profile through crown, brim, mesh/back structure, and adjustable closure; keep {primary} visible without clutter."
        if category == "hoodie":
            return f"Show the hoodie volume, sleeve shape, hood/zip structure, and {primary.lower()} through a clean layered fashion pose."
        return f"Show the fit and silhouette of {product} through {primary} and {secondary.lower()}, using product-specific callouts only where helpful."
    if intent == "model_flatlay":
        return f"Build the composition around {primary} and {secondary.lower()}, connecting styling presence with clear product shape and construction cues for {product_type}."
    if intent == "detail":
        return f"Use premium close-up framing for {primary}; keep texture, stitching, trims, hardware, print, and construction faithful to the supplied references."
    if intent == "lifestyle":
        return f"Place {product} in a clean lifestyle scene derived from {primary}, keeping the product dominant and the A+ composition commercially readable."
    return ""


def generated_visual_direction(
    raw_value: str,
    section: dict[str, object],
    global_context: str,
    visible_language: str = "English",
    no_logo: bool = False,
) -> str:
    cleaned = sanitize_prompt_context(raw_value)
    cleaned = re.sub(r"^[\s\-—–+,.，。:：()（）]+$", "", cleaned).strip()
    index = int(section.get("index", 0))
    intent = section_intent(section, index)
    category = product_category_key(global_context)
    product = product_phrase(global_context)
    features = feature_phrase(global_context, product)
    layout_task = template_layout_task(section, index, visible_language, no_logo)
    pose_note = ""
    if "section 1 unique pose direction" in cleaned.lower():
        pose_match = re.search(
            r"Section 1 unique pose direction for this batch:\s*(.+?)(?:\.\s*Use this|\n|$)",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )
        pose = pose_match.group(1).strip() if pose_match else ""
        pose_note = f" Use this specific editorial pose: {pose}." if pose else " Keep the assigned editorial pose direction from this prompt."

    specific_visual = product_specific_visual_direction(intent, category, global_context, visible_language)
    if specific_visual:
        return merge_layout_and_visual(layout_task, f"{specific_visual}{pose_note}".strip())

    if visible_language == "German":
        if intent == "replacement_background":
            return merge_layout_and_visual(
                layout_task,
                "Erzeuge einen textfreien, stilistisch passenden Hintergrund fuer spaetere Influencer-Ersetzung; keine Personen, keine Social-UI und keine Farbblock-Platzhalter, sofern nicht ausdruecklich verlangt.",
            )
        if intent == "hero":
            logo_phrase = "brandfreier Komposition ohne LOGO-Bereich" if no_logo else "sauberer LOGO-Zone"
            return merge_layout_and_visual(
                layout_task,
                f"Gestalte ein Premium-Brand-Banner fuer {product} mit klarer Produktpraesenz, {logo_phrase}, editorialer Model-Energie und Amazon A+ Lesbarkeit.{pose_note}",
            )
        if intent == "fit":
            return merge_layout_and_visual(
                layout_task,
                f"Zeige Passform, Proportion und Tragegefuehl von {product} klar am Model; nutze ruhige Callouts fuer die wichtigsten Fit- oder Komfortdetails: {features}.",
            )
        if intent == "model_flatlay":
            return merge_layout_and_visual(
                layout_task,
                f"Kombiniere Model-Styling mit Front-/Rueckseiten- oder Flat-Lay-Produktklarheit, damit Form, Proportion und Konstruktion von {product} sofort verstaendlich sind.",
            )
        if intent == "detail":
            return merge_layout_and_visual(
                layout_task,
                f"Nutze klare Makro- und Detailausschnitte, um Material, Naehte, Finish, Grafik oder Konstruktion von {product} hochwertig und produkttreu zu zeigen.",
            )
        if intent == "lifestyle":
            return merge_layout_and_visual(
                layout_task,
                f"Inszeniere {product} in einer kaufnahen Lifestyle- oder Geschenk-Szene mit ruhiger A+ Ordnung und produktabgeleiteter Farbwelt.",
            )
        return merge_layout_and_visual(
            layout_task,
            f"Erzeuge ein klares Amazon A+ Modul fuer {product} mit einem konkreten, produktbezogenen Verkaufsargument.",
        )

    if intent == "replacement_background":
        return merge_layout_and_visual(
            layout_task,
            "Create a style-matched, text-free background image for later influencer content replacement; no people, no social UI, no color-block placeholders unless explicitly requested.",
        )
    if intent == "hero":
        logo_phrase = "a brand-free composition with no LOGO area" if no_logo else "a clean LOGO area"
        return merge_layout_and_visual(
            layout_task,
            f"Create a premium brand hero banner for {product} with strong product presence, {logo_phrase}, editorial model energy, and clear Amazon A+ readability.{pose_note}",
        )
    if intent == "fit":
        if category == "cap":
            return merge_layout_and_visual(
                layout_task,
                f"Show the adjustable fit and wearing comfort of {product}, keeping the brim, crown, mesh/back structure, and closure readable with restrained callouts.",
            )
        if category in {"pants", "denim"}:
            return merge_layout_and_visual(
                layout_task,
                f"Show the leg shape, rise, waistband, and movement of {product} on body, with clean callouts for fit and construction details: {features}.",
            )
        if category == "hoodie":
            return merge_layout_and_visual(
                layout_task,
                f"Show the relaxed hoodie proportion, sleeve volume, hood/zip shape, and layering comfort of {product} in a clean commercial model composition.",
            )
        return merge_layout_and_visual(
            layout_task,
            f"Show the fit, silhouette, drape, and wearing comfort of {product} clearly, using restrained product callouts tied to: {features}.",
        )
    if intent == "model_flatlay":
        return merge_layout_and_visual(
            layout_task,
            f"Combine on-body styling with front/back or flat-lay product clarity so shoppers can understand the shape, proportion, and construction of {product}.",
        )
    if intent == "detail":
        return merge_layout_and_visual(
            layout_task,
            f"Use close-up macro framing to emphasize the most relevant product details of {product}: {features}. Keep texture, stitching, trims, print, and construction accurate.",
        )
    if intent == "lifestyle":
        return merge_layout_and_visual(
            layout_task,
            f"Place {product} in a clean lifestyle or gifting-oriented A+ scene that still keeps the product dominant, commercial, and easy to understand.",
        )
    return merge_layout_and_visual(
        layout_task,
        f"Create a clean product-focused Amazon A+ module for {product} with one clear product-specific selling point.",
    )


def image_prompt_visual_direction(
    value: str,
    section: dict[str, object],
    global_context: str = "",
    visible_language: str = "English",
    no_logo: bool = False,
) -> str:
    if global_context:
        return generated_visual_direction(value, section, global_context, visible_language, no_logo)
    cleaned = sanitize_prompt_context(value)
    cleaned = re.sub(r"^[\s\-—–+,.，。:：()（）]+$", "", cleaned).strip()
    return cleaned or "Create a clean product-focused Amazon A+ module with one clear selling point."


def slugify(index: int, title: str) -> str:
    title = clean_section_title(title, index)
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-")
    cleaned = cleaned[:42].strip("-") or "creative-module"
    return f"section-{index:02d}-{cleaned}"


def section_uses_model(section: dict[str, object]) -> bool:
    text = f"{section.get('title', '')}\n{section.get('block', '')}".lower()
    if any(
        term in text
        for term in (
            "no model",
            "no people",
            "no person",
            "do not generate influencer",
            "product close-ups only",
            "macro detail",
            "placeholder",
            "color blocks",
            "占位符",
            "色块",
            "不需要生成网红图",
            "不要出现人物",
            "不要人物",
            "不出现人物",
            "无人物",
            "不要出现模特",
            "不要模特",
        )
    ):
        return False
    return any(
        word in text
        for word in (
            "model",
            "person",
            "people",
            "on-body",
            "wearing",
            "模特",
            "人物",
            "人模",
            "上身",
            "穿着",
            "穿搭",
        )
    )


def section_requests_no_visible_copy(section: dict[str, object]) -> bool:
    text = f"{section.get('title', '')}\n{section.get('block', '')}".lower()
    return any(
        term in text
        for term in (
            "不需要任何文案",
            "不需要文案",
            "无需文案",
            "no visible copy",
            "no copy",
            "text-free",
            "background only",
            "用于后续替换为网红图",
            "后续替换为网红图",
        )
    )


NO_REFERENCE_TERMS = (
    "不要上传参考图",
    "不上传参考图",
    "无需参考图",
    "不要发送参考图",
    "不发送参考图",
    "不要传参考图",
    "不传参考图",
    "no reference images",
    "without reference images",
    "do not upload reference images",
    "do not send reference images",
    "no image references",
)


def section_requests_no_references(section: dict[str, object]) -> bool:
    text = f"{section.get('title', '')}\n{section.get('block', '')}".lower()
    return any(term.lower() in text for term in NO_REFERENCE_TERMS)


def extract_product_summary(global_context: str) -> str:
    lines: list[str] = []
    capture = False
    capture_attributes = False
    allowed_prefixes = (
        "brand",
        "marke",
        "marketplace",
        "product_type",
        "product type",
        "produkttyp",
        "target_customer",
        "target customer",
        "zielgruppe",
        "fabric",
        "material",
        "fit",
        "passform",
        "color",
        "farbe",
        "color_options",
        "neckline",
        "ausschnitt",
        "sleeve",
        "ärmel",
        "length",
        "länge",
        "season",
        "saison",
        "feature",
        "size_range",
        "größenbereich",
        "must_include",
        "product accuracy notes",
        "key features",
    )
    for line in global_context.splitlines():
        stripped = line.strip()
        lower = stripped.lower()
        if lower.startswith("## product truth") or lower.startswith("## product accuracy notes"):
            capture = True
            capture_attributes = False
            continue
        if lower.startswith("## product attributes from excel"):
            capture = True
            capture_attributes = True
            continue
        if capture and stripped.startswith("## "):
            break
        if not capture or not stripped:
            continue
        if capture_attributes:
            match = re.match(r"^\s*-\s*([^:：]+)\s*[:：]\s*(.+?)\s*$", stripped)
            if not match:
                continue
            key = match.group(1).strip()
            value = match.group(2).strip()
            if key.casefold() == "field" or value.casefold() == "value":
                continue
            normalized_key = key.casefold()
            if not normalized_key.startswith(allowed_prefixes):
                continue
            lines.append(f"- {key}: {value}")
        else:
            if stripped.startswith("-"):
                lines.append(stripped)
    if lines:
        return "\n".join(lines[:28])
    return "- Product details: Use the supplied product attributes and attached product references only."


def product_fact(global_context: str, label: str) -> str:
    def norm_key(value: str) -> str:
        return re.sub(r"[^0-9a-zA-Z\u4e00-\u9fffäöüÄÖÜß]+", "", value).casefold()

    aliases = {
        "Product type": ("Product type", "product_type", "Produkttyp", "品类", "产品类型"),
        "Color": ("Color", "color", "color_options", "Farbe", "颜色"),
        "Fabric": ("Fabric", "fabric", "Material", "材质", "面料"),
        "Fit": ("Fit", "fit", "Passform", "版型", "廓形"),
        "target_customer": ("target_customer", "Target customer", "Zielgruppe", "目标客群", "人群"),
        "Target customer": ("target_customer", "Target customer", "Zielgruppe", "目标客群", "人群"),
        "brand": ("brand", "Brand", "Marke", "品牌"),
        "Brand": ("brand", "Brand", "Marke", "品牌"),
        "Product accuracy notes": ("Product accuracy notes", "must_include", "Must include", "产品准确性", "产品细节"),
        "Key features": ("Key features", "key_features", "feature_1", "Feature_1", "Selling point", "卖点"),
    }
    alias_values = aliases.get(label)
    if alias_values is None:
        normalized_label = norm_key(label)
        alias_values = next((values for key, values in aliases.items() if norm_key(key) == normalized_label), (label,))
    wanted = {norm_key(item) for item in alias_values}
    for line in global_context.splitlines():
        match = re.match(r"^\s*-\s*([^:：]+)\s*[:：]\s*(.+?)\s*$", line)
        if not match:
            continue
        key, value = match.group(1).strip(), match.group(2).strip()
        if norm_key(key) in wanted:
            return value
    return ""


def extract_manual_visual_baseline(brief_text: str, *, required: bool = True) -> dict[str, str]:
    """Read the five-line baseline written after human image inspection."""
    heading = VISUAL_BASELINE_HEADING_RE.search(brief_text)
    if not heading:
        if required:
            raise SystemExit(
                "Creative brief is missing '## Suggested Visual Baseline'. "
                "Inspect this SKU's model and product images manually before building prompts."
            )
        return {}
    next_heading = NEXT_LEVEL_TWO_HEADING_RE.search(brief_text, heading.end())
    block = brief_text[heading.end() : next_heading.start() if next_heading else len(brief_text)].strip()
    parsed: dict[str, str] = {}
    for raw_line in block.splitlines():
        line = raw_line.strip().lstrip("-*• ").strip()
        match = re.match(r"^([^:：]+)\s*[:：]\s*(.+?)\s*$", line)
        if not match:
            continue
        label = match.group(1).strip()
        value = sanitize_prompt_context(match.group(2).strip())
        canonical = next((field for field in VISUAL_BASELINE_FIELDS if field.casefold() == label.casefold()), None)
        if canonical and value:
            parsed[canonical] = value
    missing = [field for field in VISUAL_BASELINE_FIELDS if not parsed.get(field)]
    if missing:
        if required:
            raise SystemExit(
                "Suggested Visual Baseline is incomplete. Missing: " + ", ".join(missing)
            )
        return {}
    if parsed["Style balance"] != FIXED_STYLE_BALANCE:
        raise SystemExit(
            "Suggested Visual Baseline must keep Style balance exactly as: " + FIXED_STYLE_BALANCE
        )
    return parsed


def visual_baseline_text(baseline: dict[str, str]) -> str:
    return "\n".join(f"{field}: {baseline[field]}" for field in VISUAL_BASELINE_FIELDS)


def normalized_dynamic_visual_baseline(baseline: dict[str, str]) -> str:
    dynamic = " ".join(baseline[field] for field in VISUAL_BASELINE_FIELDS if field != "Style balance")
    return re.sub(r"[^0-9a-zäöüß]+", " ", dynamic.casefold()).strip()


def ensure_manual_visual_baseline_is_unique(product_dir: Path, baseline: dict[str, str]) -> None:
    """Reject copied baselines while ignoring the intentionally fixed Style balance line."""
    current = normalized_dynamic_visual_baseline(baseline)
    if not current:
        raise SystemExit("Suggested Visual Baseline has no product-specific visual content.")
    for sibling in sorted(product_dir.parent.iterdir(), key=lambda item: item.name.casefold()):
        if not sibling.is_dir() or sibling == product_dir or sibling.name.startswith("_"):
            continue
        other_brief = sibling / "_aplus_creative_work" / "aplus_creative_brief.md"
        if not other_brief.exists():
            continue
        other = extract_manual_visual_baseline(read_text(other_brief), required=False)
        if not other:
            continue
        similarity = SequenceMatcher(
            None,
            current,
            normalized_dynamic_visual_baseline(other),
        ).ratio()
        if similarity >= 0.90:
            raise SystemExit(
                f"Suggested Visual Baseline is {similarity:.0%} similar to SKU '{sibling.name}'. "
                "Re-inspect this SKU's model and product images and rewrite the four dynamic lines manually."
            )


def localized_product_summary(global_context: str, visible_language: str) -> str:
    summary = extract_product_summary(global_context)
    if visible_language != "German":
        return summary
    replacements = {
        "Product type": "Produkttyp",
        "Color": "Farbe",
        "Fabric": "Material",
        "Fit": "Passform",
        "target_customer": "Zielgruppe",
        "neckline": "Ausschnitt/Kapuze",
        "sleeve": "Ärmel",
        "length": "Länge",
        "season": "Saison",
        "feature_": "Feature_",
        "size_range": "Größenbereich",
        "marketplace": "Marketplace",
        "brand": "Marke",
    }
    for source, target in replacements.items():
        summary = re.sub(rf"(?im)^(\s*-\s*){re.escape(source)}(\d*)\s*:", rf"\1{target}\2:", summary)
    return summary


def clean_headline(value: str) -> str:
    value = sanitize_prompt_context(value)
    value = re.sub(r"^(?:headline|title)\s*[:：]\s*", "", value, flags=re.IGNORECASE).strip()
    value = re.sub(r"\s+", " ", value).strip(" -/：:")
    return value


def clean_copy(value: str) -> str:
    value = sanitize_prompt_context(value)
    lowered = value.lower()
    if "small callout" in lowered and not any(marker in lowered for marker in ("description:", "copy:", "subheading:")):
        return ""
    value = re.sub(r"^(?:copy|subheading|body)\s*[:：]\s*", "", value, flags=re.IGNORECASE).strip()
    value = re.sub(r"^headline\s*[:：].*?(?:description|copy|subheading)\s*[:：]\s*", "", value, flags=re.IGNORECASE).strip()
    value = re.sub(r"\s+", " ", value).strip(" -/：:")
    return value


def copy_looks_like_module_instruction(value: str) -> bool:
    lowered = sanitize_prompt_context(value).lower()
    if not lowered:
        return False
    module_instruction_phrases = (
        "product views",
        "front and back views",
        "front, side, and back views",
        "on-body and product views",
        "clear product views",
        "views show",
        "views clarify",
        "views make",
        "shown with",
        "captured through",
        "true front-and-back product clarity",
        "module",
        "layout",
        "reference",
        "in context",
        "close-ups show",
        "close details show",
        "close-up details make",
        "ansichten zeigen",
        "produktansichten",
        "nachvollziehbar",
        "klar verständlich",
        "close-ups zeigen",
    )
    return any(phrase in lowered for phrase in module_instruction_phrases)


def product_context_blob(global_context: str) -> str:
    return re.sub(r"\s+", " ", global_context).strip()


def product_feature_list(global_context: str) -> list[str]:
    features = re.findall(
        r"(?im)^\s*-\s*(?:Feature|feature[_\s-]?\d*|Key features?|Selling point|must_include|Product-specific details)\s*:\s*(.+?)\s*$",
        global_context,
    )
    if not features:
        features = re.findall(
            r"(?im)^\s*(?:feature[_\s-]?\d*|key features?|selling point|must_include|product-specific details)\s*[:：]\s*(.+?)\s*$",
            global_context,
        )
    return [sanitize_prompt_context(item) for item in features if sanitize_prompt_context(item)]


def product_category_key(global_context: str) -> str:
    product_type = product_fact(global_context, "Product type").lower()
    blob = product_context_blob(global_context).lower()

    def has_any(text: str, terms: tuple[str, ...]) -> bool:
        return any(re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text) for term in terms)

    def classify(text: str) -> str | None:
        if has_any(text, ("baseball caps", "baseball cap", "trucker hat", "snapback", "cap", "hat", "mütze", "kappe")):
            return "cap"
        if has_any(text, ("jeans", "denim")):
            return "denim"
        if has_any(text, ("pants", "trousers", "sweatpants", "cargo", "shorts", "hose")):
            return "pants"
        if has_any(text, ("hoodie", "sweatshirt", "fleece", "kapuze")):
            return "hoodie"
        if has_any(text, ("t-shirt", "tee", "shirt")):
            return "tee"
        if has_any(text, ("jacket", "coat", "jacke")):
            return "jacket"
        if has_any(text, ("skirt", "dress", "rock", "kleid")):
            return "dress"
        return None

    typed_category = classify(product_type)
    if typed_category:
        return typed_category
    category = classify(blob)
    if category == "cap":
        return "cap"
    if category == "denim":
        return "denim"
    if category == "pants":
        return "pants"
    if category == "hoodie":
        return "hoodie"
    if category == "tee":
        return "tee"
    if category == "jacket":
        return "jacket"
    if category == "dress":
        return "dress"
    return "apparel"


def product_signal_blob(global_context: str) -> str:
    facts = [
        product_fact(global_context, "Product type"),
        product_fact(global_context, "Color"),
        product_fact(global_context, "Fit"),
        product_fact(global_context, "Fabric"),
        product_fact(global_context, "target_customer"),
        product_fact(global_context, "Product accuracy notes"),
        " ".join(product_feature_list(global_context)),
    ]
    return " ".join(part for part in facts if part).lower()


def short_headline(value: str, fallback: str = "PRODUCT DETAIL") -> str:
    cleaned = sanitize_prompt_context(value)
    cleaned = re.sub(r"[^\w&+\-/ ]+", " ", cleaned, flags=re.UNICODE)
    cleaned = cleaned.replace("_", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -/")
    if not cleaned:
        return fallback
    words = cleaned.upper().split()
    return " ".join(words[:5]) or fallback


def feature_candidates(global_context: str) -> list[str]:
    features = product_feature_list(global_context)
    notes = product_fact(global_context, "Product accuracy notes")
    if notes:
        features.extend(re.split(r"[;,/]| and ", notes))
    result: list[str] = []
    seen: set[str] = set()
    for item in features:
        cleaned = sanitize_prompt_context(item)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" -.;,")
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        result.append(cleaned)
    return result


def select_feature(global_context: str, keywords: tuple[str, ...], fallback_index: int = 0) -> str:
    candidates = feature_candidates(global_context)
    for item in candidates:
        lowered = item.lower()
        if any(keyword in lowered for keyword in keywords):
            return item
    if candidates:
        return candidates[min(fallback_index, len(candidates) - 1)]
    return product_phrase(global_context)


def compact_attr(value: str, fallback: str = "") -> str:
    cleaned = sanitize_prompt_context(value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -.;,")
    return cleaned or fallback


def product_noun(product_type: str) -> str:
    lowered = product_type.lower()
    if "cardigan" in lowered:
        return "cardigan"
    if "hoodie" in lowered or "sweatshirt" in lowered:
        return "hoodie"
    if "short" in lowered:
        return "shorts"
    if any(word in lowered for word in ("pants", "trousers", "sweatpants")):
        return "pants"
    if "cap" in lowered or "hat" in lowered:
        return "cap"
    if "tee" in lowered or "shirt" in lowered:
        return "tee"
    return product_type.lower() or "piece"


def feature_by_priority(global_context: str, keywords: tuple[str, ...], fallback_index: int = 0) -> str:
    candidates = feature_candidates(global_context)
    matches = [
        compact_attr(item)
        for item in candidates
        if any(keyword in item.lower() for keyword in keywords) and compact_attr(item)
    ]
    if matches:
        return matches[fallback_index % len(matches)]
    if candidates:
        return compact_attr(candidates[fallback_index % len(candidates)])
    return compact_attr(product_phrase(global_context))


def distinct_feature_by_priority(
    global_context: str,
    keywords: tuple[str, ...],
    avoid: str,
    fallback_index: int = 0,
) -> str:
    avoid_key = duplicate_key(avoid)
    candidates = feature_candidates(global_context)
    ordered: list[str] = []
    for item in candidates:
        lowered = item.lower()
        if any(keyword in lowered for keyword in keywords):
            ordered.append(item)
    ordered.extend(candidates)
    for item in ordered:
        cleaned = compact_attr(item)
        if cleaned and duplicate_key(cleaned) != avoid_key:
            return cleaned
    return ""


def section_benefit_phrase(intent: str, category: str, visible_language: str) -> str:
    if visible_language == "German":
        if intent == "fit":
            return {
                "cap": "bequemen Sitz fuer Alltag und Styling",
                "pants": "sichtbare Bewegung und klare Proportion",
                "denim": "entspannte Bewegung mit strukturierter Form",
                "hoodie": "einfaches Layering mit laessiger Weite",
            }.get(category, "kaufnahe Passform und alltagstaugliches Styling")
        if intent == "model_flatlay":
            return "Styling-Kontext mit klarer Produktform"
        if intent == "detail":
            return "mehr Textur, Finish und Produktwert aus der Naehe"
        return "einen klaren alltagsnahen Styling-Moment"
    if intent == "fit":
        return {
            "cap": "an easy adjustable fit from commute to weekend",
            "pants": "comfortable movement with a clear streetwear shape",
            "denim": "room to move with a lived-in denim profile",
            "hoodie": "easy layering without losing shape",
        }.get(category, "wearable proportion and everyday comfort")
    if intent == "model_flatlay":
        return "styling context with clear product proof"
    if intent == "detail":
        return "texture, finish, and product value up close"
    return "an everyday styling reason that still feels product-first"


def dynamic_product_section_text(
    index: int,
    intent: str,
    category: str,
    global_context: str,
    visible_language: str,
    variant: int = 0,
) -> tuple[str, str] | None:
    if intent not in {"fit", "model_flatlay", "detail", "lifestyle"} or index == 1:
        return None
    if intent == "replacement_background":
        if visible_language == "German":
            return "TEXTFREIER HINTERGRUND", "Keine sichtbare Copy; eine ruhige, stilistisch passende Flaeche fuer spaetere Content-Ersetzung."
        return "TEXT-FREE BACKGROUND", "No visible copy; create a clean styled background for later content replacement."

    product_type = compact_attr(product_fact(global_context, "Product type"), "apparel")
    noun = product_noun(product_type)
    fit = compact_attr(product_fact(global_context, "Fit"))
    fabric = compact_attr(product_fact(global_context, "Fabric"))
    color = compact_attr(product_fact(global_context, "Color"))
    features = feature_candidates(global_context)
    fallback_feature = features[variant % len(features)] if features else product_type

    if intent == "fit":
        primary = fit or feature_by_priority(global_context, ("fit", "silhouette", "shape", "waist", "leg", "sleeve", "adjustable", "closure"), variant) or fallback_feature
        secondary = distinct_feature_by_priority(global_context, ("hood", "zip", "mesh", "pleat", "wide", "pocket", "rib", "drop", "brim", "snapback"), primary, variant + 1) or fabric or fallback_feature
        if visible_language == "German":
            headline = short_headline(f"{primary} {noun}", "PASSFORM MIT CHARAKTER")
            copy = f"{primary}, {secondary.lower()} und {fabric.lower() if fabric else 'tragbare Struktur'} geben dem {noun} {section_benefit_phrase(intent, category, visible_language)}."
            return headline, copy
        headline = short_headline(f"{primary} {noun}", "FIT WITH CHARACTER")
        copy = f"{primary}, {secondary.lower()}, and {fabric.lower() if fabric else 'wearable structure'} give the {noun} {section_benefit_phrase(intent, category, visible_language)}."
        return headline, copy

    if intent == "model_flatlay":
        primary = feature_by_priority(global_context, ("graphic", "print", "embroidery", "logo", "pattern", "patch", "zip", "closure", "pocket", "mesh", "pleat"), variant) or fallback_feature
        secondary = distinct_feature_by_priority(global_context, ("fit", "shape", "waist", "leg", "hood", "sleeve", "cuff", "fabric", "knit", "cotton"), primary, variant + 1) or fit or fabric or product_type
        if visible_language == "German":
            headline = short_headline(primary, "FORM UND DETAIL")
            copy = f"{primary} und {secondary.lower()} verbinden {section_benefit_phrase(intent, category, visible_language)} fuer den {noun}."
            return headline, copy
        headline = short_headline(primary, "SHAPE AND DETAIL")
        copy = f"{primary} and {secondary.lower()} give the {noun} {section_benefit_phrase(intent, category, visible_language)}."
        return headline, copy

    if intent == "detail":
        primary = feature_by_priority(global_context, ("fabric", "knit", "cotton", "fleece", "mesh", "embroidery", "graphic", "print", "stitch", "zip", "pocket", "cuff", "hem", "brim", "snapback"), variant) or fallback_feature
        secondary = distinct_feature_by_priority(global_context, ("construction", "closure", "rib", "waist", "drawstring", "pleat", "patch", "texture", "finish"), primary, variant + 1) or fabric or color or product_type
        if visible_language == "German":
            headline = short_headline(primary, "DETAILS MIT CHARAKTER")
            copy = f"{primary}, {secondary.lower()} und sauberes Finish geben dem {noun} {section_benefit_phrase(intent, category, visible_language)}."
            return headline, copy
        headline = short_headline(primary, "DETAILS WITH CHARACTER")
        copy = f"{primary}, {secondary.lower()}, and clean finishing give the {noun} {section_benefit_phrase(intent, category, visible_language)}."
        return headline, copy

    primary = feature_by_priority(global_context, ("graphic", "fit", "fabric", "adjustable", "pocket", "embroidery", "rhinestone", "mesh", "zip"), variant) or fallback_feature
    if visible_language == "German":
        headline = short_headline(f"{noun} everyday style", "STYLE FUER VIELE MOMENTE")
        return headline, f"{primary} hilft dem {noun}, in alltagsnahen Looks klar, tragbar und produktorientiert zu wirken."
    headline = short_headline(f"{noun} everyday style", "STYLE FOR EVERYDAY")
    return headline, f"{primary} helps the {noun} fit naturally into casual outfits while keeping the product story clear."


def product_specific_section_text(
    index: int,
    intent: str,
    category: str,
    global_context: str,
    visible_language: str,
) -> tuple[str, str] | None:
    if intent not in {"fit", "model_flatlay", "detail", "lifestyle"} or index == 1:
        return None

    dynamic = dynamic_product_section_text(index, intent, category, global_context, visible_language)
    if dynamic:
        return dynamic

    product_type = product_fact(global_context, "Product type") or "apparel"
    fit = product_fact(global_context, "Fit")
    fabric = product_fact(global_context, "Fabric")
    blob = product_signal_blob(global_context)

    if visible_language == "German":
        if intent == "fit":
            if category == "hoodie" or "hoodie" in blob or "kapuze" in blob:
                if "cropped" in blob or "verkürzt" in blob or "ultra-cropped" in blob:
                    return "CROPPED HOODIE-PASSFORM", "Der verkürzte Schnitt, die lockere Weite und die Kapuze geben dem Hoodie eine moderne Layering-Silhouette."
                return "LOCKERE HOODIE-PASSFORM", "Kapuze, weiche Weite und bequeme Proportionen machen den Hoodie leicht kombinierbar."
            if "rhinestone" in blob or "strass" in blob:
                return "WEITES BEIN MIT GLANZ", "Rhinestone-Details, elastischer Bund und verstellbarer Saum geben der Hose Bewegung und Statement."
            if "dachshund" in blob:
                return "LOCKERE SHORTS MIT CHARME", "Dachshund-Stickerei, elastischer Bund und weicher Sweatstoff bringen Komfort mit spielerischem Detail."
            if "pinstripe" in blob or "pleat" in blob:
                return "PLISSIERTE PINSTRIPE-FORM", "Frontfalten, weiter Beinverlauf und strukturierter Webstoff geben der Silhouette klare Streetwear-Praesenz."
        if intent == "model_flatlay":
            if category == "hoodie" or "hoodie" in blob or "kapuze" in blob:
                if "reißverschluss" in blob or "reissverschluss" in blob or "zip" in blob:
                    return "REISSVERSCHLUSS UND LINIENAKZENT", "Zip-Front, Cropped-Form und rote Linienakzente geben dem Hoodie eine sportlich-moderne Aussage."
                return "HOODIE-FORM MIT STYLING", "Kapuze, lockere Proportion und weiches Material tragen den Look vom Styling bis zum Detail."
            if "rhinestone" in blob or "cargo" in blob:
                return "CARGO-DETAILS MIT ENERGIE", "Rhinestones, weites Bein und verstellbarer Saum machen den Look markant und beweglich."
            if "dachshund" in blob:
                return "STICKEREI TRIFFT EASY FIT", "Die Dachshund-Grafik und der lockere Bund geben dem Sweat-Short eine leichte Alltagsnote."
            if "pinstripe" in blob or "pleat" in blob:
                return "PINSTRIPE MIT STRUKTUR", "Falten, Taschen und weite Proportion verbinden Tailoring-Anmutung mit laessigem Volumen."
        if intent == "detail":
            if category == "hoodie" or "hoodie" in blob or "kapuze" in blob:
                if "rote linien" in blob or "linienakzent" in blob:
                    return "ZIP, RIPP UND ROTE LINIEN", "Reißverschluss, Bündchen und kontrastierende Linienakzente machen die Details klar sichtbar."
                return "MATERIAL UND HOODIE-FINISH", "Stoffgriff, Kapuze, Nähte und Bündchen geben dem Hoodie mehr Tiefe aus der Nähe."
            if "rhinestone" in blob or "cargo" in blob:
                return "RHINESTONES, CARGO, SAUM", "Glanzdetails, Taschen und verstellbarer Beinabschluss schaerfen den Utility-Look."
            if "dachshund" in blob:
                return "STICKEREI UND SWEAT-FINISH", "Dachshund-Motiv, Kordelzug und weicher Stoff setzen freundliche Detailakzente."
            if "pinstripe" in blob or "pleat" in blob:
                return "FALTEN, TASCHEN, PINSTRIPES", "Gewebte Streifen, Frontfalten und Taschenfinish geben der Hose Struktur aus der Naehe."
        primary = select_feature(global_context, ("graphic", "print", "embroidery", "rhinestone", "pocket", "zip", "mesh", "fabric", "cotton"), 0)
        headline = short_headline(primary, "PRODUKTDETAIL MIT CHARAKTER")
        return headline, f"{product_type} verbindet {primary.lower()} mit klarer Passform und alltagstauglichem Styling."

    if intent == "fit":
        if category == "hoodie" or "hoodie" in blob or "cardigan" in blob:
            if "cropped" in blob:
                return "CROPPED HOODIE PROPORTION", "A shortened cut, loose volume, and hooded shape give the layer a sharp modern streetwear profile."
            if "cardigan" in blob or "zip" in blob:
                return "ZIP LAYER, EASY VOLUME", "A hooded zip front, loose fit, and warm knit texture make the cardigan easy to layer with shape."
            accent = select_feature(global_context, ("fleece", "zip", "hood", "graphic", "star", "embroidery"), 0)
            return "RELAXED LAYERING VOLUME", f"{fit or 'Relaxed proportions'} and {accent.lower()} make the hoodie easy to layer without losing shape."
        if "rhinestone" in blob or "cargo" in blob or "adjustable leg hem" in blob:
            return "DANCE-READY WIDE LEG", "Rhinestone cargo details, an elastic waist, and adjustable hems keep the pants flexible with a sharper streetwear finish."
        if "dachshund" in blob:
            return "BAGGY SHORTS, EASY WAIST", "Soft sweat fabric, a drawstring waist, and relaxed length make the shorts comfortable with playful graphic character."
        if "pinstripe" in blob or "pleat" in blob or "balloon" in blob:
            return "PLEATED PINSTRIPE VOLUME", "Front pleats, structured woven stripes, and a curved wide leg give the pants clean movement and tailored volume."
        if category == "cap":
            return "ADJUSTABLE SNAPBACK COMFORT", "Mesh structure, a curved brim, and a snapback closure keep the cap breathable and easy to wear."
        primary = select_feature(global_context, ("fit", "waist", "leg", "hem", "drape", "silhouette", "stretch", "adjustable"), 0)
        return short_headline(f"{primary} fit"), f"{product_type} balances {primary.lower()} with {fabric.lower() if fabric else 'wearable texture'} for everyday movement."

    if intent == "model_flatlay":
        if category == "hoodie" or "hoodie" in blob or "cardigan" in blob:
            if "cardigan" in blob or "zip" in blob:
                return "ZIP HOOD, KNIT SHAPE", "The zip-front hood, relaxed cardigan body, and soft knit texture bring easy structure to layered outfits."
            if "cropped" in blob:
                return "CROPPED HOODIE ATTITUDE", "The ultra-cropped shape and contrast line accents give the hoodie a sporty, modern styling edge."
            return "HOODIE SHAPE, EASY STYLE", "Hood structure, relaxed volume, and soft fabric make the layer feel casual but considered."
        if "rhinestone" in blob or "cargo" in blob:
            return "RHINESTONE CARGO ENERGY", "Wide-leg volume, cargo utility, and sparkling accents bring dance-floor attitude to everyday styling."
        if "dachshund" in blob:
            return "DACHSHUND GRAPHIC SHORTS", "The embroidered dachshund, relaxed sweat shape, and easy waistband add personality to casual warm-weather looks."
        if "pinstripe" in blob or "pleat" in blob or "balloon" in blob:
            return "PINSTRIPE SHAPE, FRONT TO BACK", "Pleated volume, back pockets, and woven stripes keep the wide-leg silhouette sharp from every angle."
        primary = select_feature(global_context, ("graphic", "embroidery", "print", "wash", "pocket", "closure", "mesh", "patch"), 0)
        secondary = select_feature(global_context, ("fit", "shape", "waist", "leg", "fabric", "cotton", "denim"), 1)
        return short_headline(primary), f"{primary} and {secondary.lower()} give {product_type.lower()} a clearer styling reason and product personality."

    if intent == "detail":
        if category == "hoodie" or "hoodie" in blob or "cardigan" in blob:
            if "cardigan" in blob or "knit" in blob or "wool" in blob:
                return "KNIT, ZIP, AND HOOD", "Soft knit texture, zip construction, and hood details add warmth and structure up close."
            if "cropped" in blob or "line" in blob:
                return "ZIP, RIB, LINE DETAIL", "The zip front, ribbed cuffs, and contrast line accents sharpen the hoodie in the details."
            return "HOOD, RIB, AND FABRIC", "Hood construction, rib trim, and fabric texture keep the comfort story visible up close."
        if "rhinestone" in blob or "cargo" in blob:
            return "RHINESTONES, CARGO, HEM", "Sparkle accents, utility pockets, and adjustable hems sharpen the pants with practical streetwear detail."
        if "dachshund" in blob:
            return "EMBROIDERY AND DRAWSTRING", "The dachshund embroidery, drawstring waist, and soft sweat texture add friendly detail up close."
        if "pinstripe" in blob or "pleat" in blob or "balloon" in blob:
            return "PLEATS, POCKETS, PINSTRIPES", "Woven stripes, front pleats, back pockets, and a small accent logo build structure in the details."
        primary = select_feature(global_context, ("fabric", "cotton", "fleece", "mesh", "embroidery", "graphic", "print", "stitch", "zip", "pocket", "patch"), 0)
        return short_headline(primary), f"{primary} adds texture, finish, and a concrete reason to notice the {product_type.lower()} up close."

    if intent == "lifestyle":
        primary = select_feature(global_context, ("graphic", "fit", "fabric", "adjustable", "pocket", "embroidery", "rhinestone", "mesh"), 0)
        return short_headline(f"{product_type} everyday style"), f"{primary} helps the {product_type.lower()} move naturally across casual outfits, travel, and weekend styling."

    return None


def generated_section_text(
    index: int,
    global_context: str,
    visible_language: str = "English",
    section: dict[str, object] | None = None,
) -> tuple[str, str]:
    product_type = product_fact(global_context, "Product type") or "apparel"
    color = product_fact(global_context, "Color")
    fit = product_fact(global_context, "Fit")
    features = product_feature_list(global_context)
    first_feature = features[0] if features else product_type
    base_headline, base_copy = SECTION_HEADLINE_THEMES.get(index, ("STREET READY", "Clean product clarity with editorial energy."))
    descriptor = " ".join(part for part in [color, fit, product_type] if part).strip()
    category = product_category_key(global_context)
    intent = section_intent(section or {"index": index}, index)
    feature_text = feature_phrase(global_context, first_feature)
    product_specific = product_specific_section_text(index, intent, category, global_context, visible_language)
    if product_specific:
        return product_specific

    if visible_language == "German":
        if intent == "replacement_background":
            return "TEXTFREIER HINTERGRUND", "Keine sichtbare Copy; eine ruhige, stilistisch passende Flaeche fuer spaetere Content-Ersetzung."
        if intent == "fit" and index != 1:
            if category == "cap":
                return "VERSTELLBARER TRAGEKOMFORT", "Verstellbarer Sitz, klare Form und angenehme Alltagstauglichkeit bleiben im Fokus."
            if category in {"pants", "denim"}:
                return "FORM MIT BEWEGUNG", "Bund, Beinlinie und lockere Proportionen geben dem Look Struktur und Komfort."
            if category == "hoodie":
                return "LOCKERE LAYERING-FORM", "Kapuze, Reissverschluss und entspannte Weite machen das Styling unkompliziert."
            return "PASSFORM MIT PRODUKTCHARAKTER", f"{product_type} zeigt eine klare Silhouette mit kaufnahen Details."
        if intent == "model_flatlay" and index != 1:
            return "FORM UND DETAILS IM BLICK", f"Model-Styling und Produktansichten zeigen {product_type} mit klarer Proportion und Konstruktion."
        if intent == "detail" and index != 1:
            return "DETAILS MIT CHARAKTER", f"Material, Verarbeitung und Finish machen die Produktqualitaet von {product_type} sichtbar."
        if intent == "lifestyle" and index != 1:
            return "STYLE FUER VIELE MOMENTE", f"{product_type} passt in alltagsnahe Looks und bleibt dabei klar produktorientiert."
        german = {
            "cap": {
                1: ("RETRO-TRUCKER-STYLE", "Farbkontrast, Mesh-Struktur und ein laessiger Look fuer jeden Tag."),
                2: ("VERSTELLBARER SITZ", "Gebogener Schirm und Snapback-Verschluss sorgen fuer unkomplizierten Tragekomfort."),
                3: ("MESH-BACK MIT RETRO-PROFIL", "Atmungsaktives Mesh, gebogener Schirm und strukturierte Form bringen Vintage-Attituede in den Alltag."),
                4: ("SIGNATURE-PATCH IM FOKUS", "Logo-Patch, Naehte und Schirmdetails machen den Look klar erkennbar."),
            },
            "denim": {
                1: ("DENIM MIT PRAESENZ", "Waschung, Form und Streetwear-Attituede wirken sauber und selbstbewusst."),
                2: ("LOCKERE SILHOUETTE", "Die Passform bietet Bewegungsfreiheit und bleibt klar in der Form."),
                3: ("WASCHUNG MIT CHARAKTER", "Authentische Denim-Struktur trifft auf eine laessige, alltagstaugliche Beinform."),
                4: ("NAEHTE, TASCHEN, FINISH", "Konstruktion, Waschung und Taschenfinish geben dem Denim mehr Tiefe."),
            },
            "pants": {
                1: ("UTILITY-SILHOUETTE IN BEWEGUNG", "Eine starke Hosenform fuer laessige Streetwear-Looks."),
                2: ("LOCKERER SCHNITT, EINFACHE BEWEGUNG", "Komfort, Struktur und Alltagstauglichkeit bleiben im Gleichgewicht."),
                3: ("LAESSIGE FORM, KLARE FUNKTION", "Taschen, Bund und Beinlinie verbinden Streetwear-Struktur mit bequemem Alltagstragegefuehl."),
                4: ("KONSTRUKTION, DIE ZAEHLT", "Naehte, Taschen, Bund und Stofffinish tragen die Detailstory."),
            },
            "hoodie": {
                1: ("SOFTE STREETWEAR-PRAESENZ", "Relaxte Form und grafische Energie fuer einfaches Layering."),
                2: ("WEITER KOMFORT-FIT", "Die lockere Silhouette bleibt bequem und leicht zu stylen."),
                3: ("GRAFIK MIT STREETWEAR-WIRKUNG", "Markantes Artwork trifft auf eine entspannte Form fuer einen selbstbewussten Alltagslook."),
                4: ("FLEECE, RIPP UND FINISH", "Materialgefuehl, Buendchen und Naehte halten die Komfortstory sichtbar."),
            },
            "tee": {
                1: ("GRAFIK-LOOK FUER JEDEN TAG", "Eine klare Casual-Form mit produktnaher visueller Aussage."),
                2: ("EINFACHER ON-BODY-FIT", "Die Silhouette wirkt bequem, entspannt und leicht kombinierbar."),
                3: ("GRAFIKLOOK MIT LEICHTIGKEIT", "Auffaelliges Artwork und eine entspannte Silhouette bringen Energie in einfache Outfits."),
                4: ("STOFF UND PRINT IM DETAIL", "Materialoberflaeche und Grafikfinish geben dem Look mehr Praezision."),
            },
            "apparel": {
                1: ("PRODUKTLOOK MIT PRAESENZ", "Farbe, Form und Styling wirken klar und kaufnah."),
                2: ("PASSFORM MIT ALLTAGSGEFUEHL", "Die Silhouette bleibt bequem, klar und leicht zu stylen."),
                3: ("FORM, DIE DEN LOOK TRAEGT", "Farbe, Schnitt und Stylingdetails verbinden sich zu einem klaren Alltagsstatement."),
                4: ("DETAILS, DIE DEN LOOK DEFINIEREN", "Textur, Verarbeitung und Finish geben dem Produkt mehr Charakter."),
            },
        }
        return german.get(category, german["apparel"]).get(index, ("PRODUKTDETAILS", "Kurzer, kaufnaher Text passend zum Produkt."))

    if index == 1:
        feature_blob = " ".join(features).lower()
        type_text = product_type.upper()
        if "star" in feature_blob:
            headline = "LEOPARD STAR ENERGY" if "leopard" in feature_blob else "STAR GRAPHIC ENERGY"
        elif any(word in product_type.lower() for word in ("jeans", "pants", "sweatpants")):
            headline = "WIDE-LEG STREET SHAPE" if "wide" in f"{fit} {feature_blob}".lower() else f"{type_text} STREET SHAPE"
        elif "zip" in f"{product_type} {feature_blob}".lower():
            headline = "ZIP LAYER, STREET EDGE"
        elif "hood" in f"{product_type} {feature_blob}".lower():
            headline = "HOODED STREET COMFORT"
        elif any(word in feature_blob for word in ("graphic", "print", "logo")):
            headline = "GRAPHIC STREET IMPACT"
        else:
            headline = f"{type_text} STREET ENERGY"
        return headline, f"{descriptor or product_type} shaped for confident everyday styling."
    if intent == "replacement_background":
        return "TEXT-FREE BACKGROUND", "No visible copy; create a clean styled background for later content replacement."
    if intent == "fit" and index != 1:
        if category == "cap":
            return "ADJUSTABLE EVERYDAY FIT", "A curved brim, structured crown, and easy closure keep the cap comfortable from commute to weekend."
        if category == "denim":
            return "DENIM SHAPE WITH ROOM", "A relaxed rise, easy leg line, and lived-in texture give the denim natural everyday movement."
        if category == "pants":
            return "RELAXED LEG, EASY MOTION", "The waistband, rise, and leg shape balance streetwear volume with comfortable movement."
        if category == "hoodie":
            return "LAYERED COMFORT FIT", "Relaxed volume, hood structure, and easy sleeve shape make the hoodie simple to style."
        if category == "tee":
            return "EASY TEE PROPORTION", "A relaxed body shape and everyday drape keep the graphic look comfortable and wearable."
        return f"{fit.upper() if fit else 'CLEAR EVERYDAY FIT'}", f"{descriptor or product_type} uses its silhouette, fabric, and key details to support natural everyday wear."
    if intent == "model_flatlay" and index != 1:
        if category in {"pants", "denim"}:
            return "SHAPE FROM EVERY ANGLE", "On-body styling and flat-lay views clarify the leg shape, waistband, pockets, and construction."
        if category == "hoodie":
            return "LAYERING SHAPE, PRODUCT CLARITY", "Model styling and flat-lay views connect the hoodie volume, hood/zip structure, and graphic details."
        if category == "cap":
            return "CROWN, BRIM, AND BACK DETAIL", "Worn and flat-lay views connect the cap profile with its closure, embroidery, and color blocking."
        return "STYLE AND STRUCTURE TOGETHER", f"On-body styling and product views clarify how {product_type} looks, fits, and is constructed."
    if intent == "detail" and index != 1:
        if category == "cap":
            return "STITCHING, MESH, AND CLOSURE", "Close details highlight the embroidery, breathable back, curved brim, and adjustable finish."
        if category in {"pants", "denim"}:
            return "WAISTBAND, POCKETS, FINISH", "Construction details bring focus to the fabric, pocket shape, seams, and relaxed fit story."
        if category == "hoodie":
            return "ZIP, RIB, AND FABRIC DETAIL", "Texture, trim, and construction details keep the comfort story visible up close."
        return f"{first_feature.upper()[:28]}", f"Close detail framing turns {feature_text} into a clear product-quality story."
    if intent == "lifestyle" and index != 1:
        return "STYLE THAT MOVES WITH YOU", f"{product_type} fits easily into everyday styling, gifting, travel, and relaxed streetwear moments."
    if index == 2:
        return f"{fit.upper() if fit else base_headline}", f"{descriptor or product_type} uses proportion, fabric, and fit to support comfortable everyday movement."
    if index == 3:
        if category == "cap":
            return "MESH-BACK RETRO PROFILE", "Breathable mesh, a curved brim, and a structured crown bring easy vintage attitude."
        if category == "denim":
            return "WASHED DENIM CHARACTER", "A lived-in wash, relaxed rise, and easy leg shape bring texture to everyday styling."
        if category == "pants":
            return "UTILITY SHAPE, EASY MOTION", "Pockets, rise, and relaxed leg shape balance practical structure with everyday comfort."
        if category == "hoodie":
            return "GRAPHIC ENERGY, EASY FIT", "Statement artwork pairs with a relaxed silhouette for a bold everyday look."
        if category == "tee":
            return "GRAPHIC IMPACT, EASY FIT", "Bold print placement meets a relaxed silhouette built for everyday styling."
        return f"{first_feature.upper()[:28]}", "A clear feature focus gives the product a stronger everyday styling reason."
    if index == 4:
        feature_text = first_feature.lower()
        if any(word in feature_text for word in ("fleece", "cotton", "knit", "fabric", "texture")):
            return "SOFTNESS YOU CAN SEE", "Texture, finish, and comfort come together in a closer product story."
        if any(word in feature_text for word in ("graphic", "print", "logo", "star", "patch")):
            return "DETAIL THAT STANDS OUT", "Statement graphics and clean finishing add character without overcomplicating the look."
        if category == "cap":
            return "CURVED BRIM AND SNAPBACK", "Stitching, mesh, and closure details support an easy everyday fit."
        if category == "denim":
            return "WASH, SEAMS, AND POCKETS", "Denim finish and construction details bring texture, structure, and trust."
        if category == "pants":
            return "WAISTBAND AND POCKET DETAIL", "Functional construction details support the relaxed everyday fit."
        if category == "hoodie":
            return "RIB, FLEECE, AND FINISH", "Texture and trim details keep the comfort story visible."
        if category == "tee":
            return "FABRIC AND PRINT FINISH", "Material surface and graphic finish keep the look crisp up close."
        return f"{first_feature.upper()[:28]}", "Texture, finish, and construction add confidence to the product story."
    if index == 5:
        return "TEXT-FREE BACKGROUND", "No visible copy; create a clean styled background for later content replacement."
    return base_headline, base_copy

def visible_text_instruction(visible_language: str) -> str:
    if visible_language == "German":
        return (
            "Alle sichtbaren Texte müssen auf Deutsch sein. Wenn die Produktattribut-Tabelle deutsche Werte enthält, "
            "übernimm deutsche Begriffe, Schreibweise, Umlaute und Groß-/Kleinschreibung. Kein Englisch als sichtbarer Text, "
            "außer es ist ein Markenname oder ein exakt vorgegebener Produktname."
        )
    return "All visible rendered text must be English only."


def render_callouts_block(callouts: str) -> str:
    """Discard machine-authored callouts; the main agent adds the field after reference planning."""
    return ""


def default_negative_prompt(visible_language: str, no_logo: bool = False) -> str:
    base = (
        "low quality, blurry, pixelated, overexposed, harsh shadows, messy background, cheap fashion look, "
        "tacky styling, excessive accessories, unrealistic fabric, plastic texture, wrong garment construction, "
        "wrong garment type, wrong color, wrong print, missing hardware, incorrect patch, different model "
        "when model references are attached, changed face when model references are attached, changed hairstyle when model "
        "references are attached, changed skin tone when model references are attached, wrong gender, distorted body, extra "
        "fingers, missing fingers, unnatural hands, deformed face, bad anatomy, incorrect proportions, duplicated model, "
        "floating clothing, wrinkled dirty fabric, visible competitor logos, random text, watermark, spelling errors, "
        "Chinese characters, CJK text, bilingual text, local file paths, prompt metadata, cluttered layout, exaggerated pose, "
        "overly sexy pose, cartoon style, illustration style, CGI look, fake mannequin look"
    )
    if no_logo:
        base = (
            f"{base}, added layout logo, enlarged logo, redesigned wordmark, floating brand badge, "
            "invented brand mark, separate decorative logo element"
        )
    else:
        base = f"{base}, missing logo"
    if visible_language == "German":
        return f"{base}, English visible copy, English labels, wrong German grammar, missing German umlauts"
    return f"{base}, non-English labels"


def sanitize_negative_prompt(value: str, visible_language: str, no_logo: bool = False) -> str:
    cleaned = sanitize_prompt_context(value)
    cleaned = re.sub(r"\bvisible brand logos\b", "visible competitor or invented brand logos", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bcompetitor logos\b", "competitor or invented brand logos", cleaned, flags=re.IGNORECASE)
    if no_logo:
        cleaned = re.sub(r"\bmissing logo\b,?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = (
            f"{cleaned}, added layout logo, enlarged logo, redesigned wordmark, floating brand badge, "
            "invented brand mark, separate decorative logo element"
        ).strip(" ,")
    if visible_language == "German":
        cleaned = re.sub(r"\bnon-English labels\b", "English visible copy, English labels", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bAll visible rendered text must be English only\.?", "", cleaned, flags=re.IGNORECASE)
    return cleaned


def field_text(
    field_map: dict[str, str],
    key: str,
    section: dict[str, object],
    global_context: str,
    visible_language: str = "English",
) -> str:
    resolved_key = f"Resolved {key}"
    if field_map.get(resolved_key):
        resolved = str(field_map.get(resolved_key, ""))
        if key == "Copy":
            return preserve_section_copy_text(resolved)
        if key == "Headline":
            return clean_headline(resolved)
        return sanitize_prompt_context(resolved)
    index = int(section.get("index", 0))
    generated_headline, generated_copy = generated_section_text(index, global_context, visible_language, section)
    if key == "Headline":
        value = clean_headline(field_map.get("Headline", ""))
        if value:
            return value
        if visible_language == "German" and field_map.get("Headline Source") != "1-产品属性表.xlsx":
            return generated_headline
        return generated_headline
    if key == "Copy":
        if field_map.get("Copy Source") == "1-产品属性表.xlsx":
            return preserve_section_copy_text(field_map.get("Copy", ""))
        if visible_language == "German":
            return generated_copy
        value = clean_copy(field_map.get("Copy", ""))
        if value and value != clean_headline(field_map.get("Headline", "")) and not copy_looks_like_module_instruction(value):
            return value
        return generated_copy
    return sanitize_prompt_context(field_map.get(key, ""))


def duplicate_key(value: str) -> str:
    cleaned = sanitize_prompt_context(value).casefold()
    cleaned = re.sub(r"[^a-z0-9\u00c0-\u024f]+", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def text_is_excel_authored(section: dict[str, object], key: str) -> bool:
    fields = section.get("fields") if isinstance(section.get("fields"), dict) else {}
    return str(fields.get(f"{key} Source") or "") == "1-产品属性表.xlsx"


def store_resolved_text(section: dict[str, object], headline: str, copy: str) -> None:
    fields = section.get("fields") if isinstance(section.get("fields"), dict) else {}
    section["fields"] = fields
    fields["Resolved Headline"] = headline
    fields["Resolved Copy"] = copy


def ensure_unique_section_texts(
    sections: list[dict[str, object]],
    global_context: str,
    visible_language: str,
) -> None:
    seen_headlines: set[str] = set()
    seen_copies: set[str] = set()
    for section in sections:
        fields = section.get("fields") if isinstance(section.get("fields"), dict) else {}
        field_map = {str(k): str(v).strip() for k, v in fields.items()}
        index = int(section.get("index", 0))
        if section_requests_no_visible_copy(section):
            store_resolved_text(
                section,
                "No visible headline. Keep this module text-free." if visible_language != "German" else "Keine sichtbare Überschrift.",
                "No visible copy. Create only a clean style-matched background for later influencer content replacement."
                if visible_language != "German"
                else "Keine sichtbare Copy; nur einen ruhigen, stilistisch passenden Hintergrund erstellen.",
            )
            continue

        headline = field_text(field_map, "Headline", section, global_context, visible_language)
        copy = field_text(field_map, "Copy", section, global_context, visible_language)
        category = product_category_key(global_context)
        intent = section_intent(section, index)
        headline_key = duplicate_key(headline)
        copy_key = duplicate_key(copy)

        variant = 1
        while (
            (headline_key and headline_key in seen_headlines and not text_is_excel_authored(section, "Headline"))
            or (copy_key and copy_key in seen_copies and not text_is_excel_authored(section, "Copy"))
        ) and variant <= 8:
            alternate = dynamic_product_section_text(index, intent, category, global_context, visible_language, variant)
            if not alternate:
                alternate = generated_section_text(index, global_context, visible_language, section)
            alt_headline, alt_copy = alternate
            if headline_key in seen_headlines and not text_is_excel_authored(section, "Headline"):
                headline = alt_headline
                headline_key = duplicate_key(headline)
            if copy_key in seen_copies and not text_is_excel_authored(section, "Copy"):
                copy = alt_copy
                copy_key = duplicate_key(copy)
            variant += 1

        if headline_key and headline_key in seen_headlines and not text_is_excel_authored(section, "Headline"):
            suffix_feature = feature_by_priority(global_context, ("graphic", "fabric", "fit", "pocket", "zip", "mesh", "embroidery", "hem"), index + variant)
            if suffix_feature:
                headline = short_headline(suffix_feature, headline)
                headline_key = duplicate_key(headline)
        if copy_key and copy_key in seen_copies and not text_is_excel_authored(section, "Copy"):
            suffix_feature = feature_by_priority(global_context, ("graphic", "fabric", "fit", "pocket", "zip", "mesh", "embroidery", "hem"), index + variant)
            noun = product_noun(product_fact(global_context, "Product type") or "apparel")
            if suffix_feature:
                if visible_language == "German":
                    copy = f"{suffix_feature} gibt dem {noun} einen eigenen Verkaufsfokus fuer diese Section."
                else:
                    copy = f"{suffix_feature} gives this {noun} a distinct selling focus for this section."
                copy_key = duplicate_key(copy)

        store_resolved_text(section, headline, copy)
        if headline_key:
            seen_headlines.add(headline_key)
        if copy_key:
            seen_copies.add(copy_key)


def build_full_prompt_document(
    global_context: str,
    sections: list[dict[str, object]],
    module_size: tuple[int, int],
    visual_baseline: str,
    visible_language: str = "English",
    template_requirements: str = "",
    logo_disabled: bool = False,
) -> str:
    width, height = module_size
    canvas_height = height * len(sections)
    product_summary = extract_product_summary(global_context)
    section_blocks: list[str] = []
    for section in sections:
        fields = section.get("fields") if isinstance(section.get("fields"), dict) else {}
        field_map = {str(k): str(v).strip() for k, v in fields.items()}
        index = int(section.get("index", 0))
        no_logo = logo_disabled or section_disables_logo(global_context, section)
        no_references = section_requests_no_references(section)
        title = clean_section_title(str(section.get("title") or f"Section {index}"), index)
        headline = field_text(field_map, "Headline", section, global_context, visible_language)
        copy = field_text(field_map, "Copy", section, global_context, visible_language)
        if section_requests_no_visible_copy(section):
            headline = "No visible headline."
            copy = "No visible copy. Create only a clean styled background for later content replacement."
        visual = image_prompt_visual_direction(
            field_map.get("Visual Direction", str(section.get("block") or "")),
            section,
            global_context,
            visible_language,
            no_logo,
        )
        accuracy = image_prompt_accuracy(global_context, field_map.get("Product Accuracy Notes", ""), visible_language, no_logo, no_references)
        logo_note = f"\nNo LOGO rule:\n{no_logo_instruction(visible_language)}" if no_logo else ""
        no_reference_note = (
            "\nNo reference images rule:\nNo reference images are attached for this module. Build the image from this written prompt only."
            if no_references
            else ""
        )
        reference_note = (
            "\nReference note:\nUse the attached model reference images for the same person, pose attitude, styling mood, and on-body fit."
            if section_uses_model(section) and not no_references
            else ""
        )
        section_blocks.append(
            f"""Section {section.get('index')} - {title}
Headline:
{headline or title.upper()}

Copy:
{copy}

Visual Direction:
{visual}

Product Accuracy:
{accuracy}{logo_note}{reference_note}{no_reference_note}
"""
        )

    language_instruction = visible_text_instruction(visible_language)
    negative_prompt = default_negative_prompt(visible_language, logo_disabled)
    logo_reference_phrase = "product flat lays, model/on-body images, detail images, and product information"
    if not logo_disabled:
        logo_reference_phrase = "product flat lays, model/on-body images, detail images, logo reference, and product information"

    return f"""You are a creative director and visual merchandising expert for Amazon A+ apparel content.
Based on the supplied {logo_reference_phrase}, create a premium, clean, modern Amazon A+ image system with clear selling points and low shopper comprehension cost.

Canvas Specification
Total canvas size: {width} x {canvas_height} px
Page split: {len(sections)} images / {len(sections)} modules
Single module size: {width} x {height} px

Style
Overall visual direction:
Premium Amazon apparel e-commerce, clean editorial, modern streetwear, clear product-first layout.
Keep the page unified in tone, typography, spacing, photo treatment, callout style, and color palette.
Use a restrained commercial page feel rather than an over-designed brand poster.

Suggested Visual Baseline
{visual_baseline}

Template Design Requirements
{template_requirements or ('- ' + no_logo_instruction(visible_language) if logo_disabled else '- Use clean sans-serif typography, consistent spacing, and exact supplied brand assets when visible.')}

Product Information
{localized_product_summary(global_context, visible_language)}

Module Structure
{chr(10).join(section_blocks)}

Unified Negative Prompt:
{negative_prompt}

Design Execution Requirements
Keep every module visually consistent.
The clothing is the main subject; backgrounds only support atmosphere.
Model poses should feel natural, not exaggerated.
Each module should express one core idea.
Keep key information inside the central safe area.
Use clean sans-serif typography, bold short headlines, minimal body copy, and generous white space.
{language_instruction}
"""


def build_prompt(
    brief_text: str,
    global_context: str,
    section: dict[str, object],
    module_count: int,
    module_size: tuple[int, int],
    visual_baseline: str,
    visible_language: str = "English",
    template_requirements: str = "",
    logo_disabled: bool = False,
) -> str:
    width, height = module_size
    fields = section.get("fields") if isinstance(section.get("fields"), dict) else {}
    field_map = {str(k): str(v).strip() for k, v in fields.items()}
    index = int(section.get("index", 0))
    no_logo = logo_disabled or section_disables_logo(global_context, section)
    no_references = section_requests_no_references(section)
    title = clean_section_title(str(section.get("title") or f"Section {index}"), index)
    headline = field_text(field_map, "Headline", section, global_context, visible_language)
    copy = field_text(field_map, "Copy", section, global_context, visible_language)
    if section_requests_no_visible_copy(section):
        headline = "No visible headline. Keep this module text-free."
        copy = "No visible copy. Create only a clean style-matched background for later influencer content replacement."
    visual = image_prompt_visual_direction(
        field_map.get("Visual Direction", str(section.get("block") or "")),
        section,
        global_context,
        visible_language,
        no_logo,
    )
    accuracy = image_prompt_accuracy(global_context, field_map.get("Product Accuracy Notes", ""), visible_language, no_logo, no_references)
    negative = sanitize_negative_prompt(field_map.get("Negative Prompt", ""), visible_language, no_logo)
    language_instruction = visible_text_instruction(visible_language)

    model_reference_note = ""
    if section_uses_model(section) and not no_references:
        model_reference_note = """
Reference note:
- Model reference images are attached for this module. Match the same person, gender presentation, face/hair impression, body type, pose attitude, and styling mood shown in those references.
"""

    if visible_language == "German":
        german_model_reference_note = ""
        if section_uses_model(section) and not no_references:
            german_model_reference_note = """
Referenzhinweis:
- Für dieses Modul sind Model-Referenzbilder angehängt. Erhalte dieselbe Person, Geschlechtspräsentation, Gesicht-/Haarwirkung, Körperform, Posenhaltung und Styling-Stimmung aus diesen Referenzen.
"""
        logo_requirement = ""
        if no_logo:
            logo_requirement = f"""
Keine LOGO-Regel:
- {no_logo_instruction(visible_language)}
"""
        elif int(section.get("index", 0)) == 1 and not no_references:
            logo_requirement = """
LOGO-Referenz:
- Dies ist Section 1. Ein Produkt-LOGO-Referenzbild ist angehängt. Folge bei jeder Logo-Darstellung exakt der Wortmarke, Buchstabenform und visuellen Stilistik dieses LOGOs. Nutze es nur als Logo-Referenz, nicht als Kleidungs- oder Model-Identitätsreferenz.
"""
        no_reference_requirement = """
Keine Referenzbilder-Regel:
- Für dieses Modul werden keine Referenzbilder angehängt. Erzeuge das Bild ausschließlich aus diesem geschriebenen Prompt.
""" if no_references else ""
        return f"""Du erstellst ein einzelnes Amazon A+ Bekleidungsmodul aus einer vollständigen Creative Direction.

Canvas-Spezifikation
Erzeuge genau ein eigenständiges horizontales Modul.
Einzelmodulgröße: {width} x {height} px.
Dies ist Modul {section.get('index')} von {module_count}: {title}.
Keine lange Gesamtseite und keine anderen Module erzeugen.

Globaler Stil
Premium Amazon A+ E-Commerce für Bekleidung, clean editorial, moderner Streetwear-Charakter, klare produktorientierte Gestaltung.
Nutze eine zurückhaltende kommerzielle Seitenwirkung, großzügigen Weißraum, konsistente Typografie, weiches Studiolicht und Farben, die direkt aus dem Produkt abgeleitet sind.
{language_instruction}

Empfohlene visuelle Basis
{visual_baseline}

Template Design Requirements
{template_requirements or ('- ' + no_logo_instruction(visible_language) if no_logo else '- Use clean sans-serif typography, consistent spacing, and exact supplied brand assets when visible.')}

Produktinformationen
{localized_product_summary(global_context, visible_language)}

Section {section.get('index')} - {title}
Überschrift:
{headline}

Copy:
{copy}

Visuelle Richtung:
{visual}

Produktgenauigkeit:
{accuracy}

{german_model_reference_note}
{logo_requirement}
{no_reference_requirement}
Negative Prompt:
{negative or default_negative_prompt(visible_language, no_logo)}
"""

    return f"""You are creating one Amazon A+ apparel module from a full-page creative direction.

Canvas Specification
Generate exactly one independent horizontal module.
Single module size: {width} x {height} px.
This is module {section.get('index')} of {module_count}: {title}.
Do not generate a full long page or other modules.

Global Style
Premium Amazon apparel e-commerce, clean editorial, modern streetwear, clear product-first layout.
Use a restrained commercial page feel, generous white space, consistent typography, soft studio light, and product-derived colors.
{language_instruction}

Suggested Visual Baseline
{visual_baseline}

Template Design Requirements
{template_requirements or ('- ' + no_logo_instruction(visible_language) if no_logo else '- Use clean sans-serif typography, consistent spacing, and exact supplied brand assets when visible.')}

Product Information
{localized_product_summary(global_context, visible_language)}

Section {section.get('index')} - {title}
Headline:
{headline}

Copy:
{copy}

Visual Direction:
{visual}

Product Accuracy:
{accuracy}

{model_reference_note}
{("No LOGO rule:\n- " + no_logo_instruction(visible_language) + "\n") if no_logo else ("Logo Reference Requirement:\n- This is Section 1. A product LOGO reference image is attached. Follow that LOGO's exact brand wordmark, letter shape, and visual style for any logo exposure in this module. Use it only as a logo reference, not as garment or model identity reference.\n" if int(section.get('index', 0)) == 1 and not no_references else "")}
{("No reference images rule:\n- No reference images are attached for this module. Build the image from this written prompt only.\n" if no_references else "")}
Negative Prompt:
{negative or default_negative_prompt(visible_language, no_logo)}
"""


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--creative-brief", required=True, help="Path to _aplus_creative_work/aplus_creative_brief.md")
    parser.add_argument("--template-analysis", help="Optional JSON from analyze_template.py.")
    parser.add_argument("--out-dir", help="Output directory. Defaults to sibling module_prompts.")
    args = parser.parse_args()

    brief_path = Path(args.creative_brief).expanduser().resolve()
    if not brief_path.exists():
        raise SystemExit(f"Creative brief not found: {brief_path}")
    text = read_text(brief_path)
    analysis = read_analysis(Path(args.template_analysis).expanduser().resolve() if args.template_analysis else None)
    module_size = analysis_module_size(analysis, text)
    sections = parse_sections(text, analysis)
    product_dir = brief_path.parent.parent
    excel_overrides = read_excel_section_copy(product_dir)
    apply_excel_copy_overrides(sections, excel_overrides)
    validate_excel_section_ownership(sections, excel_overrides)
    apply_section_one_pose(sections, batch_pose_for_product(product_dir))
    visible_language = excel_value_language(product_dir)
    template_requirements = template_design_requirements(analysis, visible_language)
    logo_disabled = analysis_disables_logo(analysis) or template_disables_logo_from_text(text)
    out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else brief_path.parent / "module_prompts"
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("*.txt"):
        stale.unlink()

    global_context = extract_global_context(text)
    baseline_fields = extract_manual_visual_baseline(text)
    ensure_manual_visual_baseline_is_unique(product_dir, baseline_fields)
    visual_baseline = visual_baseline_text(baseline_fields)
    ensure_unique_section_texts(sections, global_context, visible_language)
    validate_cross_section_duplicates(sections)
    full_prompt = build_full_prompt_document(
        global_context,
        sections,
        module_size,
        visual_baseline,
        visible_language,
        template_requirements,
        logo_disabled,
    )
    full_prompt = final_api_prompt_text(full_prompt)
    (brief_path.parent / "aplus_full_prompt.txt").write_text(full_prompt, encoding="utf-8-sig")
    for section in sections:
        index = int(section.get("index", 1))
        title = clean_section_title(str(section.get("title") or f"Section {index}"), index)
        prompt = build_prompt(
            text,
            global_context,
            section,
            len(sections),
            module_size,
            visual_baseline,
            visible_language,
            template_requirements,
            logo_disabled,
        )
        if section_requests_no_references(section):
            prompt = strip_reference_claims_for_no_reference(prompt)
        prompt = final_api_prompt_text(prompt)
        out_path = out_dir / f"{slugify(index, title)}.txt"
        out_path.write_text(prompt, encoding="utf-8-sig")
        print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
