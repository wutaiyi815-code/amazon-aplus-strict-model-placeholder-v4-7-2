#!/usr/bin/env python
"""Generate Amazon A+ module images through GPT-ToAPI or GPT-RH."""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from build_api_prompt_review import build_review
from generation_state import (
    load_state,
    module_state,
    now_iso,
    update_module_state,
    update_product_state,
)
from validate_manual_layout_prompts import validate as validate_manual_layout_prompts


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
DEFAULT_BACKOFF = [15, 30, 60, 120, 240]
SHORT_BACKOFF = [5, 10, 20]
UPLOAD_URL = "https://toapis.com/v1/uploads/images"
GENERATE_URL = "https://toapis.com/v1/images/generations"
RH_UPLOAD_URL = "https://www.runninghub.ai/openapi/v2/media/upload/binary"
RH_GENERATE_URL = "https://www.runninghub.ai/openapi/v2/rhart-image-g-2-official/image-to-image"
RH_TEXT_TO_IMAGE_URL = "https://www.runninghub.ai/openapi/v2/rhart-image-g-2-official/text-to-image"
RH_QUERY_URL = "https://www.runninghub.ai/openapi/v2/query"
SKIP_DIR_PREFIXES = ("_aplus", "_influencer")
HARD_EXCLUDED_DIR_NAMES = {"弃用", "过程文件", "生成结果", "输出结果", "备份", "备份目录"}
SECTION_RE = re.compile(r"section-0?(\d+)", re.IGNORECASE)
PROVIDER_TOAPI = "gpt-toapi"
PROVIDER_RH = "gpt-rh"
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


def configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def load_analysis(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {"module_size": {"width": 1464, "height": 600}}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def expected_size(analysis: dict[str, Any]) -> tuple[int, int]:
    data = analysis.get("module_size") or {}
    if isinstance(data, dict):
        return int(data.get("width", 1464)), int(data.get("height", 600))
    return 1464, 600


def normalize_api_key(value: str | None, provider: str) -> str:
    if not value:
        label = "RunningHub GPT-RH" if provider == PROVIDER_RH else "ToAPIs GPT-ToAPI"
        value = input(f"API Key for {label}: ").strip()
    if not value:
        raise SystemExit(f"Missing API key. {provider} cannot continue.")
    value = value.strip()
    return value if value.lower().startswith("bearer ") else f"Bearer {value}"


def request_with_retry(label: str, request_fn: Any, backoff: list[int] | None = None) -> Any:
    waits = backoff or SHORT_BACKOFF
    last_error = ""
    for attempt in range(1, len(waits) + 2):
        try:
            response = request_fn()
            response.raise_for_status()
            return response
        except Exception as exc:
            last_error = str(exc)
            if attempt <= len(waits):
                wait_time = waits[attempt - 1]
                print(f"  {label} attempt {attempt} failed: {last_error}. Retrying in {wait_time}s.")
                time.sleep(wait_time)
            else:
                raise RuntimeError(f"{label} failed after {len(waits) + 1} attempts: {last_error}") from exc


def product_dirs_from_root(root: Path, product_filter: str | None = None) -> list[Path]:
    product_dirs = sorted(
        [p for p in root.iterdir() if p.is_dir() and (p / "_aplus_creative_work" / "module_prompts").exists()],
        key=lambda p: p.name.lower(),
    )
    if product_filter:
        wanted = {item.strip().lower() for item in product_filter.split(",") if item.strip()}
        product_dirs = [path for path in product_dirs if path.name.lower() in wanted]
    return product_dirs


def section_index_from_prompt(path: Path) -> int:
    match = SECTION_RE.search(path.name)
    return int(match.group(1)) if match else 0


def prompt_disables_logo_text(text: str) -> bool:
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


def prompt_disables_logo(prompt_path: Path) -> bool:
    return prompt_disables_logo_text(read_text(prompt_path))


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


def prompt_disables_reference_images_text(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text.casefold())
    return any(term.casefold() in normalized for term in NO_REFERENCE_TERMS)


def prompt_disables_reference_images(prompt_path: Path) -> bool:
    return prompt_disables_reference_images_text(read_text(prompt_path))


def is_logo_path(path: Path) -> bool:
    return "logo" in path.stem.casefold() or path.name.casefold().startswith("logo")


def strip_logo_reference_notes(prompt: str) -> str:
    prompt = re.sub(
        r"(?is)\n?Logo Reference Requirement:\s*.*?(?=\n(?:Negative Prompt|Attached Reference Image Map|Text / Callouts|Product Accuracy|Visual Direction)\s*:|\Z)",
        "\n",
        prompt,
    )
    prompt = re.sub(
        r"(?is)\n?LOGO-Referenz:\s*.*?(?=\n(?:Negative Prompt|Attached Reference Image Map|Text / Callouts|Produktgenauigkeit|Visuelle Richtung)\s*:|\Z)",
        "\n",
        prompt,
    )
    cleaned_lines: list[str] = []
    for line in prompt.splitlines():
        lowered = line.casefold()
        if any(
            term in lowered
            for term in (
                "product logo reference",
                "attached logo reference",
                "section 1 logo instruction",
                "follow that logo",
                "exact brand wordmark",
                "logo exposure",
                "logo-reference",
                "logo-referenz",
                "logo reference image",
            )
        ):
            continue
        cleaned_lines.append(line)
    prompt = "\n".join(cleaned_lines).rstrip()
    no_logo_rule = (
        "No LOGO rule:\n"
        "- Do not add, enlarge, redesign, or use any brand LOGO, wordmark, brand mark, brand badge, or logo-like emblem "
        "as a separate layout design element. Preserve any small logo, label, embroidery, tag, patch, or brand detail "
        "that already exists naturally on the product reference images as part of the actual garment/product.\n"
    )
    if "no logo rule" not in prompt.casefold() and "keine logo-regel" not in prompt.casefold():
        prompt = f"{prompt}\n\n{no_logo_rule}"
    prompt = re.sub(r"\bmissing logo\b,?\s*", "", prompt, flags=re.IGNORECASE)
    prompt = re.sub(r"\n{3,}", "\n\n", prompt)
    return prompt.strip() + "\n"


def sanitize_overbroad_german_logo_rule(prompt: str) -> str:
    safe_rule = (
        "Keine Marken-LOGOs, Wortmarken, Brand Marks, Marken-Badges oder logoartigen Embleme als separate "
        "Layout-Designelemente hinzufügen, vergrößern, neu zeichnen oder dekorativ verwenden. Kleine Logos, "
        "Labels, Stickereien, Tags, Patches oder Markendetails, die bereits natürlich auf den Produktreferenzen "
        "vorhanden sind, als Teil des tatsächlichen Kleidungsstücks/Produkts erhalten."
    )
    unsafe_phrases = (
        "Keine sichtbaren Marken-LOGOs, Wortmarken, Brand Marks, Marken-Badges oder logoartigen Embleme darstellen. "
        "Keine LOGO-Referenz verwenden oder anfordern.",
        "Keine sichtbaren Marken-LOGOs, Wortmarken, Brand Marks, Marken-Badges oder logoartigen Embleme darstellen.",
    )
    for phrase in unsafe_phrases:
        prompt = prompt.replace(phrase, safe_rule)
    return prompt


def process_image_before_upload(path: Path, min_side_limit: int = 2048) -> io.BytesIO | None:
    try:
        from PIL import Image, ImageOps

        img = Image.open(path)
        img = ImageOps.exif_transpose(img)
        width, height = img.size
        min_side = min(width, height)
        if min_side > min_side_limit:
            scale = min_side_limit / min_side
            img = img.resize((int(width * scale), int(height * scale)), Image.Resampling.LANCZOS)
        stream = io.BytesIO()
        fmt = "JPEG" if path.suffix.lower() in {".jpg", ".jpeg"} else ("WEBP" if path.suffix.lower() == ".webp" else "PNG")
        img.save(stream, format=fmt, quality=95)
        stream.seek(0)
        return stream
    except Exception as exc:
        print(f"  Reference preprocessing failed, skipped: {path.name}: {exc}")
        return None


def rh_upload_url_from_body(body: dict[str, Any]) -> str | None:
    data = body.get("data")
    if isinstance(data, dict):
        return data.get("download_url") or data.get("url") or data.get("fileUrl")
    return body.get("download_url") or body.get("url")


def upload_image(requests_mod: Any, api_key: str, image_path: Path, provider: str) -> str | None:
    content_type = "image/jpeg" if image_path.suffix.lower() in {".jpg", ".jpeg"} else "image/png"

    def post_toapi_upload() -> Any:
        stream = process_image_before_upload(image_path)
        if not stream:
            raise RuntimeError(f"Reference preprocessing returned no stream: {image_path.name}")
        files = {"file": (image_path.name, stream, content_type)}
        return requests_mod.post(UPLOAD_URL, headers={"Authorization": api_key}, files=files, timeout=60)

    def post_rh_upload() -> Any:
        stream = process_image_before_upload(image_path)
        if not stream:
            raise RuntimeError(f"Reference preprocessing returned no stream: {image_path.name}")
        files = {"file": (image_path.name, stream, content_type)}
        return requests_mod.post(RH_UPLOAD_URL, headers={"Authorization": api_key}, files=files, timeout=120)

    response = request_with_retry(
        f"upload {image_path.name}",
        post_rh_upload if provider == PROVIDER_RH else post_toapi_upload,
    )
    body = response.json()
    if provider == PROVIDER_RH:
        code = body.get("code")
        if code not in (None, 0, "0"):
            raise RuntimeError(f"RunningHub upload failed: {body}")
        return rh_upload_url_from_body(body)
    return body.get("data", {}).get("url") or body.get("url")


def collect_reference_urls(
    requests_mod: Any,
    api_key: str,
    product_dir: Path,
    max_refs: int,
    provider: str,
) -> tuple[list[str], list[Path]]:
    if max_refs <= 0:
        return [], []
    images = [
        p
        for p in sorted(product_dir.rglob("*"), key=lambda item: str(item.relative_to(product_dir)).lower())
        if p.is_file()
        and p.suffix.lower() in IMAGE_EXTENSIONS
        and not is_hard_excluded_reference(p, product_dir)
        and not is_forbidden_sku_root_model_reference(p, product_dir)
        and not p.name.lower().startswith("_reference_contact_sheet")
    ]
    urls: list[str] = []
    uploaded_paths: list[Path] = []
    for image_path in images[:max_refs]:
        try:
            url = upload_image(requests_mod, api_key, image_path, provider)
            if url:
                urls.append(url)
                uploaded_paths.append(image_path)
                print(f"  Uploaded reference: {image_path.name}")
        except Exception as exc:
            print(f"  Upload failed, skipped: {image_path.name}: {exc}")
    return urls, uploaded_paths


def is_hard_excluded_reference(path: Path, product_dir: Path) -> bool:
    try:
        parts = path.resolve().relative_to(product_dir.resolve()).parts[:-1]
    except ValueError:
        return True
    for part in parts:
        folded = part.casefold().strip()
        if folded.startswith(SKIP_DIR_PREFIXES):
            return True
        if folded in {name.casefold() for name in HARD_EXCLUDED_DIR_NAMES}:
            return True
        if any(term in folded for term in ("弃用", "过程文件", "生成结果", "输出结果", "备份", "backup")):
            return True
    return False


def is_forbidden_sku_root_model_reference(path: Path, product_dir: Path) -> bool:
    try:
        relative = path.resolve().relative_to(product_dir.resolve())
    except ValueError:
        return False
    if len(relative.parts) != 1:
        return False
    tags_path = product_dir / "_aplus_creative_work" / "aigc_model_view_tags.json"
    try:
        tags = json.loads(tags_path.read_text(encoding="utf-8-sig")) if tags_path.exists() else {}
    except Exception:
        tags = {}
    rel_key = str(relative).replace("\\", "/")
    tag = tags.get(rel_key) or tags.get(str(relative))
    if not isinstance(tag, dict):
        return False
    subject = str(tag.get("subject_type") or "").casefold().replace("-", "_")
    return tag.get("contains_person") is True or subject == "model_person"


def validate_current_sku_reference(product_dir: Path, image_path: Path) -> Path:
    resolved = image_path.expanduser().resolve()
    try:
        resolved.relative_to(product_dir.resolve())
    except ValueError as exc:
        raise RuntimeError(f"Module reference is outside current SKU: {resolved}") from exc
    if not resolved.is_file() or resolved.suffix.lower() not in IMAGE_EXTENSIONS:
        raise RuntimeError(f"Module reference does not exist as an image: {resolved}")
    if is_hard_excluded_reference(resolved, product_dir):
        raise RuntimeError(f"Module reference is in a hard-excluded directory: {resolved}")
    if is_forbidden_sku_root_model_reference(resolved, product_dir):
        raise RuntimeError(f"Root-level SKU model/person image is forbidden as an API reference: {resolved}")
    return resolved


def load_module_reference_map(product_dir: Path) -> dict[str, list[Path]]:
    path = product_dir / "_aplus_creative_work" / "module_reference_images.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    mapping: dict[str, list[Path]] = {}
    for module_name, image_paths in data.items():
        if not isinstance(image_paths, list):
            raise RuntimeError(f"Invalid module reference list for {module_name}")
        mapping[str(module_name)] = [
            validate_current_sku_reference(product_dir, Path(str(item))) for item in image_paths
        ]
    return mapping


def load_reference_role_map(product_dir: Path) -> dict[str, str]:
    path = product_dir / "_aplus_creative_work" / "reference_image_roles.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key).replace("\\", "/").casefold(): str(value).casefold() for key, value in data.items()}


def reference_role(product_dir: Path, image_path: Path, role_map: dict[str, str]) -> str:
    try:
        key = str(image_path.resolve().relative_to(product_dir.resolve())).replace("\\", "/").casefold()
    except ValueError:
        return ""
    return role_map.get(key, "")


def has_model_reference_images(product_dir: Path, image_paths: list[Path], role_map: dict[str, str]) -> bool:
    model_roles = {"model_front", "model_side", "model_back", "model_unknown"}
    return any(reference_role(product_dir, image_path, role_map) in model_roles for image_path in image_paths)


def is_back_view_model_reference(product_dir: Path, image_path: Path, role_map: dict[str, str]) -> bool:
    return reference_role(product_dir, image_path, role_map) == "model_back"


def all_model_reference_paths(product_dir: Path, role_map: dict[str, str]) -> list[Path]:
    paths: list[Path] = []
    for path in sorted(product_dir.rglob("*"), key=lambda item: str(item).casefold()):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        try:
            relative_parts = path.relative_to(product_dir).parts
        except ValueError:
            relative_parts = path.parts
        if is_hard_excluded_reference(path, product_dir):
            continue
        if is_forbidden_sku_root_model_reference(path, product_dir):
            continue
        if reference_role(product_dir, path, role_map) in {"model_front", "model_side", "model_back", "model_unknown"}:
            paths.append(path)
    return unique_paths(paths)


def enforce_no_single_back_view_model_reference(
    product_dir: Path,
    image_paths: list[Path],
    role_map: dict[str, str],
) -> list[Path]:
    model_roles = {"model_front", "model_side", "model_back", "model_unknown"}
    model_paths = [
        path
        for path in image_paths
        if reference_role(product_dir, path, role_map) in model_roles
    ]
    if len(model_paths) != 1 or not is_back_view_model_reference(product_dir, model_paths[0], role_map):
        return image_paths

    existing = {str(path.resolve()).casefold() for path in image_paths}
    candidates = [path for path in all_model_reference_paths(product_dir, role_map) if str(path.resolve()).casefold() not in existing]
    companion = next((path for path in candidates if not is_back_view_model_reference(product_dir, path, role_map)), None)
    companion = companion or (candidates[0] if candidates else None)
    if companion:
        print(f"  Back-view model reference cannot be used alone; added companion model reference: {display_path(product_dir, companion)}")
        return unique_paths([companion, *image_paths])

    print("  Back-view model reference cannot be used alone; no companion model reference found, so the back-view model reference was removed.")
    back_key = str(model_paths[0].resolve()).casefold()
    return [path for path in image_paths if str(path.resolve()).casefold() != back_key]


def strip_model_reference_notes(prompt: str) -> str:
    prompt = re.sub(
        r"\n?Reference note:\s*\n-?\s*Model reference images are attached for this module\.[^\n]*(?:\n[^\n]*)?",
        "\n",
        prompt,
        flags=re.IGNORECASE,
    )
    prompt = re.sub(
        r"\n?Reference note:\s*\nUse the attached model reference images[^\n]*",
        "\n",
        prompt,
        flags=re.IGNORECASE,
    )
    prompt = re.sub(
        r"\n?Referenzhinweis:\s*\n-?\s*Für dieses Modul sind Model-Referenzbilder angehängt\.[^\n]*(?:\n[^\n]*)?",
        "\n",
        prompt,
        flags=re.IGNORECASE,
    )
    prompt = re.sub(
        r"(?is)\n?Reference note:\s*.*?(?=\n(?:Negative Prompt|Attached Reference Image Map|Logo Reference Requirement|Text / Callouts|Product Accuracy|Visual Direction)\s*:|\Z)",
        "\n",
        prompt,
    )
    prompt = re.sub(r"(?is)\n?##\s*Model Identity Lock\b.*?(?=\n##\s+|\Z)", "\n", prompt)
    risky_terms = (
        "model reference",
        "model reference images",
        "attached model",
        "supplied model",
        "same person",
        "model identity",
        "model_identity",
        "aigc model",
        "face/hair",
        "face shape",
        "hair impression",
        "body type",
        "pose attitude",
        "on-body fit",
        "model styling",
        "model-focused",
        "model wearing",
        "model scene",
        "model scenes",
        "model pose",
        "model cues",
        "model shots",
        "on-body",
        "worn with",
        "poses",
        "female-presenting model",
        "male-presenting model",
        "preserve the same model",
        "match the same person",
    )
    cleaned_lines: list[str] = []
    removed_any = False
    for line in prompt.splitlines():
        lowered = line.casefold()
        if any(term in lowered for term in risky_terms):
            removed_any = True
            continue
        cleaned_lines.append(line)
    prompt = "\n".join(cleaned_lines)
    if removed_any:
        prompt = (
            f"{prompt.rstrip()}\n\n"
            "No-model reference rule:\n"
            "- No model/person reference images are attached for this module. "
            "Do not generate people, faces, bodies, mannequins, or random models; keep the composition product-only unless the attached references explicitly include a person.\n"
        )
    prompt = re.sub(r"\n{3,}", "\n\n", prompt)
    return prompt.strip() + "\n"


def strip_all_reference_image_notes(prompt: str) -> str:
    prompt = strip_model_reference_notes(prompt)
    prompt = re.sub(
        r"(?is)\n?Logo Reference Requirement:\s*.*?(?=\n(?:Negative Prompt|Attached Reference Image Map|Text / Callouts|Product Accuracy|Visual Direction|No reference images rule)\s*:|\Z)",
        "\n",
        prompt,
    )
    prompt = re.sub(
        r"(?is)\n?LOGO-Referenz:\s*.*?(?=\n(?:Negative Prompt|Attached Reference Image Map|Text / Callouts|Produktgenauigkeit|Visuelle Richtung|Keine Referenzbilder-Regel)\s*:|\Z)",
        "\n",
        prompt,
    )
    prompt = re.sub(
        r"(?is)\n?Attached Reference Image Map:\s*.*?(?=\n(?:Negative Prompt|No reference images rule|No-model reference rule|No LOGO rule|Keine Referenzbilder-Regel)\s*:|\Z)",
        "\n",
        prompt,
    )
    replacements = {
        r"\bthe attached product reference images\b": "the written product details in this prompt",
        r"\battached product reference images\b": "written product details in this prompt",
        r"\battached reference images\b": "the written prompt",
        r"\battached references\b": "the written prompt",
        r"\bsupplied references\b": "the written product details in this prompt",
        r"\bsupplied reference images\b": "the written product details in this prompt",
        r"\bimage references\b": "the written prompt",
        r"\bangehängten Produktreferenzen\b": "Produktinformationen in diesem Prompt",
        r"\bangehängten Referenzen\b": "schriftlichen Prompt",
    }
    for source, target in replacements.items():
        prompt = re.sub(source, target, prompt, flags=re.IGNORECASE)
    if "no reference images rule" not in prompt.casefold() and "keine referenzbilder-regel" not in prompt.casefold():
        prompt = (
            f"{prompt.rstrip()}\n\n"
            "No reference images rule:\n"
            "- No reference images are attached for this module. Build the image from this written prompt only.\n"
        )
    prompt = re.sub(r"\n{3,}", "\n\n", prompt)
    return prompt.strip() + "\n"


def normalize_brand_name(value: str) -> str:
    return re.sub(r"[\s_\-]+", "", value.strip().casefold())


EXCEL_EXTENSIONS = {".xlsx", ".xlsm", ".xltx", ".xltm"}


def first_existing_excel(product_dir: Path) -> Path | None:
    exact = product_dir / "1-产品属性表.xlsx"
    if exact.exists():
        return exact
    candidates = sorted(
        [
            path
            for path in product_dir.iterdir()
            if path.is_file()
            and path.suffix.lower() in EXCEL_EXTENSIONS
            and not path.name.startswith("~$")
        ],
        key=lambda item: item.name.casefold(),
    )
    return candidates[0] if candidates else None


def read_brand_from_excel(product_dir: Path) -> str | None:
    excel_path = first_existing_excel(product_dir)
    if not excel_path:
        return None
    workbook = None
    try:
        from openpyxl import load_workbook
    except ImportError:
        print("  openpyxl is not installed; brand LOGO lookup by Excel brand skipped.")
        return None
    try:
        workbook = load_workbook(excel_path, data_only=True, read_only=True)
        sheet = workbook.active
        brand_labels = {"brand", "品牌", "品牌名", "品牌名称"}
        for row in sheet.iter_rows(values_only=True):
            cells = ["" if value is None else str(value).strip() for value in row]
            for index, cell in enumerate(cells):
                if cell.strip().casefold() in brand_labels and index + 1 < len(cells) and cells[index + 1].strip():
                    return cells[index + 1].strip()
        for row in sheet.iter_rows(values_only=True):
            if len(row) >= 2 and row[0] is not None and row[1] is not None:
                key = str(row[0]).strip()
                if "品牌" in key or key.casefold() == "brand":
                    return str(row[1]).strip()
    except Exception as exc:
        print(f"  Brand read from Excel failed, LOGO fallback will be used: {exc}")
    finally:
        try:
            if workbook:
                workbook.close()
        except Exception:
            pass
    return None


def sibling_brand_logo_references(product_dir: Path) -> list[Path]:
    brand = read_brand_from_excel(product_dir)
    logo_dir = product_dir.parent / "LOGO"
    if not brand or not logo_dir.exists():
        return []
    exact_matches: list[Path] = []
    normalized_matches: list[Path] = []
    wanted = brand.casefold()
    normalized_wanted = normalize_brand_name(brand)
    for path in sorted(logo_dir.iterdir(), key=lambda item: item.name.casefold()):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        if path.stem.casefold() == wanted:
            exact_matches.append(path)
        elif normalize_brand_name(path.stem) == normalized_wanted:
            normalized_matches.append(path)
    matches = exact_matches or normalized_matches
    if matches:
        print(f"  Brand LOGO matched from sibling LOGO folder: {brand} -> {', '.join(path.name for path in matches)}")
        return [copy_logo_to_product_folder(product_dir, matches[0])]
    else:
        print(f"  Brand LOGO not found in sibling LOGO folder for brand: {brand}")
    return []


def copy_logo_to_product_folder(product_dir: Path, source_logo: Path) -> Path:
    destination = product_dir / f"LOGO{source_logo.suffix.lower()}"
    try:
        if source_logo.resolve() != destination.resolve():
            shutil.copy2(source_logo, destination)
            print(f"  Copied brand LOGO into product folder: {destination.name}")
    except Exception as exc:
        print(f"  Failed to copy brand LOGO into product folder, using source LOGO directly: {exc}")
        return source_logo
    return destination


def unique_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        key = str(path).casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def logo_references(product_dir: Path) -> list[Path]:
    sibling_logos = sibling_brand_logo_references(product_dir)
    if sibling_logos:
        return sibling_logos
    logos: list[Path] = []
    for path in sorted(product_dir.rglob("*"), key=lambda item: str(item.relative_to(product_dir)).lower()):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS and "logo" in path.stem.lower():
            logos.append(path)
    return logos


def prompt_needs_logo(prompt_path: Path) -> bool:
    text = read_text(prompt_path)
    if prompt_disables_logo_text(text):
        return False
    lowered = text.casefold()
    if "no logo rule" in lowered or "keine logo-regel" in lowered:
        return False
    if section_index_from_prompt(prompt_path) == 1:
        return True
    positive_logo_patterns = (
        r"\b(use|show|render|place|add|include|display|follow|match)\s+(the\s+)?(attached\s+)?(product\s+|brand\s+)?(logo|wordmark|brand\s+mark)\b",
        r"\b(logo|wordmark|brand\s+mark)\s+(reference|required|needed|exposure|placement)\b",
        r"\bsection\s*1\s+logo\s+instruction\b",
        r"\blogo-referenz\s+(verwenden|nutzen|folgen|erforderlich)\b",
    )
    if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in positive_logo_patterns):
        return True
    return False
    text = text.casefold()
    logo_terms = (
        "logo",
        "brand mark",
        "brandmark",
        "brand badge",
        "wordmark",
        "品牌logo",
        "品牌标识",
        "品牌标志",
        "标识",
        "商标",
    )
    return any(term in text for term in logo_terms)


