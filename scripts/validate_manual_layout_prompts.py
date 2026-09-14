#!/usr/bin/env python
"""Validate manual layout, callouts, action placement, language, and prompt safety."""

from __future__ import annotations

import argparse
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

from build_creative_module_prompts import excel_value_language


LAYOUT_BLOCK_RE = re.compile(
    r"(?ims)^\s*Layout execution:\s*(.+?)(?=^\s*Product Accuracy\s*:|\Z)"
)
CALLOUT_BLOCK_RE = re.compile(
    r"(?ims)^\s*Text[ \t]*/[ \t]*Callouts\s*:\s*(.+?)"
    r"(?=^\s*(?:Reference note|Referenzhinweis|No LOGO rule|Keine LOGO-Regel|"
    r"Logo Reference Requirement|LOGO-Referenz|No reference images rule|Keine Referenzbilder-Regel|"
    r"No-model reference rule|Negative Prompt|Technical seed note)\s*:|\Z)"
)
LAYOUT_TASK_RE = re.compile(
    r"(?ims)^\s*Layout task:\s*(.+?)(?=^\s*(?:Layout execution|Product Accuracy)\s*:|\Z)"
)
PRODUCT_ACCURACY_RE = re.compile(r"(?im)^\s*Product Accuracy\s*:")
SEPARATE_ACTION_RE = re.compile(r"(?im)^\s*Section 3 (?:fashion action|Modeaktion)\s*:")
INTERVENING_AFTER_ACCURACY_RE = re.compile(
    r"(?im)^\s*(?:Reference note|Referenzhinweis|No LOGO rule|Keine LOGO-Regel|"
    r"Logo Reference Requirement|LOGO-Referenz|No reference images rule|Keine Referenzbilder-Regel|"
    r"No-model reference rule|Negative Prompt|Technical seed note)\s*:"
)
NEGATIVE_EMPTY_CORRECTION_RE = re.compile(
    r"(?is)\b(?:rather\s+than|instead\s+of|avoid|do\s+not|don't|without|"
    r"anstatt|statt|vermeide|nicht|ohne)\b.{0,140}\b(?:empty|blank|bare|sparse|"
    r"leer|leere|leeren|kahl|kahle|kahlen)\b"
)
RESTRAINED_STYLE_RE = re.compile(
    r"(?i)\b(?:restrained|minimal|minimalist|minimalistic|understated|zurückhaltend|minimalistisch)\b"
)
LIGHT_TREATMENT_RE = re.compile(
    r"(?i)\b(?:white|warm-white|off-white|ivory|cream(?:y)?|pale|weiß|creme|elfenbein|blass)\b"
)
OPEN_SPACE_RE = re.compile(
    r"(?i)\b(?:generous|ample|expansive|großzügig(?:e[rmns]?)?)\s+"
    r"(?:pale\s+)?(?:white|negative|open|weiße[nrms]?|negativ(?:e[rmns]?)?)\s+(?:space|raum)\b|"
    r"\b(?:white|negative)\s+space\b|\bnegativraum\b"
)
EMPTY_RESULT_RE = re.compile(r"(?i)\b(?:empty|blank|bare|sparse|leer|leere|leeren|kahl|kahle|kahlen)\b")
INTENTIONAL_EMPTY_BACKGROUND_RE = re.compile(
    r"(?i)\b(?:influencer\s+replacement\s+background|background\s+only|"
    r"text-free[^\n]{0,80}people-free|empty\s+background[^\n]{0,80}(?:replacement|later))\b"
)
TEXT_FREE_RE = re.compile(
    r"(?i)\b(?:no visible (?:headline|copy)|text-free|no text|without visible copy|"
    r"keine sichtbare[nr]? (?:überschrift|texte?)|textfrei|ohne sichtbaren text)\b"
)
NO_CALLOUT_INSTRUCTION_RE = re.compile(
    r"(?i)\b(?:no visible callouts?|no callouts?|keep (?:this )?(?:module )?text-free|"
    r"keine sichtbaren callouts?|keine callouts?|textfrei halten)\b"
)
GERMAN_WORD_RE = re.compile(
    r"(?i)\b(?:der|die|das|den|dem|des|ein|eine|einer|einem|einen|und|oder|mit|ohne|"
    r"für|auf|aus|bei|durch|im|in|von|vor|hinter|zwischen|über|unter|während|"
    r"platziere|positioniere|verwende|halte|lasse|bewahre|zeige|vermeide|bleibt|"
    r"soll|muss|damit|sodass|nicht)\b"
)
ENGLISH_WORD_RE = re.compile(
    r"(?i)\b(?:the|and|or|with|without|for|on|from|at|through|in|of|before|behind|"
    r"between|over|under|while|place|position|use|keep|let|preserve|show|avoid|"
    r"remain|should|must|so|that|not)\b"
)
UNSUPPORTED_MEASUREMENT_RE = re.compile(
    r"(?i)\b\d+(?:\.\d+)?\s*(?:%|cm|mm|inches?|in\b|oz|gsm)"
)
DETAIL_MODULE_ROLES = {"construction_detail", "fabric_detail", "graphic_detail"}
DETAIL_GEOMETRY_PATTERNS = [
    (
        "curved/arched/irregular/crescent layout viewport",
        re.compile(
            r"(?is)\b(?:curv\w*|arch\w*|arc(?:ed|ing)?|crescent|irregular|organic(?:ally)?[- ]shaped|"
            r"freeform|blob[- ]shaped|gebog\w*|bogenf[oö]rm\w*|sichel(?:f[oö]rm\w*)?|"
            r"unregelm[aä][sß]ig\w*|organisch\w*|freiform\w*)\b(?:\s+\w+){0,3}\s+\b(?:crop\w*|window\w*|"
            r"frame\w*|panel\w*|mask\w*|viewport\w*|tile\w*|collage\w*|ausschnitt\w*|fenster\w*|"
            r"rahmen\w*|paneel\w*|maske\w*)\b|"
            r"\b(?:crop\w*|window\w*|frame\w*|panel\w*|mask\w*|viewport\w*|tile\w*|collage\w*|"
            r"ausschnitt\w*|fenster\w*|rahmen\w*|paneel\w*|maske\w*)\b\s+(?:with|using|shaped|formed|built|"
            r"mit|als)\b.{0,30}\b(?:curv\w*|"
            r"arch\w*|arc(?:ed|ing|s)?|crescent|irregular|organic(?:ally)?[- ]shaped|freeform|"
            r"blob[- ]shaped|gebog\w*|bogenf[oö]rm\w*|b[oö]gen|sichel(?:f[oö]rm\w*)?|"
            r"unregelm[aä][sß]ig\w*|organisch\w*|freiform\w*)\b|"
            r"(?:弧形|曲线|弯曲|不规则|月牙形|新月形|有机形|自由形).{0,30}(?:裁切|视窗|窗口|框架|面板|蒙版|拼贴)"
        ),
    ),
    (
        "fold-following window or mask",
        re.compile(
            r"(?is)\b(?:follow\w*|trace\w*|track\w*|conform\w*)\b.{0,50}\b(?:fold\w*|crease\w*|"
            r"drape\w*)\b|\bfold[- ]following\b|\b(?:der|den|die)\s+falte\s+(?:folgen|folgend|"
            r"nachzeichnen)\b|(?:顺应|沿着|跟随|贴合).{0,20}(?:褶皱|折痕|垂褶)"
        ),
    ),
    (
        "nested crown-panel arc frames",
        re.compile(
            r"(?is)\b(?:crown[- ]panel\w*|cap panel\w*)\b.{0,70}\b(?:arc\w*|nested frame\w*)\b|"
            r"\bnested\b.{0,40}\barc\w*\b.{0,40}\bframe\w*\b|帽冠.{0,20}(?:弧线|弧形).{0,20}(?:嵌套|框架)"
        ),
    ),
    (
        "fan-shaped curved crop sequence",
        re.compile(
            r"(?is)\bfan(?:ned|ning)?\s+out\b.{0,70}\bcurv\w*\s+crop\w*\b|"
            r"\bf[aä]cherf[oö]rm\w*\b.{0,70}\bgebog\w*\s+ausschnitt\w*\b|扇形.{0,30}(?:弧形|曲线|弯曲).{0,20}裁切"
        ),
    ),
    (
        "lower-left to upper-right diagonal material field with curved overlap",
        re.compile(
            r"(?is)\b(?:diagonal|diagonales?)\b.{0,80}\b(?:field|surface|material|texture|feld|fl[aä]che|"
            r"material|textur)\b.{0,120}\b(?:lower[- ]left|unten links)\b.{0,80}\b(?:upper[- ]right|oben rechts)\b|"
            r"(?:左下|左下角).{0,60}(?:右上|右上角).{0,60}(?:对角|斜向|材质场|面料场)"
        ),
    ),
]
GENERIC_LAYOUT_TASK_RES = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bbuild a horizontal hero/brand banner around\b",
        r"\bcreate a model fit board with multiple model angles\b",
        r"\bcreate a combined model-plus-flat-lay composition\b",
        r"\bcreate a people-free detail/macro collage with multiple product crops\b",
        r"\bcreate a text-free, people-free, style-matched background module\b",
        r"\berstelle ein modell-fit-board mit mehreren modellansichten\b",
        r"\berstelle eine kombinierte modell-und-flatlay-komposition\b",
    )
]
TASK_COMPOSITION_RE = re.compile(
    r"(?i)\b(?:composition|campaign|sequence|story|proof|study|environment|scene|setting|world|set|"
    r"asymmetr(?:y|ic)|hierarchy|anchor|cluster|collage|layer|rhythm|flow|"
    r"komposition|kampagne|sequenz|szene|hierarchie|anker|collage|ebene|rhythmus|blickführung)\b"
)
TASK_EVIDENCE_RE = re.compile(
    r"(?i)\b(?:silhouette|fit|shape|volume|front|back|profile|closure|construction|"
    r"graphic|print|embroidery|fabric|texture|pocket|waist|hem|brim|crown|detail|"
    r"passform|silhouette|volumen|vorderseite|rückseite|profil|verschluss|konstruktion|"
    r"grafik|druck|stickerei|stoff|textur|tasche|bund|saum|krempe|detail)\b"
)
BACKGROUND_TASK_RE = re.compile(
    r"(?i)\b(?:background|environment|set|studio|wall|floor|architecture|compositing|"
    r"hintergrund|umgebung|set|studio|wand|boden|architektur|compositing)\b"
)
BACKGROUND_MATERIAL_RE = re.compile(
    r"(?i)\b(?:brick|plaster|concrete|pavement|light|reflection|shadow|texture|gradient|"
    r"ziegel|putz|beton|pflaster|licht|reflexion|schatten|textur|verlauf)\b"
)
BACKGROUND_ZONE_RE = re.compile(
    r"(?i)\b(?:standing area|compositing (?:area|zone|space)|open (?:area|zone|space)|"
    r"open for (?:a )?future|future (?:model|person|influencer|full-body subject)|"
    r"stellfläche|compositing[- ]?(?:fläche|zone|raum)|"
    r"offene[rn]? (?:fläche|zone|raum)|spätere[rn]? (?:modell|person|influencer))\b"
)
DESIGN_CUE_GROUPS = {
    "hierarchy": re.compile(
        r"(?i)\b(?:dominant|anchor|focal|largest|primary|secondary|hierarchy|supporting|"
        r"visual foundation|main subject|dominant|anker|fokus|größte|primär|sekundär|"
        r"hierarchie|unterstützend|visuelle grundlage|hauptmotiv)\b"
    ),
    "placement_scale": re.compile(
        r"(?i)\b(?:left|right|center|centre|upper|lower|third|percent|full-height|"
        r"smaller|larger|scale|crop|offset|links|rechts|mitte|oben|unten|drittel|"
        r"prozent|kleiner|größer|maßstab|anschnitt|versetzt)\b"
    ),
    "depth_layering": re.compile(
        r"(?i)\b(?:overlap|layer|behind|foreground|background|plane|arc|curve|panel|"
        r"frame|shadow|depth|überlapp|ebene|hinter|vordergrund|hintergrund|bogen|"
        r"kurve|fläche|rahmen|schatten|tiefe)\w*\b"
    ),
    "connection_flow": re.compile(
        r"(?i)\b(?:connect|connector|leader|line|separator|sequence|step|bridge|guide|travel|reading order|"
        r"eye should move|visual flow|link|verbinde|verbindung|linie|brücke|führen|"
        r"blickführung|lesereihenfolge|visueller fluss)\w*\b"
    ),
    "typography": re.compile(
        r"(?i)\b(?:headline|title|copy|callout|caption|typography|text-free|no text|"
        r"überschrift|titel|textblock|callout|beschriftung|typografie|textfrei|ohne text)\b"
    ),
    "product_protection": re.compile(
        r"(?i)\b(?:unobstructed|visibl\w*|readable|preserv\w*|protect\w*|maintain\w*|"
        r"clear separation|do not cover|keep clear|never (?:cover|cross|touch|obscure)|"
        r"no \w+ crossing|unverdeckt|sichtbar|lesbar|bewahr\w*|schütz\w*|erhalt\w*|"
        r"freie sicht|nicht verdecken)\b"
    ),
}


