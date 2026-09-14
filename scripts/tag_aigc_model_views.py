#!/usr/bin/env python
"""Tag supplied AIGC/上身 candidates by subject, view angle, and framing.

Writes <product>/_aplus_creative_work/aigc_model_view_tags.json for use by
build_module_reference_images.py. ToAPIs chat/completions is used for API
tagging, defaulting to gemini-3.5-flash; a filename heuristic fallback keeps
the pipeline usable if no key is available.
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import re
import sys
from io import BytesIO
from pathlib import Path
from typing import Any

import requests


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
TOAPI_ENDPOINT = "https://toapis.com/v1/chat/completions"


def data_url(path: Path, max_side: int = 1200) -> str:
    try:
        from PIL import Image, ImageOps

        image = Image.open(path)
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        buf = BytesIO()
        image.save(buf, format="JPEG", quality=78, optimize=True)
        encoded = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"
    except Exception:
        mime = mimetypes.guess_type(path.name)[0] or "image/png"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{encoded}"


def image_files(product_dir: Path) -> list[Path]:
    candidates: list[Path] = []
    for directory_name in ("AIGC", "上身"):
        directory = product_dir / directory_name
        if not directory.exists():
            continue
        candidates.extend(
            path
            for path in directory.rglob("*")
            if path.is_file()
            and path.suffix.lower() in IMAGE_EXTENSIONS
            and not any(part.casefold().startswith(("_aplus", "_influencer")) for part in path.relative_to(product_dir).parts)
        )
    return sorted(candidates, key=lambda item: str(item.relative_to(product_dir)).casefold())


def heuristic_tag(path: Path) -> dict[str, Any]:
    text = f"{path.parent.name} {path.stem}".casefold()
    view = "unknown"
    if any(term in text for term in ("back", "rear", "背面", "背影", "背视图")):
        view = "back"
    elif any(term in text for term in ("side", "profile", "侧面", "侧身")):
        view = "side"
    elif any(term in text for term in ("three", "3q", "quarter", "斜侧", "三分")):
        view = "three_quarter"
    elif any(term in text for term in ("front", "face", "正面", "正脸")):
        view = "front"

    framing = "unknown"
    if any(term in text for term in ("full", "body", "全身", "整身")):
        framing = "full_body"
    elif any(term in text for term in ("half", "upper", "半身", "上半身")):
        framing = "half_body"

    contains_person = any(part.casefold() == "aigc" for part in path.parts[:-1])
    return {
        "view": view,
        "framing": framing,
        "identity_quality": "unknown",
        "usable_for_identity": contains_person and view != "back",
        "contains_person": contains_person,
        "subject_type": "model_person" if contains_person else "unknown",
        "gender_presentation": "unknown",
        "notes": "Heuristic tag from filename/path; 上身 remains non-model unless image analysis confirms a person.",
        "source": "heuristic",
    }


def extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    match = re.search(r"\{.*\}", text, flags=re.S)
    if match:
        text = match.group(0)
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Model response is not a JSON object")
    return data


def tag_with_gpt55(path: Path, api_key: str, model: str) -> dict[str, Any]:
    prompt = (
        "Classify this apparel model reference image for an image-generation pipeline. "
        "Return JSON only with these keys: "
        "view (front, three_quarter, side, back, detail, unknown), "
        "framing (full_body, half_body, upper_body, closeup, unknown), "
        "contains_person (true/false), "
        "subject_type (model_person, product_flatlay, product_detail, unknown), "
        "gender_presentation (woman, man, ambiguous, unknown), "
        "identity_quality (high, medium, low, unknown), "
        "usable_for_identity (true/false), "
        "notes (short English). "
        "Distinguish a real person wearing the garment from product-only front/back flat lays. "
        "The directory name 上身 is not evidence that a person is present. "
        "A back-view person means the face/front identity is not visible enough and must not be the only model reference."
    )
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url(path)}},
                ],
            }
        ],
        "max_tokens": 220,
    }
    response = requests.post(
        TOAPI_ENDPOINT,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()
    content = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    if isinstance(content, list):
        content = "\n".join(str(item.get("text", "")) for item in content if isinstance(item, dict))
    tag = extract_json(str(content))
    tag["source"] = model
    return tag


def normalize_tag(tag: dict[str, Any]) -> dict[str, Any]:
    view = str(tag.get("view") or "unknown").strip().casefold().replace("-", "_")
    if view not in {"front", "three_quarter", "side", "back", "detail", "unknown"}:
        view = "unknown"
    framing = str(tag.get("framing") or "unknown").strip().casefold().replace("-", "_")
    if framing not in {"full_body", "half_body", "upper_body", "closeup", "unknown"}:
        framing = "unknown"
    return {
        "view": view,
        "framing": framing,
        "identity_quality": str(tag.get("identity_quality") or "unknown").strip().casefold(),
        "usable_for_identity": bool(tag.get("usable_for_identity", False)),
        "contains_person": bool(tag.get("contains_person", False)),
        "subject_type": str(tag.get("subject_type") or "unknown").strip().casefold().replace("-", "_"),
        "gender_presentation": str(tag.get("gender_presentation") or "unknown").strip().casefold(),
        "notes": str(tag.get("notes") or "").strip(),
        "source": str(tag.get("source") or "unknown"),
    }


def product_dirs(root: Path, selected: set[str] | None) -> list[Path]:
    dirs = [
        path
        for path in sorted(root.iterdir(), key=lambda item: item.name.casefold())
        if path.is_dir()
        and path.name not in {"LOGO", "输出结果"}
        and not path.name.startswith("_")
        and (selected is None or path.name in selected)
    ]
    return dirs


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--provider", choices=("gpt55", "heuristic"), default="gpt55")
    parser.add_argument("--api-key", default=os.getenv("TOAPIS_API_KEY") or os.getenv("OPENAI_API_KEY"))
    parser.add_argument("--model", default="gemini-3.5-flash")
    parser.add_argument("--product", help="Optional product folder name, or comma-separated names.")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--allow-heuristic-fallback",
        action="store_true",
        help="Explicitly allow heuristic tags after an API failure. Disabled by default.",
    )
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    selected = {item.strip() for item in args.product.split(",") if item.strip()} if args.product else None
    if args.provider == "gpt55" and not args.api_key:
        raise SystemExit("Missing ToAPIs key. Pass --api-key or set TOAPIS_API_KEY.")

    summary: dict[str, Any] = {"root": str(root), "products": {}}
    for product_dir in product_dirs(root, selected):
        work_dir = product_dir / "_aplus_creative_work"
        work_dir.mkdir(parents=True, exist_ok=True)
        out_path = work_dir / "aigc_model_view_tags.json"
        if out_path.exists() and not args.overwrite:
            summary["products"][product_dir.name] = {"status": "exists", "path": str(out_path)}
            continue

        tags: dict[str, Any] = {}
        for image_path in image_files(product_dir):
            try:
                tag = tag_with_gpt55(image_path, args.api_key or "", args.model) if args.provider == "gpt55" else heuristic_tag(image_path)
            except Exception as exc:
                if not args.allow_heuristic_fallback:
                    raise RuntimeError(f"Strict image tagging failed for {image_path}: {exc}") from exc
                tag = heuristic_tag(image_path)
                tag["error"] = str(exc)
            rel = str(image_path.relative_to(product_dir))
            normalized = normalize_tag(tag)
            root_model_excluded = len(Path(rel).parts) == 1 and (
                normalized.get("contains_person") is True
                or normalized.get("subject_type") == "model_person"
            )
            if root_model_excluded:
                normalized["usable_for_identity"] = False
                normalized["source_excluded_reason"] = "sku_root_model_image"
            tags[rel] = normalized
            print(f"{product_dir.name}: {rel} -> {tags[rel]['view']} / {tags[rel]['framing']}")

        out_path.write_text(json.dumps(tags, ensure_ascii=False, indent=2), encoding="utf-8")
        summary["products"][product_dir.name] = {"status": "written", "path": str(out_path), "count": len(tags)}

    summary_path = root / "_aplus_aigc_model_view_tags_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(summary_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