def display_path(product_dir: Path, image_path: Path) -> str:
    try:
        return str(image_path.relative_to(product_dir))
    except ValueError:
        try:
            return str(image_path.relative_to(product_dir.parent))
        except ValueError:
            return str(image_path)


def print_module_reference_plan(
    product_dir: Path,
    prompt_path: Path,
    image_paths: list[Path],
    shared_reference_count: int,
) -> None:
    if image_paths:
        print(f"  Reference images for {prompt_path.name}:")
        for index, image_path in enumerate(image_paths, 1):
            print(f"    {index}. {display_path(product_dir, image_path)}")
    elif shared_reference_count:
        print(f"  Reference images for {prompt_path.name}: shared uploaded product references ({shared_reference_count} images).")
    else:
        print(f"  Reference images for {prompt_path.name}: none")


def write_module_reference_upload_log(product_dir: Path, data: dict[str, Any]) -> None:
    path = product_dir / "_aplus_creative_work" / "module_reference_upload_log.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def stitch_long_image(product_dir: Path, target: tuple[int, int]) -> Path | None:
    try:
        from PIL import Image
    except ImportError:
        print("  Pillow is not installed; long image stitching skipped.")
        return None
    out_dir = product_dir / "_aplus_creative_work" / "generated_split"
    files = sorted(out_dir.glob(f"section-*-{target[0]}x{target[1]}.png"), key=section_index_from_prompt)
    if not files:
        return None
    canvas = Image.new("RGB", (target[0], target[1] * len(files)), "white")
    y = 0
    opened = []
    try:
        for path in files:
            img = Image.open(path).convert("RGB")
            opened.append(img)
            if img.size != target:
                scale = max(target[0] / img.width, target[1] / img.height)
                resized = img.resize((round(img.width * scale), round(img.height * scale)), Image.Resampling.LANCZOS)
                left = (resized.width - target[0]) // 2
                top = (resized.height - target[1]) // 2
                img = resized.crop((left, top, left + target[0], top + target[1]))
                opened.append(img)
            canvas.paste(img, (0, y))
            y += target[1]
        long_path = product_dir / "_aplus_creative_work" / f"{product_dir.name}_Aplus_Long_{target[0]}x{target[1] * len(files)}.png"
        split_copy = out_dir / f"{product_dir.name}_Aplus_Long_{target[0]}x{target[1] * len(files)}.png"
        canvas.save(long_path)
        canvas.save(split_copy)
        print(f"  Stitched long image: {long_path}")
        root_output_dir = product_dir.parent / "输出结果"
        try:
            root_output_dir.mkdir(parents=True, exist_ok=True)
            root_copy = root_output_dir / long_path.name
            shutil.copy2(long_path, root_copy)
            print(f"  Copied long image to root output folder: {root_copy}")
        except Exception as exc:  # noqa: BLE001 - stitching should still succeed even if copy fails
            print(f"  Failed to copy long image to root output folder: {exc}")
        return long_path
    finally:
        for img in opened:
            img.close()