def normalized_similarity_text(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9äöüß]+", text.casefold()))


def text_similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, normalized_similarity_text(left), normalized_similarity_text(right)).ratio()


def extract_layout_fields(text: str) -> tuple[str, str]:
    task_match = LAYOUT_TASK_RE.search(text)
    execution_match = LAYOUT_BLOCK_RE.search(text)
    task = re.sub(r"\s+", " ", task_match.group(1)).strip() if task_match else ""
    execution = re.sub(r"\s+", " ", execution_match.group(1)).strip() if execution_match else ""
    return task, execution


def validate_detail_section_geometry(path: Path, text: str, module_role: str) -> list[str]:
    if module_role not in DETAIL_MODULE_ROLES:
        return []
    task, execution = extract_layout_fields(text)
    layout_text = f"{task}\n{execution}"
    errors: list[str] = []
    for label, pattern in DETAIL_GEOMETRY_PATTERNS:
        if pattern.search(layout_text):
            errors.append(
                f"{path.name}: product-detail section uses prohibited {label}; use straight-edged rectangular/orthogonal layout geometry"
            )
    return errors


def validate_designed_visual_direction(path: Path, text: str, expected_language: str) -> list[str]:
    errors: list[str] = []
    task, execution = extract_layout_fields(text)
    if not task or not execution:
        return errors
    if len(task) < 160:
        errors.append(f"{path.name}: Layout task is too short for a manually designed, product-specific concept")
    if len(execution) < 360:
        errors.append(f"{path.name}: Layout execution is too short for a fully specified designed composition")
    if len([part for part in re.split(r"[.!?]+", task) if part.strip()]) < 2:
        errors.append(f"{path.name}: Layout task must use at least two purposeful sentences")
    if any(pattern.search(task) for pattern in GENERIC_LAYOUT_TASK_RES):
        errors.append(f"{path.name}: Layout task still contains a prohibited builder/template starter; replace it completely")
    if not TASK_COMPOSITION_RE.search(task):
        errors.append(f"{path.name}: Layout task lacks a concrete composition concept or spatial relationship")
    intentional_background = bool(INTENTIONAL_EMPTY_BACKGROUND_RE.search(text))
    if intentional_background:
        if not BACKGROUND_TASK_RE.search(task):
            errors.append(f"{path.name}: empty-background Layout task lacks a concrete scene or compositing concept")
    elif not TASK_EVIDENCE_RE.search(task):
        errors.append(f"{path.name}: Layout task lacks product-specific evidence to keep readable")
    task_language = dominant_layout_language(task)
    if task_language != expected_language:
        errors.append(
            f"{path.name}: Layout task language must be {expected_language} for the product marketplace, detected {task_language}"
        )
    matched_groups = [name for name, pattern in DESIGN_CUE_GROUPS.items() if pattern.search(execution)]
    if intentional_background:
        background_score = len(matched_groups)
        background_score += int(bool(BACKGROUND_MATERIAL_RE.search(execution)))
        background_score += int(bool(BACKGROUND_ZONE_RE.search(execution)))
        minimum_score = 4
    else:
        background_score = len(matched_groups)
        minimum_score = 5
    if background_score < minimum_score:
        missing = sorted(set(DESIGN_CUE_GROUPS) - set(matched_groups))
        errors.append(
            f"{path.name}: Layout execution covers only {background_score} designed-composition dimensions; missing {', '.join(missing)}"
        )
    return errors


