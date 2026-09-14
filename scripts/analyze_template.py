#!/usr/bin/env python
"""Analyze an Amazon A+ template and emit reusable run metadata."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


SECTION_RE = re.compile(r"(?m)^#\s+(.+?)\s*$")
SIZE_RE = re.compile(r"(\d{3,5})\s*[xX×*]\s*(\d{3,5})\s*px", re.IGNORECASE)
MODULE_COUNT_RE = re.compile(r"(?:页面拆分|拆分|模块数量|module\s*count).*?(\d+)", re.IGNORECASE)
SECTION_LINE_RE = re.compile(
    r"(?im)^\s*(?:[-*]\s*)?(?:section|module|模块)\s*0?(\d+)\s*[:：/\-.]?\s*(.+?)\s*$"
)


def read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def split_sections(text: str) -> dict[str, str]:
    matches = list(SECTION_RE.finditer(text))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        name = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[name] = text[start:end].strip()
    return sections


def find_section(sections: dict[str, str], names: tuple[str, ...]) -> str:
    for key, value in sections.items():
        lowered = key.lower()
        if any(name.lower() in lowered for name in names):
            return value
    return ""


def first_size_near(text: str, labels: tuple[str, ...]) -> tuple[int, int] | None:
    for line in text.splitlines():
        if any(label.lower() in line.lower() for label in labels):
            match = SIZE_RE.search(line)
            if match:
                return int(match.group(1)), int(match.group(2))
    return None


def module_count_from_text(text: str, sections: dict[str, str]) -> int | None:
    match = MODULE_COUNT_RE.search(text)
    if match:
        return int(match.group(1))
    presentation = find_section(sections, ("页面呈现点", "presentation", "page presentation"))
    numbers = [int(match.group(1)) for match in SECTION_LINE_RE.finditer(presentation)]
    return max(numbers) if numbers else None


def extract_modules(sections: dict[str, str], module_count: int) -> list[dict[str, object]]:
    presentation = find_section(sections, ("页面呈现点", "presentation", "page presentation"))
    modules: list[dict[str, object]] = []
    for match in SECTION_LINE_RE.finditer(presentation):
        number = int(match.group(1))
        instruction = match.group(2).strip()
        modules.append({"index": number, "title": f"Section {number}", "instruction": instruction})

    seen = {int(module["index"]) for module in modules}
    for index in range(1, module_count + 1):
        if index not in seen:
            modules.append({"index": index, "title": f"Section {index}", "instruction": ""})
    return sorted(modules, key=lambda item: int(item["index"]))


def extract_gender(sections: dict[str, str]) -> str | None:
    target = find_section(sections, ("target", "目标"))
    if "女装" in target or re.search(r"\bwomen'?s|female|womenswear\b", target, re.IGNORECASE):
        return "women"
    if "男装" in target or re.search(r"\bmen'?s|male|menswear\b", target, re.IGNORECASE):
        return "men"
    return None


def extract_style_terms(sections: dict[str, str]) -> list[str]:
    style_source = "\n".join(
        part
        for part in [
            find_section(sections, ("target", "目标")),
            find_section(sections, ("skills", "rules", "规则")),
            find_section(sections, ("页面呈现点", "presentation")),
        ]
        if part
    )
    candidates = [
        "Poppins",
        "Amazon",
        "premium studio",
        "editorial",
        "streetwear",
        "e-commerce",
        "minimal",
        "clean",
        "neutral",
        "callout",
        "annotation",
        "lifestyle",
    ]
    lowered = style_source.lower()
    return [term for term in candidates if term.lower() in lowered]


def is_positive_execution_rule(line: str) -> bool:
    lowered = line.lower()
    if "违规词" in line or "亚马逊违规" in line or "low quality" in lowered:
        return False
    positive_markers = (
        "字体",
        "font",
        "poppins",
        "logo",
        "brand logo",
        "品牌logo",
        "保持一致",
        "consistent",
        "match",
        "reference",
    )
    return any(marker in lowered for marker in positive_markers)


def clean_rule_line(line: str) -> str:
    value = line.strip().strip("`\"'")
    value = re.sub(r"^\s*\d+\s*[.、]\s*", "", value)
    return value.strip()


def extract_design_requirements(sections: dict[str, str]) -> list[str]:
    source = "\n".join(
        part
        for part in [
            find_section(sections, ("skills", "rules", "规则")),
            find_section(sections, ("target", "目标")),
        ]
        if part
    )
    requirements: list[str] = []
    for line in source.splitlines():
        cleaned = clean_rule_line(line)
        if not cleaned:
            continue
        if is_positive_execution_rule(cleaned):
            requirements.append(cleaned)

    unique: list[str] = []
    seen: set[str] = set()
    for requirement in requirements:
        key = requirement.casefold()
        if key not in seen:
            seen.add(key)
            unique.append(requirement)
    return unique


def extract_prohibited_terms(text: str) -> list[str]:
    terms: list[str] = []
    for line in text.splitlines():
        if re.search(r"严禁|禁止|avoid|do not|prohibited", line, re.IGNORECASE):
            if is_positive_execution_rule(line):
                continue
            fragments = re.split(r"[，,、;；()（）:：]", line)
            for fragment in fragments:
                value = fragment.strip(" `\"'")
                if 2 <= len(value) <= 40:
                    terms.append(value)
    unique: list[str] = []
    seen: set[str] = set()
    for term in terms:
        if term not in seen:
            seen.add(term)
            unique.append(term)
    return unique


def analyze_template(template: Path) -> dict[str, object]:
    text = read_text(template)
    sections = split_sections(text)
    module_count = module_count_from_text(text, sections) or 6
    module_size = first_size_near(text, ("单张模块尺寸", "module size", "single module")) or (1464, 600)
    canvas_size = first_size_near(text, ("总画布尺寸", "canvas", "画布")) or (
        module_size[0],
        module_size[1] * module_count,
    )
    return {
        "template_path": str(template),
        "headings": list(sections.keys()),
        "target_gender_in_template": extract_gender(sections),
        "canvas_size": {"width": canvas_size[0], "height": canvas_size[1]},
        "module_count": module_count,
        "module_size": {"width": module_size[0], "height": module_size[1]},
        "modules": extract_modules(sections, module_count),
        "style_terms": extract_style_terms(sections),
        "design_requirements": extract_design_requirements(sections),
        "prohibited_terms": extract_prohibited_terms(text),
        "allowed_rewrite_sections": ["Product Information", "页面呈现点"],
        "must_preserve_other_sections": True,
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", required=True, help="Path to root 模板.txt")
    parser.add_argument("--out", help="Optional JSON output path.")
    args = parser.parse_args()

    template = Path(args.template).expanduser().resolve()
    if not template.exists():
        raise SystemExit(f"Template not found: {template}")
    analysis = analyze_template(template)
    payload = json.dumps(analysis, ensure_ascii=False, indent=2)
    if args.out:
        out = Path(args.out).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload + "\n", encoding="utf-8-sig")
        print(out)
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