def upload_extra_references(
    requests_mod: Any,
    api_key: str,
    image_paths: list[Path],
    cache: dict[str, str],
    provider: str,
) -> list[str]:
    urls: list[str] = []
    for image_path in image_paths:
        key = str(image_path)
        if key in cache:
            urls.append(cache[key])
            continue
        if not image_path.exists():
            print(f"  Extra module reference missing, skipped: {image_path}")
            continue
        try:
            url = upload_image(requests_mod, api_key, image_path, provider)
            if url:
                cache[key] = url
                urls.append(url)
                print(f"  Uploaded module reference: {image_path.name}")
        except Exception as exc:
            print(f"  Extra module reference upload failed, skipped: {image_path.name}: {exc}")
    return urls


def poll_generation(
    requests_mod: Any,
    api_key: str,
    task_id: str,
    timeout_seconds: int,
    queued_timeout_seconds: int,
    progress_callback: Any | None = None,
) -> str:
    poll_url = f"{GENERATE_URL}/{task_id}"
    start = time.time()
    queued_start: float | None = None
    while time.time() - start < timeout_seconds:
        response = request_with_retry(
            f"poll {task_id}",
            lambda: requests_mod.get(poll_url, headers={"Authorization": api_key}, timeout=30),
            backoff=[5, 10, 20],
        )
        body = response.json()
        status = body.get("status")
        if progress_callback:
            progress_callback(str(status or "unknown"), body)
        if status == "completed":
            result_url = body.get("url") or body.get("result", {}).get("data", [{}])[0].get("url")
            if result_url:
                return result_url
            raise RuntimeError(f"Completed task did not return an image URL: {body}")
        if status == "failed":
            raise RuntimeError(f"Generation failed: {body}")
        progress = body.get("progress", 0)
        if status == "queued" and progress == 0:
            queued_start = queued_start or time.time()
            if time.time() - queued_start >= queued_timeout_seconds:
                raise TimeoutError(
                    f"Task {task_id} stayed queued at 0% for {queued_timeout_seconds}s"
                )
        else:
            queued_start = None
        print(f"    polling {task_id}: {status} {progress}%")
        time.sleep(5)
    raise TimeoutError(f"Timed out polling task {task_id}")


def rh_result_url(body: dict[str, Any]) -> str | None:
    results = body.get("results")
    if isinstance(results, list):
        for item in results:
            if isinstance(item, dict):
                url = item.get("url") or item.get("download_url") or item.get("fileUrl")
                if url:
                    return url
    data = body.get("data")
    if isinstance(data, dict):
        nested_results = data.get("results")
        if isinstance(nested_results, list):
            for item in nested_results:
                if isinstance(item, dict):
                    url = item.get("url") or item.get("download_url") or item.get("fileUrl")
                    if url:
                        return url
        return data.get("url") or data.get("download_url") or data.get("fileUrl")
    return body.get("url") or body.get("download_url")


def poll_rh_generation(
    requests_mod: Any,
    api_key: str,
    task_id: str,
    timeout_seconds: int,
    queued_timeout_seconds: int,
    progress_callback: Any | None = None,
) -> tuple[str, dict[str, Any]]:
    start = time.time()
    queued_start: float | None = None
    last_body: dict[str, Any] = {}
    while time.time() - start < timeout_seconds:
        response = request_with_retry(
            f"poll RunningHub {task_id}",
            lambda: requests_mod.post(RH_QUERY_URL, json={"taskId": task_id}, headers={"Authorization": api_key}, timeout=30),
            backoff=[5, 10, 20],
        )
        body = response.json()
        last_body = body
        data = body.get("data")
        data_status = data.get("status") if isinstance(data, dict) else None
        status = str(body.get("status") or data_status or "").upper()
        if progress_callback:
            progress_callback(status or "UNKNOWN", body)
        if status == "SUCCESS":
            result_url = rh_result_url(body)
            if result_url:
                return result_url, body
            raise RuntimeError(f"RunningHub SUCCESS did not return an image URL: {body}")
        if status == "FAILED":
            raise RuntimeError(f"RunningHub generation failed: {body}")
        if status == "QUEUED":
            queued_start = queued_start or time.time()
            if time.time() - queued_start >= queued_timeout_seconds:
                raise TimeoutError(f"RunningHub task {task_id} stayed QUEUED for {queued_timeout_seconds}s")
        else:
            queued_start = None
        print(f"    polling RunningHub {task_id}: {status or 'UNKNOWN'}")
        time.sleep(5)
    raise TimeoutError(f"Timed out polling RunningHub task {task_id}: {last_body}")