def dominant_layout_language(text: str) -> str:
    german_score = len(GERMAN_WORD_RE.findall(text))
    english_score = len(ENGLISH_WORD_RE.findall(text))
    if german_score >= 3 and german_score > english_score:
        return "German"
    if english_score >= 3 and english_score > german_score:
        return "English"
    return "Unknown"


def normalized_words(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9äöüß]+", text.casefold()) if len(word) > 2}


def field_body(text: str, start_label: str, end_label: str) -> str:
    match = re.search(
        rf"(?ims)^\s*{re.escape(start_label)}\s*:\s*(.*?)(?=^\s*{re.escape(end_label)}\s*:|\Z)",
        text,
    )
    return re.sub(r"\s+", " ", match.group(1)).strip() if match else ""


def positive_prompt_without_negative_block(text: str) -> str:
    return re.sub(r"(?ims)^\s*Negative Prompt:\s*.*\Z", "", text)


def prompt_risks_over_minimalism(text: str) -> bool:
    positive = positive_prompt_without_negative_block(text)
    if INTENTIONAL_EMPTY_BACKGROUND_RE.search(positive):
        return False
    restrained = bool(RESTRAINED_STYLE_RE.search(positive))
    light = bool(LIGHT_TREATMENT_RE.search(positive))
    open_space_count = len(OPEN_SPACE_RE.findall(positive))
    empty_result = bool(EMPTY_RESULT_RE.search(positive))
    return restrained and light and (open_space_count >= 2 or (open_space_count >= 1 and empty_result))


