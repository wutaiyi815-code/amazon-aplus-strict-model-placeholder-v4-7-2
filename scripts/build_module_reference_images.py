#!/usr/bin/env python
"""Build per-module reference image maps for A+ generation."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
PP_RE = re.compile(r"pp[_\s-]?(\d+)", re.IGNORECASE)
SECTION_RE = re.compile(r"section-0?(\d+)", re.IGNORECASE)
MODEL_IDENTITY_REFERENCE_RE = re.compile(
    r"(?im)^\s*[-*]?\s*model_identity_reference\s*:\s*(.+?)\s*$"
)
SKIP_DIR_PREFIXES = ("_aplus", "_influencer")
HARD_EXCLUDED_DIR_NAMES = {"弃用", "过程文件", "生成结果", "输出结果", "备份", "备份目录"}

ROLE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "no_reference": ("不要上传参考图", "不上传参考图", "无需参考图", "不要发送参考图", "不发送参考图", "不要传参考图", "不传参考图", "no reference images", "without reference images", "do not upload reference images", "do not send reference images", "no image references"),
    "placeholder_blocks": ("占位符", "色块", "等大色块", "等大的色块", "placeholder", "placeholder blocks", "color blocks"),
    "influencer_background": ("不需要生成网红图", "无需生成网红图", "并不需要生成网红图", "不生成网红图", "用于后续替换为网红图", "后续替换为网红图", "背景图", "background only", "text-free background"),
    "influencer": ("网红图", "网红", "达人", "ugc", "influencer", "social proof", "selfie"),
    "hero_model": ("首图", "主图", "开屏", "banner", "hero", "model", "模特", "人物", "上身", "穿着", "lookbook"),
    "fit_silhouette": ("版型", "廓形", "剪裁", "上身效果", "穿着效果", "fit", "silhouette", "oversized", "drop shoulder"),
    "front_back": ("正反面", "正面", "背面", "前后", "front", "back", "front-back"),
    "graphic_detail": ("印花", "图案", "星星", "logo", "标识", "graphic", "print", "artwork", "pattern"),
    "fabric_detail": ("面料", "材质", "质感", "纹理", "fabric", "material", "texture", "jersey"),
    "construction_detail": ("细节", "工艺", "走线", "缝线", "领口", "袖口", "下摆", "detail", "construction", "stitch", "neckline", "hem"),
    "brand_logo": ("品牌", "logo", "wordmark", "标志"),
}

ROLE_NEEDS: dict[str, list[str]] = {
    "no_reference": [],
    "placeholder_blocks": ["product_front", "brand_logo"],
    "influencer_background": ["product_front", "product_detail", "brand_logo"],
    "influencer": ["influencer"],
    "hero_model": ["model_identity"],
    "model_multi_angle": ["model_front", "model_side", "model_back"],
    "fit_silhouette": ["model_front", "model_side", "model_back"],
    "model_flatlay": ["model_identity", "product_front", "product_back", "product_detail"],
    "front_back": ["product_front", "product_back", "product_detail"],
    "graphic_detail": ["product_front", "product_back", "graphic_detail", "product_detail"],
    "fabric_detail": ["product_detail", "fabric_closeup", "construction_detail", "product_front", "product_back"],
    "construction_detail": ["product_detail", "construction_detail", "fabric_closeup", "product_front", "product_back"],
    "brand_logo": ["brand_logo", "product_front", "model_identity"],
    "product_overview": ["model_identity", "product_front", "product_back", "product_detail"],
}


STRUCTURED_IMAGE_DIRS = ("aigc", "素材", "上身")


MODEL_VIEW_TAGS: dict[str, dict[str, Any]] = {}
MODEL_VIEW_TAG_PRODUCT_DIR: Path | None = None
LAYOUT_TASK_RE = re.compile(
    r"(?ims)^\s*Layout task:\s*(.*?)"
    r"(?=^\s*(?:Layout execution|Product Accuracy|Produktgenauigkeit|Text / Callouts|Negative Prompt|"
    r"No LOGO rule|Keine LOGO-Regel|Reference note|Attached Reference Image Map)\s*:|\Z)"
)
LEGACY_SECTION3_ACTION_MARKERS = (
    "Section 3 fashion action:",
    "Section 3 Modeaktion:",
    "Section 3 action adjustment:",
    "Section 3 Aktionsanpassung:",
)


def read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def load_model_view_tags(product_dir: Path) -> dict[str, dict[str, Any]]:
    path = product_dir / "_aplus_creative_work" / "aigc_model_view_tags.json"
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    tags: dict[str, dict[str, Any]] = {}
    for key, value in raw.items():
        if not isinstance(value, dict):
            continue
        tag = {
            "view": str(value.get("view") or "unknown").casefold().replace("-", "_"),
            "framing": str(value.get("framing") or "unknown").casefold().replace("-", "_"),
            "usable_for_identity": bool(value.get("usable_for_identity", True)),
            "identity_quality": str(value.get("identity_quality") or "unknown").casefold(),
            "contains_person": value.get("contains_person"),
            "subject_type": str(value.get("subject_type") or "unknown").casefold().replace("-", "_"),
            "gender_presentation": str(value.get("gender_presentation") or "unknown").casefold(),
            "detail_types": [
                str(item).casefold().replace("-", "_").replace(" ", "_")
                for item in value.get("detail_types", [])
                if str(item).strip()
            ],
            "source_folder": str(value.get("source_folder") or ""),
            "source_excluded_reason": str(value.get("source_excluded_reason") or ""),
            "source": str(value.get("source") or ""),
            "notes": str(value.get("notes") or ""),
        }
        normalized_key = str(Path(str(key))).replace("\\", "/").casefold().lstrip("./")
        tags[normalized_key] = tag
    return tags


def model_view_tag(path: Path) -> dict[str, Any]:
    if MODEL_VIEW_TAG_PRODUCT_DIR is None:
        return {}
    try:
        key = str(path.resolve().relative_to(MODEL_VIEW_TAG_PRODUCT_DIR.resolve())).replace("\\", "/").casefold()
    except (OSError, ValueError):
        return {}
    return MODEL_VIEW_TAGS.get(key, {})


def is_sku_root_model_image(path: Path) -> bool:
    if MODEL_VIEW_TAG_PRODUCT_DIR is None:
        return False
    try:
        relative = path.resolve().relative_to(MODEL_VIEW_TAG_PRODUCT_DIR.resolve())
    except (OSError, ValueError):
        return False
    if len(relative.parts) != 1:
        return False
    tag = model_view_tag(path)
    subject = str(tag.get("subject_type") or "").casefold().replace("-", "_")
    return tag.get("contains_person") is True or subject == "model_person"


def section_index(path: Path) -> int:
    match = SECTION_RE.search(path.name)
    return int(match.group(1)) if match else 0


def is_hard_excluded_relative(path: Path, product_dir: Path) -> bool:
    try:
        parts = path.relative_to(product_dir).parts[:-1]
    except ValueError:
        return True
    for part in parts:
        folded = part.casefold().strip()
        if folded.startswith(SKIP_DIR_PREFIXES):
            return True
        if folded in {name.casefold() for name in HARD_EXCLUDED_DIR_NAMES}:
            return True
        if "弃用" in folded or "过程文件" in folded or "生成结果" in folded or "输出结果" in folded:
            return True
        if "备份" in folded or "backup" in folded:
            return True
    return False


def product_images(product_dir: Path) -> list[Path]:
    return [
        path
        for path in sorted(product_dir.rglob("*"), key=lambda item: str(item.relative_to(product_dir)).lower())
        if path.is_file()
        and path.suffix.lower() in IMAGE_EXTENSIONS
        and not is_hard_excluded_relative(path, product_dir)
        and not path.name.lower().startswith("_reference_contact_sheet")
    ]


def analysis_modules_by_index(path: Path | None) -> dict[int, dict[str, Any]]:
    if not path or not path.exists():
        return {}
    analysis = read_json(path)
    modules = analysis.get("modules", [])
    if not isinstance(modules, list):
        return {}
    result: dict[int, dict[str, Any]] = {}
    for module in modules:
        if isinstance(module, dict):
            try:
                result[int(module.get("index", 0))] = module
            except (TypeError, ValueError):
                continue
    return result


def pp_number(path: Path) -> int | None:
    match = PP_RE.search(path.stem)
    return int(match.group(1)) if match else None


def is_logo(path: Path) -> bool:
    return "logo" in path.stem.lower()


def path_has_directory(path: Path, directory_name: str) -> bool:
    return any(part.casefold() == directory_name.casefold() for part in path.parts[:-1])


def tag_contains_person(path: Path) -> bool | None:
    tag = model_view_tag(path)
    explicit = tag.get("contains_person")
    if isinstance(explicit, bool):
        return explicit
    subject_type = str(tag.get("subject_type") or "unknown")
    if subject_type in {"model_person", "person", "on_body_model", "model"}:
        return True
    if subject_type in {"product_flatlay", "product_detail", "product_only", "flatlay"}:
        return False
    return None


def is_model_identity_image(path: Path, identity_anchor: Path | None = None) -> bool:
    contains_person = tag_contains_person(path)
    tag = model_view_tag(path)
    return (
        not is_sku_root_model_image(path)
        and contains_person is True
        and str(tag.get("subject_type") or "") == "model_person"
        and bool(tag.get("usable_for_identity", False))
    )


def is_product_flat(path: Path, identity_anchor: Path | None = None) -> bool:
    return str(model_view_tag(path).get("subject_type") or "") == "product_flatlay"


def score_model_ref(path: Path) -> tuple[int, str]:
    tag = model_view_tag(path)
    view = str(tag.get("view") or "")
    quality = str(tag.get("identity_quality") or "unknown")
    view_rank = {"front": 0, "three_quarter": 1, "side": 2, "back": 8}.get(view, 9)
    framing_rank = 0 if is_full_body_model(path) else 2
    quality_rank = {"high": 0, "medium": 1, "low": 3, "unknown": 4}.get(quality, 4)
    return (view_rank + framing_rank + quality_rank, str(path).casefold())


def is_back_view_model(path: Path) -> bool:
    return str(model_view_tag(path).get("view") or "") == "back"


def is_full_body_model(path: Path) -> bool:
    return str(model_view_tag(path).get("framing") or "") == "full_body"


def unique(paths: list[Path], max_count: int) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        key = str(path.resolve()).lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(path.resolve())
        if len(result) >= max_count:
            break
    return result


def brief_identity_reference(product_dir: Path) -> Path | None:
    brief_path = product_dir / "_aplus_creative_work" / "aplus_creative_brief.md"
    if not brief_path.exists():
        return None
    match = MODEL_IDENTITY_REFERENCE_RE.search(read_text(brief_path))
    if not match:
        return None
    raw = match.group(1).strip().strip("`\"'")
    if not raw or raw.casefold().startswith(("no usable", "none", "n/a", "not available")):
        return None
    normalized = raw.replace("\\", "/")
    candidate = (product_dir / normalized).resolve()
    try:
        candidate.relative_to(product_dir.resolve())
    except ValueError:
        return None
    if candidate.is_file() and candidate.suffix.lower() in IMAGE_EXTENSIONS:
        if is_sku_root_model_image(candidate):
            return None
        return candidate
    return None


def classify_references(product_dir: Path, identity_anchor: Path | None = None) -> dict[str, list[Path]]:
    images = [path for path in product_images(product_dir) if not is_logo(path)]
    model_refs = sorted(
        [path for path in images if is_model_identity_image(path, identity_anchor)],
        key=score_model_ref,
    )
    if identity_anchor is not None:
        model_refs = unique([identity_anchor, *model_refs], 999)
    pp_refs = [path for path in images if str(model_view_tag(path).get("subject_type") or "") in {"product_flatlay", "product_detail"}]
    front_refs = [path for path in pp_refs if str(model_view_tag(path).get("subject_type") or "") == "product_flatlay" and str(model_view_tag(path).get("view") or "") == "front"]
    back_refs = [path for path in pp_refs if str(model_view_tag(path).get("subject_type") or "") == "product_flatlay" and str(model_view_tag(path).get("view") or "") == "back"]
    detail_refs = [path for path in pp_refs if str(model_view_tag(path).get("subject_type") or "") == "product_detail"]
    product_refs = front_refs + back_refs + detail_refs + pp_refs
    return {
        "model": model_refs,
        "front": front_refs,
        "back": back_refs,
        "detail": detail_refs,
        "product": product_refs,
    }


def image_role(path: Path, identity_anchor: Path | None = None) -> str:
    tag = model_view_tag(path)
    if is_sku_root_model_image(path):
        return "excluded_sku_root_model"
    subject = str(tag.get("subject_type") or "unknown")
    view = str(tag.get("view") or "unknown")
    details = set(tag.get("detail_types") or [])
    if subject == "brand_logo":
        return "brand_logo"
    if subject == "model_person":
        if view == "front":
            return "model_front"
        if view in {"side", "three_quarter"}:
            return "model_side"
        if view == "back":
            return "model_back"
        return "model_unknown"
    if subject == "product_flatlay":
        if view == "front":
            return "product_front"
        if view == "back":
            return "product_back"
        return "product_flatlay_other"
    if subject == "product_detail":
        if "fabric" in details:
            return "fabric_closeup"
        if "print_graphic" in details:
            return "graphic_detail"
        if details & {"neckline", "cuff", "zipper", "stitching", "hem", "pocket", "hardware", "closure"}:
            return "construction_detail"
        return "product_detail"
    return "unknown"


def build_image_role_map(product_dir: Path, identity_anchor: Path | None = None) -> dict[str, str]:
    return {
        str(path.relative_to(product_dir)): image_role(path, identity_anchor)
        for path in product_images(product_dir)
    }


def role_sources(
    product_dir: Path,
    buckets: dict[str, list[Path]],
    role_map: dict[str, str],
    identity_anchor: Path | None = None,
) -> dict[str, list[Path]]:
    sources: dict[str, list[Path]] = {
        "model_identity": [],
        "model_front": [],
        "model_side": [],
        "model_back": [],
        "product_front": buckets["front"],
        "product_back": buckets["back"],
        "product_detail": buckets["detail"],
        "graphic_detail": buckets["detail"],
        "fabric_closeup": [],
        "construction_detail": [],
        "brand_logo": [],
    }
    all_paths = product_images(product_dir)
    by_relative = {str(path.relative_to(product_dir)): path for path in all_paths}
    for key, role in role_map.items():
        path = by_relative.get(key)
        if path:
            sources.setdefault(role, []).append(path)
    sources["model_identity"] = unique(
        [*sources.get("model_front", []), *sources.get("model_side", [])],
        999,
    )
    if identity_anchor is not None:
        sources["model_identity"] = unique([identity_anchor, *sources["model_identity"]], 999)
    else:
        sources["model_identity"] = unique(sources["model_identity"], 999)
    sources["product_detail"] = unique([
        *sources.get("product_detail", []),
        *sources.get("fabric_closeup", []),
        *sources.get("construction_detail", []),
        *sources.get("graphic_detail", []),
    ], 999)
    return sources


def detect_module_role(context: str, index: int) -> tuple[str, list[str]]:
    normalized = normalize_text(context)
    no_reference_matches = [
        keyword
        for keyword in ROLE_KEYWORDS["no_reference"]
        if keyword.lower() in normalized
    ]
    if no_reference_matches:
        return "no_reference", sorted(set(no_reference_matches))
    placeholder_matches = [
        keyword
        for keyword in ROLE_KEYWORDS["placeholder_blocks"]
        if keyword.lower() in normalized
    ]
    if placeholder_matches:
        return "placeholder_blocks", sorted(set(placeholder_matches))
    influencer_background_matches = [
        keyword for keyword in ROLE_KEYWORDS["influencer_background"] if keyword.lower() in normalized
    ]
    if influencer_background_matches:
        return "influencer_background", sorted(set(influencer_background_matches))
    influencer_matches = [keyword for keyword in ROLE_KEYWORDS["influencer"] if keyword.lower() in normalized]
    if influencer_matches:
        return "influencer", sorted(set(influencer_matches))

    model_terms = ("模特", "人物", "人模", "model", "person", "on-body", "wearing")
    multi_angle_terms = (
        "多角度", "正侧背", "正面侧面背面", "front side back", "front-side-back", "multi-angle",
        "multiple angles",
    )
    fit_terms = ("版型", "廓形", "剪裁", "fit", "silhouette", "drop shoulder", "oversized")
    flatlay_terms = ("平铺", "flat lay", "flat-lay", "flatlay")
    front_back_terms = ("正背面", "正反面", "前后", "front and back", "front-back", "front/back")
    detail_terms = ("细节", "微距", "面料", "工艺", "领口", "袖口", "拉链", "印花", "detail", "macro", "fabric", "construction", "stitch", "zipper", "print")
    hero_terms = ("品牌banner", "brand banner", "hero", "开屏", "首图")

    if any(term in normalized for term in model_terms) and any(term in normalized for term in flatlay_terms) and any(term in normalized for term in front_back_terms):
        matches = [term for term in (*model_terms, *flatlay_terms, *front_back_terms) if term in normalized]
        return "model_flatlay", sorted(set(matches))
    if any(term in normalized for term in model_terms) and any(term in normalized for term in multi_angle_terms):
        matches = [term for term in (*model_terms, *multi_angle_terms) if term in normalized]
        return "model_multi_angle", sorted(set(matches))
    if any(term in normalized for term in detail_terms) and not context_requests_model(context):
        matches = [term for term in detail_terms if term in normalized]
        return "construction_detail", sorted(set(matches))
    if any(term in normalized for term in hero_terms) and any(term in normalized for term in model_terms):
        matches = [term for term in (*hero_terms, *model_terms) if term in normalized]
        return "hero_model", sorted(set(matches))
    if any(term in normalized for term in model_terms) and any(term in normalized for term in fit_terms):
        matches = [term for term in (*model_terms, *fit_terms) if term in normalized]
        return "fit_silhouette", sorted(set(matches))
    if any(term in normalized for term in front_back_terms):
        matches = [term for term in front_back_terms if term in normalized]
        return "front_back", sorted(set(matches))
    scores: dict[str, int] = {}
    matched: list[str] = []
    for role, keywords in ROLE_KEYWORDS.items():
        score = 0
        for keyword in keywords:
            if keyword.lower() in normalized:
                score += 1
                matched.append(keyword)
        if score:
            scores[role] = score
    if scores:
        priority = [
            "no_reference",
            "placeholder_blocks",
            "influencer_background",
            "influencer",
            "model_flatlay",
            "front_back",
            "fabric_detail",
            "construction_detail",
            "hero_model",
            "fit_silhouette",
            "graphic_detail",
            "brand_logo",
        ]
        return sorted(scores, key=lambda role: (-scores[role], priority.index(role) if role in priority else 99))[0], sorted(set(matched))
    return "unresolved", []


def module_context(prompt_path: Path, modules_by_index: dict[int, dict[str, Any]]) -> str:
    index = section_index(prompt_path)
    module = modules_by_index.get(index, {})
    prompt_text = read_text(prompt_path)
    relevant_prompt = prompt_text
    if "Module content:" in prompt_text:
        relevant_prompt = prompt_text.split("Module content:", 1)[1]
    if "Strict model identity lock:" in relevant_prompt:
        relevant_prompt = relevant_prompt.split("Strict model identity lock:", 1)[0]
    if "Negative Prompt:" in relevant_prompt:
        relevant_prompt = relevant_prompt.split("Negative Prompt:", 1)[0]
    parts = [
        prompt_path.name,
        str(module.get("title", "")),
        str(module.get("instruction", "")),
        str(module.get("raw", "")),
        relevant_prompt,
    ]
    return "\n".join(parts)


def context_requests_model(context: str) -> bool:
    normalized = normalize_text(context)
    no_model_terms = (
        "no model needed",
        "no model",
        "no people",
        "no person",
        "product close-ups only",
        "product closeups only",
        "macro detail module",
        "use product close-ups only",
        "不要出现人物",
        "不要人物",
        "不出现人物",
        "无人物",
        "不要出现模特",
        "不要模特",
    )
    if any(term in normalized for term in no_model_terms):
        return False
    return any(
        keyword in normalized
        for keyword in (
            "model",
            "person",
            "people",
            "on-body",
            "wearing",
            "lookbook",
            "styling mood",
            "模特",
            "人物",
            "人模",
            "上身",
            "穿着",
            "穿搭",
        )
    )


def context_requests_no_references(context: str) -> bool:
    normalized = normalize_text(context)
    return any(keyword.lower() in normalized for keyword in ROLE_KEYWORDS["no_reference"])


def looks_like_influencer_mapping(paths: list[str]) -> bool:
    return any("_influencer_selfie_work" in item.replace("/", "\\").lower() for item in paths)


def choose_refs_from_needs(
    needs: list[str],
    sources: dict[str, list[Path]],
    max_refs: int,
) -> list[Path]:
    per_need_limits = {
        "model_identity": 3,
        "product_front": 2,
        "product_back": 1,
        "product_detail": 4,
        "graphic_detail": 4,
        "fabric_closeup": 3,
        "construction_detail": 3,
        "brand_logo": 1,
    }
    refs: list[Path] = []
    for need in needs:
        refs.extend(sources.get(need, [])[: per_need_limits.get(need, max_refs)])
    return unique(refs, max_refs)


def relative_key(product_dir: Path, path: Path) -> str:
    return str(path.resolve().relative_to(product_dir.resolve())).replace("\\", "/").casefold()


def validate_semantic_tag_coverage(product_dir: Path) -> None:
    allowed = {relative_key(product_dir, path) for path in product_images(product_dir)}
    tagged = set(MODEL_VIEW_TAGS)
    missing = sorted(allowed - tagged)
    stale = sorted(tagged - allowed)
    invalid_source = sorted(
        key for key in allowed & tagged if MODEL_VIEW_TAGS[key].get("source") != "gpt-5.6-sol"
    )
    invalid_root_model_policy = sorted(
        key
        for key in allowed & tagged
        if len(Path(key).parts) == 1
        and (
            MODEL_VIEW_TAGS[key].get("contains_person") is True
            or MODEL_VIEW_TAGS[key].get("subject_type") == "model_person"
        )
        and (
            bool(MODEL_VIEW_TAGS[key].get("usable_for_identity"))
            or MODEL_VIEW_TAGS[key].get("source_excluded_reason") != "sku_root_model_image"
        )
    )
    if missing or stale or invalid_source or invalid_root_model_policy:
        raise RuntimeError(
            f"{product_dir.name}: semantic tag coverage is not exact; "
            f"missing={missing}, stale_or_excluded={stale}, invalid_source={invalid_source}, "
            f"invalid_root_model_policy={invalid_root_model_policy}"
        )


def source_priority(product_dir: Path, path: Path) -> tuple[int, str]:
    parts = path.resolve().relative_to(product_dir.resolve()).parts
    top = parts[0].casefold() if len(parts) > 1 else ""
    if top == "素材".casefold():
        rank = 0
    elif top in {"上身", "上身1"}:
        rank = 1
    elif top == "aigc":
        rank = 2
    else:
        rank = 3
    return rank, "/".join(parts).casefold()


def sorted_sources(product_dir: Path, paths: list[Path]) -> list[Path]:
    return sorted(unique(paths, 999), key=lambda path: source_priority(product_dir, path))


def validate_selected_reference(product_dir: Path, path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(product_dir.resolve())
    except ValueError as exc:
        raise RuntimeError(f"Reference is outside current SKU: {resolved}") from exc
    if not resolved.is_file() or resolved.suffix.lower() not in IMAGE_EXTENSIONS:
        raise RuntimeError(f"Reference does not exist as an allowed image: {resolved}")
    if is_hard_excluded_relative(resolved, product_dir):
        raise RuntimeError(f"Reference is in a hard-excluded directory: {resolved}")
    key = relative_key(product_dir, resolved)
    if key not in MODEL_VIEW_TAGS:
        raise RuntimeError(f"Reference has no exact SKU-relative semantic tag: {resolved}")
    if is_sku_root_model_image(resolved):
        raise RuntimeError(f"Root-level SKU model/person image is forbidden as a reference: {resolved}")
    return resolved


def discover_influencer_refs(product_dir: Path) -> list[Path]:
    generated = product_dir / "_influencer_selfie_work" / "generated"
    if not generated.exists():
        return []
    return sorted(
        [path.resolve() for path in generated.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS],
        key=lambda path: str(path).casefold(),
    )


def select_dynamic_contract_refs(
    product_dir: Path,
    module_role: str,
    context: str,
    sources: dict[str, list[Path]],
    identity_anchor: Path | None,
    max_refs: int,
) -> tuple[list[Path], dict[str, Any]]:
    """Create image-role requirements from module semantics, then select and validate them."""
    required: dict[str, int] = {}
    optional: dict[str, int] = {}
    if module_role == "no_reference":
        pass
    elif module_role == "hero_model":
        required = {"model_front": 1}
        optional = {"model_side": 1}
    elif module_role == "model_multi_angle":
        required = {"model_front": 1, "model_back": 1}
        optional = {"model_side": 1}
    elif module_role == "fit_silhouette":
        required = {"model_front": 1}
        optional = {"model_side": 1, "model_back": 1}
    elif module_role == "model_flatlay":
        required = {"model_front": 1, "product_front": 1, "product_back": 1}
        optional = {"model_side": 1, "product_detail": 1}
    elif module_role == "front_back":
        required = {"product_front": 1, "product_back": 1}
        optional = {"product_detail": 2}
    elif module_role in {"construction_detail", "fabric_detail", "graphic_detail"}:
        required = {"verified_detail": 1}
        optional = {"verified_detail": 4}
    elif module_role == "placeholder_blocks":
        required = {"product_front": 1}
        optional = {"brand_logo": 1}
    elif module_role == "influencer_background":
        required = {"product_front": 1}
        optional = {"product_detail": 2, "brand_logo": 1}
    elif module_role == "influencer":
        refs = discover_influencer_refs(product_dir)
        if not refs:
            raise RuntimeError(f"{product_dir.name}: influencer module has no current-SKU generated influencer reference")
        return refs[:max_refs], {
            "required_roles": {"influencer": 1},
            "optional_roles": {},
            "selected_roles": {"influencer": len(refs[:max_refs])},
            "contract_validation": "passed",
        }
    else:
        raise RuntimeError(f"Unresolved or unsupported module function: {module_role}")

    pools = {role: sorted_sources(product_dir, paths) for role, paths in sources.items()}
    pools["verified_detail"] = sorted_sources(
        product_dir,
        [
            *sources.get("fabric_closeup", []),
            *sources.get("construction_detail", []),
            *sources.get("graphic_detail", []),
            *sources.get("product_detail", []),
        ],
    )
    if identity_anchor is not None and image_role(identity_anchor) == "model_front":
        pools["model_front"] = unique([identity_anchor, *pools.get("model_front", [])], 999)

    selected: list[Path] = []
    selected_roles: dict[str, int] = {}
    missing: list[str] = []
    for role, count in required.items():
        chosen = [path for path in pools.get(role, []) if path not in selected][:count]
        if len(chosen) < count:
            missing.append(f"{role}:{count - len(chosen)}")
        selected.extend(chosen)
        selected_roles[role] = selected_roles.get(role, 0) + len(chosen)
    if missing:
        raise RuntimeError(
            f"{product_dir.name}: module contract {module_role} missing required semantic roles: {', '.join(missing)}"
        )
    for role, count in optional.items():
        remaining = max_refs - len(selected)
        if remaining <= 0:
            break
        chosen = [path for path in pools.get(role, []) if path not in selected][: min(count, remaining)]
        selected.extend(chosen)
        selected_roles[role] = selected_roles.get(role, 0) + len(chosen)
    selected = [validate_selected_reference(product_dir, path) for path in unique(selected, max_refs)]
    return selected, {
        "required_roles": required,
        "optional_roles": optional,
        "selected_roles": selected_roles,
        "contract_validation": "passed",
    }


def section_model_refs(sources: dict[str, list[Path]], index: int) -> list[Path]:
    models = sources.get("model_identity", [])
    if not models:
        return []
    if index == 1:
        return unique([path for path in models if not is_back_view_model(path)], 3)
    if len(models) == 1:
        return models[:1]

    preferred = [path for path in models if not is_back_view_model(path)]
    pool = preferred or models
    offset = {1: 0, 2: 1, 3: 2}.get(index, 0)
    selected: list[Path] = []

    for step in range(len(pool)):
        selected.append(pool[(offset + step) % len(pool)])
        if len(unique(selected, 99)) >= 2:
            break

    if not any(is_full_body_model(path) for path in selected):
        full_body = next((path for path in preferred if is_full_body_model(path)), None)
        if full_body:
            selected.insert(0, full_body)

    for path in models:
        if len(unique(selected, 99)) >= 2:
            break
        selected.append(path)

    return unique(selected, 3)


def is_preferred_identity_view(path: Path) -> bool:
    tag = model_view_tag(path)
    return (
        tag_contains_person(path) is not False
        and bool(tag.get("usable_for_identity", True))
        and str(tag.get("view") or "unknown") in {"front", "three_quarter"}
        and not is_back_view_model(path)
    )


def enforce_section_two_identity_lock(
    refs: list[Path],
    sources: dict[str, list[Path]],
    identity_anchor: Path | None,
    max_refs: int,
) -> tuple[list[Path], dict[str, Any]]:
    """Always carry the brief identity anchor into Section 2 and pair it when possible."""
    model_keys = model_identity_keys(sources)
    if identity_anchor is None or model_key(identity_anchor) not in model_keys:
        return refs, {
            "section2_identity_anchor_forced": False,
            "section2_identity_companion_added": False,
        }

    non_model_refs = [path for path in refs if model_key(path) not in model_keys]
    candidates = sources.get("model_identity", [])
    selected = [identity_anchor]
    companion = next(
        (
            path
            for path in candidates
            if model_key(path) != model_key(identity_anchor) and is_preferred_identity_view(path)
        ),
        None,
    )
    if companion is None:
        companion = next(
            (
                path
                for path in candidates
                if model_key(path) != model_key(identity_anchor)
                and tag_contains_person(path) is not False
                and bool(model_view_tag(path).get("usable_for_identity", True))
                and not is_back_view_model(path)
            ),
            None,
        )
    if companion is not None:
        selected.append(companion)

    return unique([*selected, *non_model_refs], max_refs), {
        "section2_identity_anchor_forced": True,
        "section2_identity_companion_added": companion is not None,
    }


def model_key(path: Path) -> str:
    try:
        return str(path.resolve()).lower()
    except OSError:
        return str(path).lower()


def model_identity_keys(sources: dict[str, list[Path]]) -> set[str]:
    return {
        model_key(path)
        for role in ("model_identity", "model_front", "model_side", "model_back")
        for path in sources.get(role, [])
    }


def enforce_distinct_model_refs_for_sections(
    refs: list[Path],
    sources: dict[str, list[Path]],
    section_number: int,
    max_refs: int,
) -> list[Path]:
    if section_number not in {1, 2, 3}:
        return refs
    model_set = {str(path.resolve()).lower() for path in sources.get("model_identity", [])}
    selected_models = section_model_refs(sources, section_number)
    non_model_refs = [path for path in refs if str(path.resolve()).lower() not in model_set]
    return unique(selected_models + non_model_refs, max_refs)


def enforce_unique_model_refs_across_all_sections(
    refs: list[Path],
    sources: dict[str, list[Path]],
    section_number: int,
    max_refs: int,
    used_model_keys: set[str],
) -> list[Path]:
    """Avoid reusing the same supplied model reference in different modules for one SPU."""
    model_keys = model_identity_keys(sources)
    if not model_keys:
        return refs

    current_model_refs = [path for path in refs if model_key(path) in model_keys]
    if not current_model_refs:
        return refs

    non_model_refs = [path for path in refs if model_key(path) not in model_keys]
    remaining_slots = max(0, max_refs - len(non_model_refs))
    if remaining_slots == 0:
        return unique(non_model_refs, max_refs)

    all_model_candidates = sources.get("model_identity", [])
    if section_number == 1:
        all_model_candidates = [path for path in all_model_candidates if not is_back_view_model(path)]
    candidates = unique(section_model_refs(sources, section_number) + all_model_candidates, 999)
    unused_candidates = [path for path in candidates if model_key(path) not in used_model_keys]
    if not candidates:
        return unique(non_model_refs, max_refs)

    # Prefer unused model references, but do not let the no-repeat rule break a
    # template section that explicitly needs a model/person. When unused AIGC
    # images run out, reuse the best earlier model references to keep at least
    # two identity references attached.
    desired_count = min(max(len(current_model_refs), 2), len(candidates), remaining_slots)
    selected: list[Path] = []

    fill_pool = unused_candidates + [path for path in candidates if path not in unused_candidates]

    if desired_count >= 1 and not any(is_full_body_model(path) for path in fill_pool[:desired_count]):
        full_body = next((path for path in fill_pool if is_full_body_model(path)), None)
        if full_body:
            selected.append(full_body)

    for path in fill_pool:
        if len(unique(selected, 999)) >= desired_count:
            break
        selected.append(path)

    return unique(selected + non_model_refs, max_refs)


def enforce_section_one_no_back_view_model_refs(
    refs: list[Path],
    sources: dict[str, list[Path]],
    max_refs: int,
) -> list[Path]:
    """Section 1 must not use back-view model references."""
    model_keys = model_identity_keys(sources)
    if not model_keys:
        return refs
    cleaned: list[Path] = []
    removed_back_model = False
    for path in refs:
        if model_key(path) in model_keys and is_back_view_model(path):
            removed_back_model = True
            continue
        cleaned.append(path)
    if not removed_back_model:
        return refs
    non_back_models = [
        path
        for path in sources.get("model_identity", [])
        if not is_back_view_model(path) and model_key(path) not in {model_key(item) for item in cleaned}
    ]
    return unique(non_back_models + cleaned, max_refs)


def enforce_no_single_back_view_model_ref(
    refs: list[Path],
    sources: dict[str, list[Path]],
    max_refs: int,
) -> list[Path]:
    """Never leave a module with only one model reference when that model is a back view."""
    model_keys = model_identity_keys(sources)
    if not model_keys:
        return refs

    model_refs = [path for path in refs if model_key(path) in model_keys]
    if len(model_refs) != 1 or not is_back_view_model(model_refs[0]):
        return refs

    existing_keys = {model_key(path) for path in refs}
    companion = next(
        (
            path
            for path in sources.get("model_identity", [])
            if model_key(path) not in existing_keys and not is_back_view_model(path)
        ),
        None,
    )
    if companion is None:
        companion = next(
            (
                path
                for path in sources.get("model_identity", [])
                if model_key(path) not in existing_keys
            ),
            None,
        )
    if companion is not None:
        return unique([companion, *refs], max_refs)

    # If no second model reference exists, remove the single back view instead of sending
    # a back-only identity reference that can cause an invented front-facing model.
    return unique([path for path in refs if model_key(path) not in model_keys], max_refs)


def mark_used_model_refs(refs: list[Path], sources: dict[str, list[Path]], used_model_keys: set[str]) -> None:
    model_keys = model_identity_keys(sources)
    for path in refs:
        key = model_key(path)
        if key in model_keys:
            used_model_keys.add(key)


def section_selected_model_keys(refs: list[Path], sources: dict[str, list[Path]]) -> set[str]:
    model_keys = model_identity_keys(sources)
    return {model_key(path) for path in refs if model_key(path) in model_keys}


PRODUCT_TYPE_PATTERNS = (
    re.compile(r"(?im)^\s*[-*]?\s*(?:product[ _-]?type|produkttyp)\s*:\s*([^;\r\n]+)"),
    re.compile(r"(?i)\bproduct[ _-]?type\s*:\s*([^;\r\n]+)"),
)


def product_type_from_prompts(prompt_paths: list[Path]) -> str:
    """Read the canonical product type once for a SKU from generated attribute-backed prompts."""
    for prompt_path in prompt_paths:
        text = read_text(prompt_path)
        for pattern in PRODUCT_TYPE_PATTERNS:
            match = pattern.search(text)
            if match:
                value = match.group(1).strip().strip("-: ")
                if value:
                    return value
    return ""


def validate_section3_human_fashion_action(prompt_path: Path) -> tuple[bool, str]:
    """Validate the human-authored Section 3 action inside Layout task without rewriting it."""
    text = read_text(prompt_path)
    legacy = [marker for marker in LEGACY_SECTION3_ACTION_MARKERS if marker.casefold() in text.casefold()]
    if legacy:
        return False, f"remove separate or legacy action block and merge its content into Layout task: {legacy[0]}"
    matches = list(LAYOUT_TASK_RE.finditer(text))
    if len(matches) != 1:
        return False, f"expected exactly one action-bearing 'Layout task:' field, found {len(matches)}"
    action = re.sub(r"\s+", " ", matches[0].group(1)).strip(" -")
    if len(action) < 120:
        return False, "Layout task is too short; append the human fashion action with body mechanics, direction, and product-clearance logic"
    forbidden_workflow_phrases = (
        "shared reference files",
        "geteilte referenzdateien",
        "because this module shares",
        "da dieses modul einige model-referenzen",
        "safe action library",
        "category-specific action",
        "selected automatically",
    )
    if any(phrase in action.casefold() for phrase in forbidden_workflow_phrases):
        return False, "human fashion action contains workflow metadata or legacy library wording"
    body_terms = (
        "hand", "arm", "elbow", "shoulder", "torso", "head", "gaze", "chin", "hip", "leg", "foot", "knee",
        "händ", "hand", "arm", "ellbogen", "schulter", "oberkörper", "kopf", "blick", "kinn", "hüft", "bein", "fuß", "fuss", "knie",
    )
    body_term_count = sum(1 for term in body_terms if term in action.casefold())
    if body_term_count < 2:
        return False, "Layout task needs at least two concrete body/action cues from the human-authored fashion action"
    direction_terms = (
        "gaze", "look", "face", "turn", "rotate", "angle", "toward", "away", "three-quarter",
        "blick", "schaue", "drehe", "dreh", "winkel", "richtung", "zugewandt", "abgewandt",
    )
    if not any(term in action.casefold() for term in direction_terms):
        return False, "Layout task needs a gaze, torso, or body-direction cue for the human-authored fashion action"
    clearance_terms = (
        "clear", "unobstructed", "do not cover", "avoid covering", "outside", "visible", "zipper", "hem", "graphic", "embroidery", "pocket",
        "frei", "unverdeckt", "nicht verdecken", "außerhalb", "sichtbar", "reißverschluss", "reissverschluss", "saum", "grafik", "stickerei", "tasche",
    )
    if not any(term in action.casefold() for term in clearance_terms):
        return False, "Layout task needs product-clearance logic so hands and limbs do not hide important garment features"
    return True, action


def choose_placeholder_refs(sources: dict[str, list[Path]], buckets: dict[str, list[Path]], max_refs: int) -> list[Path]:
    refs: list[Path] = []
    refs.extend(sources.get("product_front", []))
    refs.extend(sources.get("product_detail", []))
    refs.extend(sources.get("fabric_closeup", []))
    refs.extend(sources.get("construction_detail", []))
    refs.extend(sources.get("brand_logo", []))
    refs.extend(buckets.get("product", []))
    refs = [path for path in refs if "aigc" not in str(path).lower()]
    return unique(refs, max_refs)


def choose_detail_flatlay_refs(sources: dict[str, list[Path]], buckets: dict[str, list[Path]], max_refs: int) -> list[Path]:
    refs: list[Path] = []
    refs.extend(sources.get("product_detail", []))
    refs.extend(sources.get("graphic_detail", []))
    refs.extend(sources.get("fabric_closeup", []))
    refs.extend(sources.get("construction_detail", []))
    refs.extend(sources.get("product_front", []))
    refs.extend(sources.get("product_back", []))
    refs.extend(buckets.get("product", []))
    refs = [path for path in refs if "aigc" not in str(path).lower()]
    return unique(refs, max_refs)


def choose_refs(prompt_path: Path, buckets: dict[str, list[Path]], max_refs: int) -> list[Path]:
    index = section_index(prompt_path)
    text = read_text(prompt_path).lower()
    role_text = prompt_path.name.lower()
    model = buckets["model"]
    front = buckets["front"]
    back = buckets["back"]
    detail = buckets["detail"]
    product = buckets["product"]

    if "influencer ugc reference integration" in text:
        return []
    if index == 1:
        return unique(model[:3] + front[:1] + detail[:1], max_refs)
    if index == 2:
        return unique(model[:4] + front[:2] + back[:1], max_refs)
    if index == 3:
        return unique(front[:2] + back[:1] + detail[:4], max_refs)
    if index == 4:
        return unique(detail[:5] + front[:1], max_refs)
    if any(word in role_text for word in ("hero", "opening", "campaign")):
        return unique(model[:3] + front[:1] + detail[:1], max_refs)
    if any(word in role_text for word in ("fit", "silhouette", "front-side-back", "oversized")):
        return unique(model[:4] + front[:2] + back[:1], max_refs)
    if any(word in role_text for word in ("fabric", "material", "construction", "stitch", "texture")):
        return unique(detail[:5] + front[:1], max_refs)
    if any(word in role_text for word in ("graphic", "print", "front-back", "detail", "signature")):
        return unique(front[:2] + back[:1] + detail[:4], max_refs)
    return unique(model[:2] + product[:3], max_refs)


def main() -> int:
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Root folder containing product subfolders.")
    parser.add_argument("--template-analysis", help="Optional _aplus_creative_template_analysis.json.")
    parser.add_argument("--max-references-per-module", type=int, default=6)
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    analysis_path = Path(args.template_analysis).expanduser().resolve() if args.template_analysis else root / "_aplus_creative_template_analysis.json"
    modules_by_index = analysis_modules_by_index(analysis_path)
    summary: dict[str, Any] = {"root": str(root), "products": {}}
    pending_human_actions: list[str] = []
    for product_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        global MODEL_VIEW_TAGS, MODEL_VIEW_TAG_PRODUCT_DIR
        MODEL_VIEW_TAG_PRODUCT_DIR = product_dir
        MODEL_VIEW_TAGS = load_model_view_tags(product_dir)
        prompt_dir = product_dir / "_aplus_creative_work" / "module_prompts"
        if not prompt_dir.exists():
            continue
        validate_semantic_tag_coverage(product_dir)
        reference_path = product_dir / "_aplus_creative_work" / "module_reference_images.json"
        # Rebuild from a deliberately empty map. Never inherit historical paths.
        mapping: dict[str, list[str]] = {}
        identity_anchor = brief_identity_reference(product_dir)
        buckets = classify_references(product_dir, identity_anchor)
        image_roles = build_image_role_map(product_dir, identity_anchor)
        sources = role_sources(product_dir, buckets, image_roles, identity_anchor)
        roles_path = product_dir / "_aplus_creative_work" / "reference_image_roles.json"
        requirements_path = product_dir / "_aplus_creative_work" / "module_reference_requirements.json"
        requirements: dict[str, Any] = {}
        product_summary: dict[str, Any] = {"modules": {}}
        used_model_keys: set[str] = set()
        section_model_keys_by_index: dict[int, set[str]] = {}
        prompt_paths = sorted(prompt_dir.glob("*.txt"))
        product_type = product_type_from_prompts(prompt_paths)
        product_summary["product_type"] = product_type
        for prompt_path in prompt_paths:
            context = module_context(prompt_path, modules_by_index)
            module_meta = modules_by_index.get(section_index(prompt_path), {})
            authoritative_context = "\n".join(
                str(module_meta.get(key, "")) for key in ("title", "instruction", "raw")
            )
            module_role, matched_keywords = detect_module_role(authoritative_context, section_index(prompt_path))
            if module_role == "unresolved":
                module_role, matched_keywords = detect_module_role(context, section_index(prompt_path))
            if context_requests_no_references(context):
                module_role = "no_reference"
                matched_keywords = sorted(set([*matched_keywords, "no_reference"]))
            if module_role == "unresolved":
                raise RuntimeError(
                    f"{product_dir.name}/{prompt_path.name}: cannot derive module function from template and prompt semantics"
                )
            refs, contract = select_dynamic_contract_refs(
                product_dir,
                module_role,
                context,
                sources,
                identity_anchor,
                args.max_references_per_module,
            )
            needs = list(contract.get("required_roles", {})) + list(contract.get("optional_roles", {}))
            current_section_model_keys = section_selected_model_keys(refs, sources)
            duplicate_section2_model_keys: set[str] = set()
            section3_human_action_required = False
            section3_human_action_validated = False
            section3_human_action_text = ""
            section3_human_action_error = ""
            if section_index(prompt_path) == 3:
                duplicate_section2_model_keys = current_section_model_keys & section_model_keys_by_index.get(2, set())
                if duplicate_section2_model_keys:
                    section3_human_action_required = True
                    section3_human_action_validated, action_result = validate_section3_human_fashion_action(prompt_path)
                    if not section3_human_action_validated:
                        section3_human_action_error = action_result
                        pending_human_actions.append(
                            f"{product_dir.name}/{prompt_path.name}: {section3_human_action_error}"
                        )
                    else:
                        section3_human_action_text = action_result
            mark_used_model_refs(refs, sources, used_model_keys)
            section_model_keys_by_index[section_index(prompt_path)] = current_section_model_keys
            requirements[prompt_path.name] = {
                "module_role": module_role,
                "needs": needs,
                "matched_keywords": matched_keywords,
                "source": "dynamic contract derived from template analysis + module prompt semantics",
                "product_type": product_type,
                "model_identity_reference": str(identity_anchor) if identity_anchor else None,
                **contract,
                "section3_human_fashion_action_required": section3_human_action_required,
                "section3_human_fashion_action_validated": section3_human_action_validated,
                "section3_human_fashion_action": section3_human_action_text or None,
                "section3_shared_model_references": sorted(duplicate_section2_model_keys),
                "section3_human_fashion_action_error": section3_human_action_error or None,
            }
            mapping[prompt_path.name] = [str(path) for path in refs]
            product_summary["modules"][prompt_path.name] = {
                "reference_role": module_role,
                "needs": needs,
                "matched_keywords": matched_keywords,
                "references": [str(path) for path in refs],
                **contract,
            }
        roles_path.write_text(json.dumps(image_roles, ensure_ascii=False, indent=2), encoding="utf-8")
        requirements_path.write_text(json.dumps(requirements, ensure_ascii=False, indent=2), encoding="utf-8")
        product_summary["reference_image_roles"] = str(roles_path)
        product_summary["module_reference_requirements"] = str(requirements_path)
        product_summary["model_identity_reference"] = str(identity_anchor) if identity_anchor else None
        reference_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
        product_summary["module_reference_images"] = str(reference_path)
        summary["products"][product_dir.name] = product_summary

    out_path = root / "_aplus_module_reference_images_summary.json"
    summary["pending_section3_human_fashion_actions"] = pending_human_actions
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out_path)
    if pending_human_actions:
        print(
            "Section 3 human fashion action is required before generation:\n- "
            + "\n- ".join(pending_human_actions),
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