def postprocess_to_size(source_bytes: bytes, raw_path: Path, final_path: Path, target: tuple[int, int]) -> None:
    from PIL import Image

    final_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(source_bytes)
    img = Image.open(io.BytesIO(source_bytes)).convert("RGB")
    scale = max(target[0] / img.width, target[1] / img.height)
    resized = img.resize((round(img.width * scale), round(img.height * scale)), Image.Resampling.LANCZOS)
    left = (resized.width - target[0]) // 2
    top = (resized.height - target[1]) // 2
    resized.crop((left, top, left + target[0], top + target[1])).save(final_path)


def append_failure(product_dir: Path, module_name: str, reason: str, retry_count: int) -> None:
    failure_path = product_dir / "_aplus_creative_work" / "generation_failures.md"
    with failure_path.open("a", encoding="utf-8-sig") as handle:
        handle.write(f"\n## {datetime.now().isoformat(timespec='seconds')}\n")
        handle.write(f"- product_id: {product_dir.name}\n")
        handle.write(f"- module: {module_name}\n")
        handle.write(f"- failure_reason: {reason}\n")
        handle.write(f"- retry_count: {retry_count}\n")
        handle.write("- method: GPT API provider\n")
        handle.write("- action: skipped and continued to next module\n")


def append_api_event(product_dir: Path, module_name: str, event: dict[str, Any]) -> None:
    log_path = product_dir / "_aplus_creative_work" / "module_generation_api_log.jsonl"
    payload = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "product_id": product_dir.name,
        "module": module_name,
        **event,
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def write_api_submitted_prompt(product_dir: Path, prompt_path: Path, prompt: str) -> Path:
    out_dir = product_dir / "_aplus_creative_work" / "api_submitted_prompts"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / prompt_path.name
    out_path.write_text(prompt.strip() + "\n", encoding="utf-8-sig")
    return out_path


def backup_existing_module_outputs(
    product_dir: Path,
    prompt_path: Path,
    target: tuple[int, int],
) -> Path | None:
    """Preserve a rejected/QA-failed result before an explicit overwrite."""
    work_dir = product_dir / "_aplus_creative_work"
    split_dir = work_dir / "generated_split"
    candidates = [
        split_dir / f"{prompt_path.stem}-{target[0]}x{target[1]}.png",
        split_dir / f"{prompt_path.stem}-raw.png",
    ]
    long_pattern = f"{product_dir.name}_Aplus_Long_{target[0]}x*.png"
    candidates.extend(work_dir.glob(long_pattern))
    candidates.extend(split_dir.glob(long_pattern))
    candidates.extend((product_dir.parent / "\u8f93\u51fa\u7ed3\u679c").glob(long_pattern))
    existing = [path for path in candidates if path.exists() and path.is_file()]
    if not existing:
        return None

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_dir = work_dir / "generation_result_backups" / f"{stamp}_{prompt_path.stem}"
    backup_dir.mkdir(parents=True, exist_ok=False)
    manifest_lines = [
        f"product_id: {product_dir.name}",
        f"module: {prompt_path.name}",
        f"backed_up_at: {now_iso()}",
        "files:",
    ]
    for source in unique_paths(existing):
        try:
            relative = source.relative_to(product_dir.parent)
        except ValueError:
            relative = Path(source.name)
        destination = backup_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        manifest_lines.append(f"- {source}")
    (backup_dir / "backup_manifest.txt").write_text(
        "\n".join(manifest_lines) + "\n",
        encoding="utf-8-sig",
    )
    for active_output in candidates[:2]:
        if active_output.exists():
            active_output.unlink()
    append_api_event(
        product_dir,
        prompt_path.name,
        {
            "event": "backup_before_overwrite",
            "backup_dir": str(backup_dir),
            "file_count": len(existing),
        },
    )
    update_module_state(
        product_dir,
        prompt_path.name,
        status="backed_up_before_overwrite",
        backup_dir=str(backup_dir),
        provider_task_id=None,
        result_url=None,
    )
    print(f"  Existing QA result backed up before overwrite: {backup_dir}")
    return backup_dir


def strip_text_callouts(prompt: str) -> str:
    """Backward-compatible no-op: human-authored Text / Callouts must be preserved."""
    return prompt.strip()


def strip_none_callouts(prompt: str) -> str:
    """Backward-compatible alias that preserves the required manual field."""
    return strip_text_callouts(prompt)


def strip_attached_reference_map(prompt: str) -> str:
    """Remove the model-facing filename map; exact paths remain in the upload log."""
    cleaned = re.sub(
        r"(?ims)(?:\r?\n)*^[ \t]*Attached Reference Image Map[ \t]*:[ \t]*(?:\r?\n|\Z).*\Z",
        "",
        prompt,
    )
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def _extract_manual_block(prompt: str, label_pattern: str, canonical_label: str) -> tuple[str, str]:
    heading_pattern = (
        r"Headline|Copy|Visual Direction|Layout execution|Product Accuracy|Produktgenauigkeit|"
        r"Text[ \t]*/[ \t]*Callouts|Reference note|Referenzhinweis|No LOGO rule|Keine LOGO-Regel|"
        r"Logo Reference Requirement|LOGO-Referenz|No reference images rule|Keine Referenzbilder-Regel|"
        r"No-model reference rule|Negative Prompt|Technical seed note"
    )
    pattern = re.compile(
        rf"(?ims)^[ \t]*{label_pattern}[ \t]*:[ \t]*(.*?)(?=^[ \t]*(?:{heading_pattern})[ \t]*:|\Z)"
    )
    matches = list(pattern.finditer(prompt))
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one {canonical_label!r} block, found {len(matches)}")
    body = matches[0].group(1).strip()
    if not body:
        raise ValueError(f"{canonical_label} must contain human-authored content")
    cleaned = f"{prompt[:matches[0].start()]}\n{prompt[matches[0].end():]}"
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip(), f"{canonical_label}:\n{body}"


def normalize_manual_prompt_structure(prompt: str) -> str:
    """Place manual layout and callouts in their canonical semantic positions."""
    if re.search(r"(?im)^\s*Section 3 (?:fashion action|Modeaktion)\s*:", prompt):
        raise ValueError("Section 3 fashion action must be merged into the existing Layout task, not kept as a separate block")
    cleaned, layout_block = _extract_manual_block(prompt, r"Layout execution", "Layout execution")
    cleaned, callouts_block = _extract_manual_block(
        cleaned,
        r"Text[ \t]*/[ \t]*Callouts",
        "Text / Callouts",
    )
    layout_task = re.search(r"(?im)^\s*Layout task\s*:", cleaned)
    product_accuracy = re.search(r"(?im)^\s*Product Accuracy\s*:", cleaned)
    if not layout_task or not product_accuracy or layout_task.start() >= product_accuracy.start():
        raise ValueError("Layout task must appear before Product Accuracy")
    cleaned = (
        f"{cleaned[:product_accuracy.start()].rstrip()}\n\n{layout_block}\n\n"
        f"{cleaned[product_accuracy.start():].lstrip()}"
    )
    product_accuracy = re.search(r"(?im)^\s*Product Accuracy\s*:", cleaned)
    assert product_accuracy is not None
    next_heading = re.search(
        r"(?im)^\s*(?:Reference note|Referenzhinweis|No LOGO rule|Keine LOGO-Regel|"
        r"Logo Reference Requirement|LOGO-Referenz|No reference images rule|Keine Referenzbilder-Regel|"
        r"No-model reference rule|Negative Prompt|Technical seed note)\s*:",
        cleaned[product_accuracy.end():],
    )
    insert_at = len(cleaned) if not next_heading else product_accuracy.end() + next_heading.start()
    cleaned = (
        f"{cleaned[:insert_at].rstrip()}\n\n{callouts_block}\n\n"
        f"{cleaned[insert_at:].lstrip()}"
    )
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def move_manual_directives_to_prompt_end(prompt: str) -> str:
    """Backward-compatible alias for the canonical manual-field normalizer."""
    return normalize_manual_prompt_structure(prompt)