def validate_callouts(path: Path, text: str, callout_match: re.Match[str]) -> list[str]:
    errors: list[str] = []
    body = re.sub(r"\s+", " ", callout_match.group(1)).strip(" -")
    if len(body) < 10 or body.casefold() in {"none", "n/a", "na", "null"}:
        return [f"{path.name}: Text / Callouts must contain deliberate human-authored content"]
    if re.search(r"(?:\\\\|[A-Za-z]:\\|\.(?:png|jpe?g|webp)\b)", body, re.IGNORECASE):
        errors.append(f"{path.name}: Text / Callouts must not expose reference filenames or paths")
    text_without_callouts = f"{text[:callout_match.start()]}\n{text[callout_match.end():]}"
    if TEXT_FREE_RE.search(text_without_callouts):
        if not NO_CALLOUT_INSTRUCTION_RE.search(body):
            errors.append(f"{path.name}: text-free module callouts must explicitly say that no visible callouts should render")
        return errors
    headline = field_body(text_without_callouts, "Headline", "Copy")
    copy = field_body(text_without_callouts, "Copy", "Visual Direction")
    callout_words = normalized_words(body)
    for label, existing in (("Headline", headline), ("Copy", copy)):
        existing_words = normalized_words(existing)
        if not existing_words or not callout_words:
            continue
        overlap = len(callout_words & existing_words) / max(1, len(callout_words | existing_words))
        if body.casefold() == existing.casefold() or overlap >= 0.85:
            errors.append(f"{path.name}: Text / Callouts duplicates existing {label}; write complementary, non-conflicting information")
    for measurement in UNSUPPORTED_MEASUREMENT_RE.findall(body):
        if measurement.casefold() not in text_without_callouts.casefold():
            errors.append(f"{path.name}: Text / Callouts contains unsupported measurement {measurement!r}")
    return errors