def no_reference_seed_image(product_dir: Path, target: tuple[int, int]) -> Path:
    """Create a blank technical seed for RH's non-empty imageUrls requirement."""
    seed_dir = product_dir / "_aplus_creative_work" / "technical_seed"
    seed_dir.mkdir(parents=True, exist_ok=True)
    seed_path = seed_dir / f"no_reference_seed_{target[0]}x{target[1]}.png"
    if seed_path.exists():
        return seed_path
    try:
        from PIL import Image

        Image.new("RGB", target, (242, 242, 240)).save(seed_path)
    except Exception:
        # Minimal fallback: create a tiny valid PNG from Pillow is preferred, but
        # if image tooling is unavailable, fail clearly at upload/open time.
        seed_path.write_bytes(b"")
    return seed_path


def rh_endpoint_for_request(use_text_to_image: bool) -> str:
    return "text-to-image" if use_text_to_image else "image-to-image"


def generate_one_module(
    requests_mod: Any,
    api_key: str,
    provider: str,
    prompt_path: Path,
    product_dir: Path,
    reference_urls: list[str],
    size: str,
    resolution: str,
    model: str,
    quality: str,
    target: tuple[int, int],
    poll_timeout: int,
    queued_timeout: int,
    overwrite: bool,
    extra_reference_urls: list[str] | None = None,
    reference_prompt_note: str = "",
    has_model_references: bool = True,
) -> bool:
    # Kept for backward-compatible callers only. Filename maps are never added to prompts.
    del reference_prompt_note
    out_dir = product_dir / "_aplus_creative_work" / "generated_split"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = prompt_path.stem
    final_path = out_dir / f"{stem}-{target[0]}x{target[1]}.png"
    raw_path = out_dir / f"{stem}-raw.png"
    if final_path.exists() and not overwrite:
        print(f"  Exists, skipped: {final_path.name}")
        update_module_state(
            product_dir,
            prompt_path.name,
            status="skipped_existing",
            final_path=str(final_path),
            completed_at=now_iso(),
        )
        return True
    if overwrite:
        backup_existing_module_outputs(product_dir, prompt_path, target)

    prompt = read_text(prompt_path)
    references_disabled_by_prompt = prompt_disables_reference_images_text(prompt)
    use_rh_text_to_image = bool(provider == PROVIDER_RH and references_disabled_by_prompt)
    logo_disabled_by_prompt = prompt_disables_logo_text(prompt)
    if references_disabled_by_prompt:
        reference_urls = []
        extra_reference_urls = []
        has_model_references = False
        prompt = strip_all_reference_image_notes(prompt)
        if provider == PROVIDER_RH and not use_rh_text_to_image:
            seed_path = no_reference_seed_image(product_dir, target)
            seed_url = upload_image(requests_mod, api_key, seed_path, provider)
            if seed_url:
                reference_urls = [seed_url]
                prompt = (
                    f"{prompt.rstrip()}\n\n"
                    "Technical seed note:\n"
                    "- Reference image #1 is a blank technical seed required only by the RunningHub image-to-image API. "
                    "Do not treat it as a product, model, styling, color, composition, LOGO, or layout reference. "
                    "Follow the written prompt only.\n"
                )
    if logo_disabled_by_prompt:
        prompt = strip_logo_reference_notes(prompt)
    if not has_model_references:
        prompt = strip_model_reference_notes(prompt)
    if logo_disabled_by_prompt:
        prompt = strip_logo_reference_notes(prompt)
    prompt = sanitize_overbroad_german_logo_rule(prompt)
    prompt = strip_attached_reference_map(prompt)
    prompt = normalize_manual_prompt_structure(prompt)
    submitted_prompt_path = write_api_submitted_prompt(product_dir, prompt_path, prompt)
    review_path = build_review(product_dir)
    update_module_state(
        product_dir,
        prompt_path.name,
        status="prompt_ready",
        provider=provider,
        submitted_prompt_path=str(submitted_prompt_path),
        prompt_review_path=str(review_path) if review_path else None,
    )

    merged_urls = list(reference_urls)
    if extra_reference_urls:
        merged_urls.extend(extra_reference_urls)
    if provider == PROVIDER_RH and len(merged_urls) > 10:
        print(f"  GPT-RH supports at most 10 reference images; using first 10 of {len(merged_urls)}.")
        merged_urls = merged_urls[:10]

    def progress_callback(task_id: str, provider_status: str, body: dict[str, Any]) -> None:
        update_module_state(
            product_dir,
            prompt_path.name,
            status="polling",
            provider=provider,
            provider_task_id=task_id,
            last_provider_status=provider_status,
            last_provider_response=body,
        )

    def poll_existing_task(task_id: str) -> tuple[str, dict[str, Any] | None]:
        if provider == PROVIDER_RH:
            result_url, poll_body = poll_rh_generation(
                requests_mod,
                api_key,
                task_id,
                poll_timeout,
                queued_timeout,
                lambda status, body: progress_callback(task_id, status, body),
            )
            return result_url, poll_body
        result_url = poll_generation(
            requests_mod,
            api_key,
            task_id,
            poll_timeout,
            queued_timeout,
            lambda status, body: progress_callback(task_id, status, body),
        )
        return result_url, None

    def download_result(task_id: str, result_url: str) -> bool:
        update_module_state(
            product_dir,
            prompt_path.name,
            status="downloading",
            provider=provider,
            provider_task_id=task_id,
            result_url=result_url,
        )
        image_response = request_with_retry(
            f"download result {prompt_path.name}",
            lambda: requests_mod.get(result_url, timeout=120),
            backoff=[5, 10, 20],
        )
        postprocess_to_size(image_response.content, raw_path, final_path, target)
        update_module_state(
            product_dir,
            prompt_path.name,
            status="completed",
            provider=provider,
            provider_task_id=task_id,
            result_url=result_url,
            raw_path=str(raw_path),
            final_path=str(final_path),
            completed_at=now_iso(),
        )
        append_api_event(
            product_dir,
            prompt_path.name,
            {
                "event": "download_and_save",
                "provider": provider,
                "task_id": task_id,
                "download_status": getattr(image_response, "status_code", None),
                "raw_path": str(raw_path),
                "final_path": str(final_path),
            },
        )
        print(f"  Saved: {final_path}")
        return True

    existing_state = module_state(product_dir, prompt_path.name)
    existing_task_id = None if overwrite else existing_state.get("provider_task_id")
    existing_result_url = None if overwrite else existing_state.get("result_url")
    if existing_task_id:
        task_id = str(existing_task_id)
        print(f"  Existing provider_task_id found; query-only resume: {task_id}")
        update_module_state(
            product_dir,
            prompt_path.name,
            status="resuming_query_only",
            provider=provider,
            provider_task_id=task_id,
            resume_mode="query_only",
        )
        try:
            if existing_result_url:
                result_url = str(existing_result_url)
                poll_body = None
            else:
                result_url, poll_body = poll_existing_task(task_id)
            update_module_state(
                product_dir,
                prompt_path.name,
                status="provider_succeeded",
                provider=provider,
                provider_task_id=task_id,
                result_url=result_url,
                last_provider_response=poll_body,
            )
            append_api_event(
                product_dir,
                prompt_path.name,
                {
                    "event": "generation_completed",
                    "provider": provider,
                    "task_id": task_id,
                    "result_url": result_url,
                    "resumed_query_only": True,
                    "response_body": poll_body,
                },
            )
            return download_result(task_id, result_url)
        except Exception as exc:
            reason = str(exc)
            update_module_state(
                product_dir,
                prompt_path.name,
                status="query_resume_error",
                provider=provider,
                provider_task_id=task_id,
                error=reason,
                resume_mode="query_only",
            )
            append_api_event(
                product_dir,
                prompt_path.name,
                {
                    "event": "error",
                    "provider": provider,
                    "task_id": task_id,
                    "error": reason,
                    "resumed_query_only": True,
                    "resubmitted": False,
                },
            )
            append_failure(product_dir, prompt_path.name, reason, 0)
            return False

    last_error = ""
    for attempt in range(1, len(DEFAULT_BACKOFF) + 2):
        task_id: str | None = None
        try:
            update_module_state(
                product_dir,
                prompt_path.name,
                status="submitting",
                provider=provider,
                provider_task_id=None,
                submission_attempt=attempt,
                request_reference_count=len(merged_urls),
            )
            if provider == PROVIDER_RH:
                use_rh_text_to_image_for_request = use_rh_text_to_image or not merged_urls
                payload = {
                    "prompt": prompt,
                    "aspectRatio": size.lower(),
                    "resolution": resolution.lower(),
                    "quality": quality,
                }
                rh_endpoint = RH_TEXT_TO_IMAGE_URL if use_rh_text_to_image_for_request else RH_GENERATE_URL
                if not use_rh_text_to_image_for_request:
                    payload["imageUrls"] = merged_urls
                response = request_with_retry(
                    f"submit RunningHub generation {prompt_path.name}",
                    lambda: requests_mod.post(rh_endpoint, json=payload, headers={"Authorization": api_key, "Content-Type": "application/json"}, timeout=120),
                    backoff=[5, 10, 20],
                )
            else:
                payload = {
                    "model": model,
                    "prompt": prompt,
                    "size": size,
                    "resolution": resolution,
                    "quality": quality,
                    "response_format": "url",
                }
                if merged_urls:
                    payload["image_urls"] = merged_urls
                response = request_with_retry(
                    f"submit generation {prompt_path.name}",
                    lambda: requests_mod.post(GENERATE_URL, json=payload, headers={"Authorization": api_key}, timeout=60),
                    backoff=[5, 10, 20],
                )
            body = response.json()
            task_value = body.get("taskId") or body.get("id") or body.get("task_id")
            task_id = str(task_value) if task_value else None
            if task_id:
                update_module_state(
                    product_dir,
                    prompt_path.name,
                    status="submitted",
                    provider=provider,
                    provider_task_id=task_id,
                    submitted_at=now_iso(),
                    submission_attempt=attempt,
                    request_reference_count=len(merged_urls),
                    last_provider_response=body,
                    runninghub_endpoint=rh_endpoint_for_request(use_rh_text_to_image_for_request) if provider == PROVIDER_RH else None,
                )
            append_api_event(
                product_dir,
                prompt_path.name,
                {
                    "event": "submit_generation",
                    "provider": provider,
                    "attempt": attempt,
                    "submitted_prompt_path": str(submitted_prompt_path),
                    "task_id": task_id,
                    "response_status": getattr(response, "status_code", None),
                    "response_body": body,
                    "request_reference_count": len(merged_urls),
                    "runninghub_endpoint": rh_endpoint_for_request(use_rh_text_to_image_for_request) if provider == PROVIDER_RH else None,
                    "model": model if provider == PROVIDER_TOAPI else None,
                    "quality": quality,
                },
            )
            if not task_id:
                raise RuntimeError(f"Generation API returned no task id: {body}")
            if provider == PROVIDER_RH and body.get("errorCode"):
                raise RuntimeError(f"RunningHub generation returned error: {body}")
            result_url, poll_body = poll_existing_task(task_id)
            update_module_state(
                product_dir,
                prompt_path.name,
                status="provider_succeeded",
                provider=provider,
                provider_task_id=task_id,
                result_url=result_url,
                last_provider_response=poll_body,
            )
            append_api_event(
                product_dir,
                prompt_path.name,
                {
                    "event": "generation_completed",
                    "provider": provider,
                    "task_id": task_id,
                    "result_url": result_url,
                    "response_body": poll_body,
                },
            )
            return download_result(task_id, result_url)
        except Exception as exc:
            last_error = str(exc)
            if task_id:
                update_module_state(
                    product_dir,
                    prompt_path.name,
                    status="provider_task_error",
                    provider=provider,
                    provider_task_id=task_id,
                    error=last_error,
                    resubmission_blocked=True,
                )
                append_api_event(
                    product_dir,
                    prompt_path.name,
                    {
                        "event": "error",
                        "provider": provider,
                        "attempt": attempt,
                        "task_id": task_id,
                        "error": last_error,
                        "resubmitted": False,
                        "resubmission_blocked_by_existing_task_id": True,
                    },
                )
                print(f"  Provider task exists; submission retry blocked: {task_id}: {last_error}")
                append_failure(product_dir, prompt_path.name, last_error, attempt - 1)
                return False
            append_api_event(
                product_dir,
                prompt_path.name,
                {"event": "error", "provider": provider, "attempt": attempt, "error": last_error},
            )
            update_module_state(
                product_dir,
                prompt_path.name,
                status="unsubmitted_error",
                provider=provider,
                provider_task_id=None,
                error=last_error,
                submission_attempt=attempt,
            )
            if attempt <= len(DEFAULT_BACKOFF):
                wait_time = DEFAULT_BACKOFF[attempt - 1]
                print(f"  Attempt {attempt} failed: {last_error}. Retrying in {wait_time}s.")
                time.sleep(wait_time)
            else:
                print(f"  Failed after retries: {prompt_path.name}: {last_error}")
                append_failure(product_dir, prompt_path.name, last_error, len(DEFAULT_BACKOFF))
                return False
    return False


def main() -> int:
    configure_stdout()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Root folder containing product subfolders.")
    parser.add_argument("--template-analysis", help="Optional _aplus_creative_template_analysis.json.")
    parser.add_argument("--provider", choices=[PROVIDER_TOAPI, PROVIDER_RH], default=PROVIDER_TOAPI, help="Image generation provider. GPT-ToAPI is the original provider; GPT-RH uses RunningHub.")
    parser.add_argument("--api-key", help="Optional API key. GPT-ToAPI prefers TOAPIS_API_KEY/OPENAI_API_KEY; GPT-RH prefers RUNNINGHUB_API_KEY.")
    parser.add_argument("--size", default="21:9", help="API aspect ratio, e.g. 21:9.")
    parser.add_argument("--resolution", default="2K", help="API resolution: 1K, 2K, or 4K.")
    parser.add_argument("--model", default="gpt-image-2", help="GPT-ToAPI image model. Default gpt-image-2; e.g. gpt-image-2-high.")
    parser.add_argument("--quality", choices=["low", "medium", "high"], default="medium", help="GPT-RH quality. Default medium.")
    parser.add_argument("--product", required=True, help="Exactly one product folder name. V4 never accepts a whole root or comma-separated products.")
    parser.add_argument("--module", help="Optional comma-separated module prompt filename or stem; regenerate only these modules for output QA.")
    parser.add_argument("--max-reference-images", type=int, default=0, help="Upload up to N product images as image_urls. Default 0.")
    parser.add_argument("--poll-timeout", type=int, default=1800)
    parser.add_argument(
        "--queued-timeout",
        type=int,
        default=60,
        help="Retry a module when an API task stays queued at 0%% for this many seconds.",
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if "," in args.product:
        raise SystemExit("V4 requires exactly one --product value; comma-separated products are forbidden.")

    try:
        import requests
    except ImportError as exc:
        raise SystemExit(f"requests is required for method 2: {exc}") from exc

    env_key = (
        os.environ.get("RUNNINGHUB_API_KEY")
        if args.provider == PROVIDER_RH
        else (os.environ.get("TOAPIS_API_KEY") or os.environ.get("OPENAI_API_KEY"))
    )
    api_key = normalize_api_key(args.api_key or env_key, args.provider)
    root = Path(args.root).expanduser().resolve()
    if not root.exists():
        raise SystemExit(f"Root does not exist: {root}")
    analysis_path = Path(args.template_analysis).expanduser().resolve() if args.template_analysis else root / "_aplus_creative_template_analysis.json"
    target = expected_size(load_analysis(analysis_path))
    product_dirs = product_dirs_from_root(root, args.product)
    if not product_dirs:
        detail = f" matching --product {args.product!r}" if args.product else ""
        raise SystemExit(f"No product module prompts found under: {root}{detail}")

    for product_dir in product_dirs:
        print(f"\nProduct: {product_dir.name}")
        layout_errors = validate_manual_layout_prompts(product_dir)
        if layout_errors:
            update_product_state(
                product_dir,
                status="manual_layout_validation_failed",
                errors=layout_errors,
                worker_pid=os.getpid(),
            )
            raise SystemExit(
                "Manual layout validation failed before API submission:\n- "
                + "\n- ".join(layout_errors)
            )
        update_product_state(
            product_dir,
            status="worker_running",
            worker_pid=os.getpid(),
            provider=args.provider,
            size=args.size,
            resolution=args.resolution,
            quality=args.quality,
            overwrite=args.overwrite,
        )
        prompts = sorted((product_dir / "_aplus_creative_work" / "module_prompts").glob("*.txt"))
        if args.module:
            selected_modules = {item.strip().casefold() for item in args.module.split(",") if item.strip()}
            prompts = [
                prompt
                for prompt in prompts
                if prompt.name.casefold() in selected_modules or prompt.stem.casefold() in selected_modules
            ]
            if not prompts:
                raise SystemExit(f"No module prompts matched --module {args.module!r} for {product_dir.name}")
        if prompts and not args.overwrite:
            out_dir = product_dir / "_aplus_creative_work" / "generated_split"
            expected_files = [out_dir / f"{prompt.stem}-{target[0]}x{target[1]}.png" for prompt in prompts]
            if all(path.exists() for path in expected_files):
                print("  All module images already exist, skipped product.")
                stitch_long_image(product_dir, target)
                update_product_state(
                    product_dir,
                    status="completed",
                    worker_pid=None,
                    completed_at=now_iso(),
                )
                continue

        module_reference_map = load_module_reference_map(product_dir)
        missing_module_mappings = [prompt.name for prompt in prompts if prompt.name not in module_reference_map]
        if missing_module_mappings:
            raise RuntimeError(
                f"{product_dir.name}: fresh module reference map is incomplete: {missing_module_mappings}"
            )
        reference_role_map = load_reference_role_map(product_dir)
        module_reference_cache: dict[str, str] = {}
        module_reference_upload_log: dict[str, Any] = {}
        product_logo_paths: list[Path] | None = None
        module_results: list[bool] = []
        for prompt_path in prompts:
            print(f"- Module: {prompt_path.name}")
            existing_final_path = (
                product_dir
                / "_aplus_creative_work"
                / "generated_split"
                / f"{prompt_path.stem}-{target[0]}x{target[1]}.png"
            )
            if existing_final_path.exists() and not args.overwrite:
                print(f"  Exists, skipped before reference planning: {existing_final_path.name}")
                update_module_state(
                    product_dir,
                    prompt_path.name,
                    status="skipped_existing",
                    final_path=str(existing_final_path),
                    completed_at=now_iso(),
                )
                module_results.append(True)
                continue
            update_module_state(
                product_dir,
                prompt_path.name,
                status="planning_references",
                provider=args.provider,
                worker_pid=os.getpid(),
            )
            module_reference_paths = module_reference_map.get(prompt_path.name, [])
            extra_paths = unique_paths(list(module_reference_paths))
            references_disabled_by_prompt = prompt_disables_reference_images(prompt_path)
            logo_disabled_by_prompt = prompt_disables_logo(prompt_path)
            module_needs_logo = False if references_disabled_by_prompt else prompt_needs_logo(prompt_path)
            if module_needs_logo:
                product_logo_paths = [
                    path for path in module_reference_paths
                    if reference_role(product_dir, path, reference_role_map) == "brand_logo"
                ]
                if product_logo_paths:
                    if section_index_from_prompt(prompt_path) == 1:
                        print("  Section 1 requires LOGO; using matched LOGO references.")
                    else:
                        print("  LOGO requested by prompt; using matched LOGO references.")
                else:
                    print("  LOGO requested by prompt, but the semantic module contract selected no LOGO reference.")
            prompt_reference_urls: list[str] = []
            planned_paths = extra_paths
            if references_disabled_by_prompt:
                module_reference_paths = []
                extra_paths = []
                prompt_reference_urls = []
                planned_paths = []
                print("  Prompt disables reference images; no reference images will be uploaded for this module.")
            if logo_disabled_by_prompt:
                planned_paths = [path for path in planned_paths if not is_logo_path(path)]
                extra_paths = [path for path in extra_paths if not is_logo_path(path)]
                print("  Template/prompt disables LOGO; LOGO references will not be uploaded for this module.")
            original_planned_keys = [str(path.resolve()).casefold() for path in planned_paths]
            planned_paths = enforce_no_single_back_view_model_reference(product_dir, planned_paths, reference_role_map)
            extra_paths = planned_paths
            print_module_reference_plan(product_dir, prompt_path, planned_paths, len(prompt_reference_urls))
            logo_reference_numbers = [
                index
                for index, image_path in enumerate(planned_paths, 1)
                if image_path.name.lower().startswith("logo")
            ]
            if section_index_from_prompt(prompt_path) == 1 and logo_reference_numbers:
                print(f"  Section 1 LOGO reference image number: #{logo_reference_numbers[0]}")
            has_model_references = has_model_reference_images(product_dir, planned_paths, reference_role_map)
            if not has_model_references:
                print("  No model reference image is planned for this module; model-reference prompt notes will be stripped before API submit.")
            module_reference_upload_log[prompt_path.name] = {
                "mode": "no_reference" if references_disabled_by_prompt else "module_specific",
                "reference_images_disabled_by_prompt": references_disabled_by_prompt,
                "runninghub_endpoint": rh_endpoint_for_request(bool(args.provider == PROVIDER_RH and not planned_paths and len(prompt_reference_urls) == 0)) if args.provider == PROVIDER_RH else None,
                "runninghub_blank_technical_seed": False,
                "logo_disabled_by_prompt": logo_disabled_by_prompt,
                "logo_requested_by_prompt": module_needs_logo,
                "logo_reference_numbers": logo_reference_numbers,
                "has_model_reference_images": has_model_references,
                "reference_images": [display_path(product_dir, image_path) for image_path in planned_paths],
                "shared_reference_count": len(prompt_reference_urls),
            }
            write_module_reference_upload_log(product_dir, module_reference_upload_log)
            existing_module_state = module_state(product_dir, prompt_path.name)
            query_only_resume = bool(
                not args.overwrite
                and existing_module_state.get("provider_task_id")
                and not (
                    product_dir
                    / "_aplus_creative_work"
                    / "generated_split"
                    / f"{prompt_path.stem}-{target[0]}x{target[1]}.png"
                ).exists()
            )
            if query_only_resume:
                print(
                    "  Existing provider_task_id detected before uploads; "
                    "skipping all reference uploads and resuming query only."
                )
                extra_reference_urls = []
                prompt_reference_urls = []
            else:
                update_module_state(
                    product_dir,
                    prompt_path.name,
                    status="uploading_references",
                    provider=args.provider,
                    provider_task_id=None,
                )
                extra_reference_urls = upload_extra_references(
                    requests,
                    api_key,
                    extra_paths,
                    module_reference_cache,
                    args.provider,
                )
            if module_reference_paths:
                print("  Module-specific references detected: using mapped references plus prompt-needed LOGO only; shared product/model references skipped.")
            module_results.append(generate_one_module(
                requests,
                api_key,
                args.provider,
                prompt_path,
                product_dir,
                prompt_reference_urls,
                args.size,
                args.resolution,
                args.model,
                args.quality,
                target,
                args.poll_timeout,
                args.queued_timeout,
                args.overwrite,
                extra_reference_urls,
                "",
                has_model_references,
            ))
        write_module_reference_upload_log(product_dir, module_reference_upload_log)
        long_path = stitch_long_image(product_dir, target)
        final_status = "completed" if all(module_results) and long_path else "completed_with_errors"
        update_product_state(
            product_dir,
            status=final_status,
            worker_pid=None,
            completed_at=now_iso(),
            successful_modules=sum(1 for result in module_results if result),
            total_modules=len(module_results),
            stitched_long_image=str(long_path) if long_path else None,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