def validate(product_dir: Path) -> list[str]:
    work_dir = product_dir / "_aplus_creative_work"
    prompt_dir = work_dir / "module_prompts"
    errors: list[str] = []
    layout_records: list[tuple[Path, str, str]] = []
    expected_language = excel_value_language(product_dir)
    prompts = sorted(prompt_dir.glob("section-*.txt"))
    if not prompts:
        return [f"No module prompts found: {prompt_dir}"]
    reference_map_path = work_dir / "module_reference_images.json"
    if not reference_map_path.exists():
        errors.append("module_reference_images.json must exist before human Text / Callouts are authored")
        reference_map: dict[str, object] = {}
    else:
        try:
            reference_map = json.loads(reference_map_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"invalid module_reference_images.json: {exc}")
            reference_map = {}
    requirements_path = work_dir / "module_reference_requirements.json"
    try:
        requirements = json.loads(requirements_path.read_text(encoding="utf-8-sig")) if requirements_path.exists() else {}
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"invalid module_reference_requirements.json: {exc}")
        requirements = {}
    for path in prompts:
        text = path.read_text(encoding="utf-8-sig")
        requirement = requirements.get(path.name, {}) if isinstance(requirements, dict) else {}
        module_role = str(requirement.get("module_role") or "") if isinstance(requirement, dict) else ""
        layout_matches = list(LAYOUT_BLOCK_RE.finditer(text))
        callout_matches = list(CALLOUT_BLOCK_RE.finditer(text))
        layout_task = LAYOUT_TASK_RE.search(text)
        product_accuracy = PRODUCT_ACCURACY_RE.search(text)
        if len(layout_matches) != 1:
            errors.append(f"{path.name}: expected exactly one 'Layout execution:' block, found {len(layout_matches)}")
        if len(callout_matches) != 1:
            errors.append(f"{path.name}: expected exactly one 'Text / Callouts:' block, found {len(callout_matches)}")
        if SEPARATE_ACTION_RE.search(text):
            errors.append(f"{path.name}: Section 3 fashion action must be merged into Layout task and may not be a separate block")
        if not layout_task:
            errors.append(f"{path.name}: missing Layout task")
        if not product_accuracy:
            errors.append(f"{path.name}: missing Product Accuracy")
        if layout_matches and layout_task and product_accuracy:
            layout_match = layout_matches[0]
            if not (layout_task.start() < layout_match.start() < product_accuracy.start()):
                errors.append(f"{path.name}: Layout execution must appear between Layout task and Product Accuracy")
            if text[layout_match.end():product_accuracy.start()].strip():
                errors.append(f"{path.name}: Layout execution must sit immediately before Product Accuracy")
            detected = dominant_layout_language(layout_match.group(1).strip())
            if detected != expected_language:
                errors.append(
                    f"{path.name}: Layout execution language must be {expected_language} for the product marketplace, detected {detected}"
                )
            if NEGATIVE_EMPTY_CORRECTION_RE.search(layout_match.group(1)):
                errors.append(
                    f"{path.name}: Layout execution repeats an unwanted empty/blank result in a negative correction; describe concrete positive layering actions instead"
                )
            errors.extend(validate_designed_visual_direction(path, text, expected_language))
            errors.extend(validate_detail_section_geometry(path, text, module_role))
            task_body, execution_body = extract_layout_fields(text)
            layout_records.append((path, task_body, execution_body))
        if callout_matches and product_accuracy:
            callout_match = callout_matches[0]
            if callout_match.start() <= product_accuracy.start():
                errors.append(f"{path.name}: Text / Callouts must appear after Product Accuracy")
            between = text[product_accuracy.start():callout_match.start()]
            if INTERVENING_AFTER_ACCURACY_RE.search(between):
                errors.append(f"{path.name}: Text / Callouts must sit immediately after the Product Accuracy content")
            errors.extend(validate_callouts(path, text, callout_match))
        no_reference = bool(re.search(r"(?i)No reference images rule|Keine Referenzbilder-Regel", text))
        if not no_reference and path.name not in reference_map:
            errors.append(f"{path.name}: final upload-image plan is missing; inspect uploaded references before writing Text / Callouts")
        if prompt_risks_over_minimalism(text):
            errors.append(
                f"{path.name}: positive prompt over-stacks restrained/minimal styling, white/pale treatment, and repeated generous white/negative-space cues; replace them with concrete hierarchy, overlap, trim, texture, and color-layer actions"
            )

    for index, (path, task, execution) in enumerate(layout_records):
        for other_path, other_task, other_execution in layout_records[index + 1 :]:
            task_score = text_similarity(task, other_task)
            execution_score = text_similarity(execution, other_execution)
            if task_score >= 0.82 or execution_score >= 0.82:
                errors.append(
                    f"{path.name} and {other_path.name}: Visual Direction is too similar within this SKU "
                    f"(task={task_score:.0%}, execution={execution_score:.0%}); redesign hierarchy and spatial rhythm"
                )

    full_prompt_path = work_dir / "aplus_full_prompt.txt"
    if not full_prompt_path.exists():
        errors.append(f"missing full prompt for manual Visual Direction synchronization: {full_prompt_path}")
    else:
        full_text = full_prompt_path.read_text(encoding="utf-8-sig")
        full_tasks = [re.sub(r"\s+", " ", match.group(1)).strip() for match in LAYOUT_TASK_RE.finditer(full_text)]
        full_executions = [re.sub(r"\s+", " ", match.group(1)).strip() for match in LAYOUT_BLOCK_RE.finditer(full_text)]
        if len(full_tasks) != len(layout_records) or len(full_executions) != len(layout_records):
            errors.append(
                f"aplus_full_prompt.txt has {len(full_tasks)} Layout task and {len(full_executions)} Layout execution fields; "
                f"expected {len(layout_records)} of each"
            )
        else:
            for index, (path, task, execution) in enumerate(layout_records):
                if task != full_tasks[index] or execution != full_executions[index]:
                    errors.append(
                        f"{path.name}: manual Visual Direction does not match aplus_full_prompt.txt; "
                        "run sync_manual_visual_directions.py"
                    )

    for path, task, execution in layout_records:
        for sibling in sorted(product_dir.parent.iterdir()):
            if sibling == product_dir or not sibling.is_dir():
                continue
            sibling_prompt = sibling / "_aplus_creative_work" / "module_prompts" / path.name
            if not sibling_prompt.exists():
                continue
            sibling_task, sibling_execution = extract_layout_fields(
                sibling_prompt.read_text(encoding="utf-8-sig")
            )
            if not sibling_task or not sibling_execution:
                continue
            task_score = text_similarity(task, sibling_task)
            execution_score = text_similarity(execution, sibling_execution)
            if task_score >= 0.88 or execution_score >= 0.86:
                errors.append(
                    f"{path.name}: Visual Direction is too similar to sibling SKU '{sibling.name}' "
                    f"(task={task_score:.0%}, execution={execution_score:.0%}); re-inspect this SKU and author a distinct concept"
                )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product-dir", required=True)
    args = parser.parse_args()
    product_dir = Path(args.product_dir).expanduser().resolve()
    errors = validate(product_dir)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"Manual prompt-field validation passed: {product_dir.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
