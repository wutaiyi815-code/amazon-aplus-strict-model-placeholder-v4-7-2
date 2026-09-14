from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import requests
from PIL import Image, ImageDraw, ImageOps


ENDPOINT = "https://toapis.com/v1/chat/completions"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
MODEL = "gemini-3.1-flash-lite"
SKIP_DIR_PREFIXES = ("_aplus", "_influencer")
HARD_EXCLUDED_DIR_NAMES = {"弃用", "过程文件", "生成结果", "输出结果", "备份", "备份目录"}


def hard_excluded(path: Path, product_dir: Path) -> bool:
    for part in path.relative_to(product_dir).parts[:-1]:
        folded = part.casefold().strip()
        if folded.startswith(SKIP_DIR_PREFIXES):
            return True
        if folded in {name.casefold() for name in HARD_EXCLUDED_DIR_NAMES}:
            return True
        if any(term in folded for term in ("弃用", "过程文件", "生成结果", "输出结果", "备份", "backup")):
            return True
    return False


def configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def image_inventory(product_dir: Path) -> list[Path]:
    tags_path = product_dir / "_aplus_creative_work" / "aigc_model_view_tags.json"
    try:
        tags = json.loads(tags_path.read_text(encoding="utf-8-sig")) if tags_path.exists() else {}
    except Exception:
        tags = {}
    return sorted(
        [
            p
            for p in product_dir.rglob("*")
            if p.is_file()
            and p.suffix.lower() in IMAGE_EXTENSIONS
            and not hard_excluded(p, product_dir)
            and not p.name.lower().startswith("logo")
            and not p.name.lower().startswith("_manual_reference_contact_sheet")
            and not is_sku_root_model_image(product_dir, p, tags)
        ],
        key=lambda p: str(p.relative_to(product_dir)).casefold(),
    )


def role_label(product_dir: Path, path: Path) -> str:
    return "VISUAL_ONLY"


def create_contact_sheet(product_dir: Path, images: list[Path], output: Path) -> list[str]:
    columns = 4
    tile_w, tile_h, label_h = 300, 360, 42
    rows = max(1, (len(images) + columns - 1) // columns)
    sheet = Image.new("RGB", (columns * tile_w, rows * (tile_h + label_h)), "white")
    draw = ImageDraw.Draw(sheet)
    labels: list[str] = []
    for index, path in enumerate(images, 1):
        image = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
        image.thumbnail((tile_w - 12, tile_h - 12), Image.Resampling.LANCZOS)
        row, col = divmod(index - 1, columns)
        cell_x = col * tile_w
        cell_y = row * (tile_h + label_h)
        x = cell_x + (tile_w - image.width) // 2
        y = cell_y + (tile_h - image.height) // 2
        sheet.paste(image, (x, y))
        label = f"#{index:02d} {role_label(product_dir, path)}"
        ascii_label = label.encode("ascii", errors="replace").decode("ascii")
        draw.text((cell_x + 6, cell_y + tile_h + 8), ascii_label[:45], fill="black")
        labels.append(f"#{index:02d}: {role_label(product_dir, path)}")
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, format="JPEG", quality=88, optimize=True)
    return labels


def data_url(path: Path, max_side: int = 1800) -> str:
    image = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    stream = io.BytesIO()
    image.save(stream, format="JPEG", quality=84, optimize=True)
    encoded = base64.b64encode(stream.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def is_sku_root_model_tag(relative_path: str, tag: Any) -> bool:
    if len(Path(str(relative_path)).parts) != 1 or not isinstance(tag, dict):
        return False
    subject = str(tag.get("subject_type") or "").casefold().replace("-", "_")
    return tag.get("contains_person") is True or subject == "model_person"


def is_sku_root_model_image(product_dir: Path, path: Path, tags: dict[str, Any]) -> bool:
    try:
        rel = str(path.relative_to(product_dir)).replace("\\", "/")
    except ValueError:
        return False
    tag = tags.get(rel) or tags.get(str(Path(rel)))
    return is_sku_root_model_tag(rel, tag)


def creative_eligible_tags(tags: dict[str, Any]) -> dict[str, Any]:
    return {
        rel: tag
        for rel, tag in tags.items()
        if not is_sku_root_model_tag(str(rel), tag)
    }


def candidate_model_reference(product_dir: Path, images: list[Path]) -> Path | None:
    tag_path = product_dir / "_aplus_creative_work" / "aigc_model_view_tags.json"
    if tag_path.exists():
        tags = load_json(tag_path)
        ranked: list[tuple[tuple[int, int, int], Path]] = []
        view_score = {"front": 0, "three_quarter": 1, "side": 2, "unknown": 3, "back": 9, "detail": 9}
        framing_score = {"full_body": 0, "half_body": 1, "upper_body": 2, "closeup": 3, "unknown": 4}
        quality_score = {"high": 0, "medium": 1, "low": 2, "unknown": 3}
        for rel, tag in tags.items():
            path = product_dir / rel
            if is_sku_root_model_tag(str(rel), tag):
                continue
            subject_type = str(tag.get("subject_type") or "unknown").casefold().replace("-", "_")
            contains_person = tag.get("contains_person")
            person_confirmed = contains_person is True or subject_type in {
                "model_person",
                "person",
                "on_body_model",
                "model",
            }
            if (
                not path.exists()
                or not person_confirmed
                or not bool(tag.get("usable_for_identity", True))
            ):
                continue
            ranked.append(
                (
                    (
                        view_score.get(str(tag.get("view")), 5),
                        framing_score.get(str(tag.get("framing")), 5),
                        quality_score.get(str(tag.get("identity_quality")), 4),
                    ),
                    path,
                )
            )
        if ranked:
            return sorted(ranked, key=lambda item: (item[0], str(item[1]).casefold()))[0][1]
    return None


def reference_images_for_request(product_dir: Path, images: list[Path], contact_sheet: Path) -> list[Path]:
    selected = [contact_sheet]
    identity = candidate_model_reference(product_dir, images)
    if identity:
        selected.append(identity)
    tags = load_json(product_dir / "_aplus_creative_work" / "aigc_model_view_tags.json")
    product_refs = []
    for path in images:
        rel = str(path.relative_to(product_dir)).replace("\\", "/")
        tag = tags.get(rel) or tags.get(str(path.relative_to(product_dir)))
        if isinstance(tag, dict) and str(tag.get("subject_type") or "") in {"product_flatlay", "product_detail"}:
            product_refs.append(path)
    product_refs.sort(key=lambda path: (0 if path.relative_to(product_dir).parts[0].casefold() == "素材".casefold() else 1, str(path).casefold()))
    for path in product_refs[:2]:
        if path not in selected:
            selected.append(path)
    return selected[:4]


def compact_excel(excel: dict[str, Any] | None) -> str:
    if not excel:
        return "No local spreadsheet is available. Infer only clearly visible facts from the references and mark uncertain material claims as visual impressions."
    key_values = excel.get("key_values") or {}
    if key_values:
        return json.dumps(key_values, ensure_ascii=False, indent=2)[:12000]
    return json.dumps(excel.get("rows") or [], ensure_ascii=False, indent=2)[:12000]


def build_prompt(
    product_dir: Path,
    manifest: dict[str, Any],
    labels: list[str],
    identity: Path | None,
    tags: dict[str, Any],
    manual_baseline: dict[str, str],
) -> str:
    identity_rel = str(identity.relative_to(product_dir)) if identity else "No usable supplied identity reference found"
    tag_excerpt = json.dumps(tags, ensure_ascii=False, indent=2)[:10000]
    return f"""You are the product-analysis and creative-copy stage for the amazon-aplus-strict-model-placeholder-v4-7-2 workflow.
Use the attached contact sheet and reference images together with the spreadsheet facts below. Create one complete API-ready Amazon A+ creative brief in Markdown. Return Markdown only, without code fences or commentary.

PRODUCT ID
{product_dir.name}

SPREADSHEET FACTS
{compact_excel(manifest.get('excel'))}

REFERENCE INVENTORY
{chr(10).join(labels)}

VALIDATED MODEL VIEW TAGS
{tag_excerpt or '{}'}

PRESELECTED MODEL IDENTITY REFERENCE
{identity_rel}

HUMAN-ANALYZED SUGGESTED VISUAL BASELINE
{json.dumps(manual_baseline, ensure_ascii=False, indent=2)}

The Suggested Visual Baseline above was written by a human after inspecting this SKU's model and product images. Reproduce these five values faithfully. Do not replace them with a generic palette, generic studio background, or rule-combination baseline.

ROOT TEMPLATE FUNCTIONS
- Section 1: brand/banner hero with the supplied model wearing the actual product; fashion-editorial pose.
- Section 2: multiple angles of the same supplied model identity in one composition to explain fit and silhouette.
- Section 3: supplied model context plus front/back flat-lay product proof.
- Section 4: people-free collage of product details and macro construction views.
- Section 5: style-matched, text-free, people-free empty background for later influencer replacement. No influencer people, no selfies, no UGC/social UI, no color blocks, and no reference images.

GLOBAL DESIGN REQUIREMENTS
- Five modules, each 1464 x 600 px, full canvas 1464 x 3000 px.
- Poppins typography, premium Amazon apparel e-commerce, clean editorial streetwear, restrained brand-poster feeling.
- Do not add, enlarge, redesign, or use a standalone LOGO/wordmark/brand mark as a layout element. Preserve small logos, labels, embroidery, tags, patches, or brand details physically present on the actual garment.
- Preserve the exact garment color, fit, fabric impression, print, hardware, stitching, front/back differences, and construction visible in references.
- All renderable copy must follow marketplace language. US/UK/CA/AU use English; DE/AT/CH use German. Default to English when marketplace is absent.
- Shopper-facing copy only. Headlines are 3-6 words. Supporting copy is concise, benefit-led, and not prompt-like.
- Spreadsheet Section N Headline/Copy is authoritative only for that same Section N. Never move, reuse, paraphrase, or duplicate any supplied Section N text in another section. If an Excel Headline or Copy field is empty, generate that field normally.
- Use a distinct selling angle for each section. Do not repeat headlines or copy within this SKU.
- Do not use prohibited superlatives or compliance-risk claims such as Best, No.1, Perfect, Cheap, or Top-quality.
- Model Identity Lock: all Sections containing people must match the same supplied person. Never use a back-view image as the only identity reference.
- Never classify an image as a person/model merely because it is stored in a folder named 上身. Use the visual tags and visible image content; product-only flat lays are garment-accuracy references only.
- Treat the visible gender presentation of the selected identity reference as authoritative for target_gender. Keep spreadsheet Target customer as advisory metadata only. If they differ, preserve the supplied person, record the model-derived target_gender, and continue without a conflict pause or model swap. Use spreadsheet gender only when no usable model identity/gender is available.

REQUIRED MARKDOWN STRUCTURE
# A+ Creative Brief - {product_dir.name}

## Product Truth
- Brand:
- Marketplace:
- Product type:
- Target customer:
- Color:
- Fabric:
- Fit:
- Construction:
- Graphic / print / hardware:
- Verified features:

## Model Identity Lock
- model_identity_reference: {identity_rel}
- model_identity_notes: describe visible face, hair, skin tone, body type, age range, expression mood, and styling attitude from the supplied reference.
- model_identity_policy: All A+ model scenes must use this same supplied person; do not change ethnicity, gender presentation, face, hair, skin tone, or body type.

## Product Accuracy Notes
- Exact visual facts to preserve.

## Suggested Visual Baseline
Main color:
Supporting colors:
Background:
Texture:
Style balance:

## Target And Language
- target_gender:
- target_gender_source: model_identity_reference when visible model gender is usable; otherwise attribute_table_fallback.
- target_customer_reference: retain the spreadsheet value as advisory metadata only.
- marketplace:
- visible_copy_language:

## Section 1 - Brand Banner
Headline:
Copy:
Visual Direction:
Product Accuracy Notes:
Negative Prompt:

## Section 2 - Multi-Angle Fit
Headline:
Copy:
Visual Direction:
Product Accuracy Notes:
Negative Prompt:

## Section 3 - Model And Product Proof
Headline:
Copy:
Visual Direction:
Product Accuracy Notes:
Negative Prompt:

## Section 4 - Detail Macro
Headline:
Copy:
Visual Direction:
Product Accuracy Notes:
Negative Prompt:

## Section 5 - Influencer Replacement Background
Headline:
Copy:
Visual Direction: explicitly state text-free, people-free, style-matched empty background, no social UI, no color blocks, and NO REFERENCE IMAGES.
Product Accuracy Notes:
Negative Prompt:

Do not create a Text/Callouts field for any Section. That field is authored later by the main agent only after inspecting the planned layout, final upload-reference map, and the existing Headline, Copy, Visual Direction, and Product Accuracy; it must add supported, complementary information without duplication or conflict. Keep Section 5 Headline, Copy, and Product Accuracy Notes empty. Every Visual Direction must begin with the concrete composition task for its Section, then add product-specific art direction. Do not include local paths except the relative model_identity_reference field above."""


def response_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if not choices:
        return ""
    content = ((choices[0].get("message") or {}).get("content"))
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "\n".join(str(item.get("text", "")) for item in content if isinstance(item, dict)).strip()
    return ""


def clean_markdown(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:markdown|md)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    return text.strip() + "\n"


def enforce_manual_baseline(text: str, manual_baseline: dict[str, str]) -> str:
    """Insert the human-written baseline verbatim; the analysis model may not rewrite it."""
    required = ("Main color", "Supporting colors", "Background", "Texture", "Style balance")
    missing = [key for key in required if not str(manual_baseline.get(key) or "").strip()]
    if missing:
        raise RuntimeError("Missing human baseline fields: " + ", ".join(missing))
    block = "## Suggested Visual Baseline\n" + "\n".join(
        f"{key}: {str(manual_baseline[key]).strip()}" for key in required
    )
    pattern = re.compile(r"(?ims)^##\s+Suggested Visual Baseline\s*$.*?(?=^##\s+|\Z)")
    if pattern.search(text):
        return pattern.sub(block + "\n\n", text, count=1).strip() + "\n"
    anchor = re.search(r"(?im)^##\s+Target And Language\s*$", text)
    if anchor:
        return (text[: anchor.start()] + block + "\n\n" + text[anchor.start() :]).strip() + "\n"
    raise RuntimeError("Analysis-model response omitted the Suggested Visual Baseline placement anchor")


def valid_brief(text: str) -> bool:
    required = ["## Product Truth", "## Model Identity Lock"] + [f"## Section {i}" for i in range(1, 6)]
    return all(term in text for term in required)


def generate_brief(api_key: str, prompt: str, request_images: list[Path]) -> tuple[str, dict[str, Any]]:
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for path in request_images:
        content.append({"type": "image_url", "image_url": {"url": data_url(path)}})
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 5000,
        "temperature": 0.25,
    }
    last_error = ""
    for attempt in range(1, 4):
        try:
            response = requests.post(
                ENDPOINT,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=body,
                timeout=240,
            )
            payload = response.json()
            if response.status_code >= 400:
                raise RuntimeError(json.dumps(payload, ensure_ascii=False)[:1000])
            text = clean_markdown(response_text(payload))
            if not valid_brief(text):
                raise RuntimeError("Analysis-model response omitted required brief sections")
            return text, payload
        except Exception as exc:
            last_error = str(exc)
            if attempt < 3:
                time.sleep(5 * attempt)
    raise RuntimeError(f"Analysis-model brief generation failed after 3 attempts: {last_error}")


def product_dirs(root: Path) -> list[Path]:
    return [
        p
        for p in sorted(root.iterdir(), key=lambda p: p.name.casefold())
        if p.is_dir()
        and not p.name.startswith("_")
        and p.name not in {"LOGO", "输出结果"}
        and (p / "_aplus_work" / "product_summary.json").exists()
    ]


def main() -> int:
    global MODEL
    configure_stdout()
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--api-key", default=os.getenv("TOAPIS_API_KEY") or os.getenv("OPENAI_API_KEY"))
    parser.add_argument("--model", default=os.getenv("APLUS_ANALYSIS_MODEL") or MODEL)
    parser.add_argument("--product")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--baseline-file", required=True)
    args = parser.parse_args()
    MODEL = args.model
    if not args.api_key:
        raise SystemExit("Missing TOAPIS_API_KEY")
    root = Path(args.root).expanduser().resolve()
    baselines = load_json(Path(args.baseline_file).expanduser().resolve())
    selected = {x.strip() for x in args.product.split(",") if x.strip()} if args.product else None
    out = root / "_aplus_gemini_brief_summary.json"
    if out.exists():
        try:
            summary = load_json(out)
        except Exception:
            summary = {}
    else:
        summary = {}
    summary["root"] = str(root)
    summary["model"] = MODEL
    if not isinstance(summary.get("products"), dict):
        summary["products"] = {}
    for product_dir in product_dirs(root):
        if selected is not None and product_dir.name not in selected:
            continue
        work_dir = product_dir / "_aplus_creative_work"
        work_dir.mkdir(parents=True, exist_ok=True)
        brief_path = work_dir / "aplus_creative_brief.md"
        if brief_path.exists() and not args.overwrite:
            summary["products"][product_dir.name] = {"status": "exists", "brief": str(brief_path)}
            continue
        manifest = load_json(product_dir / "_aplus_work" / "product_summary.json")
        images = image_inventory(product_dir)
        contact_sheet = work_dir / "gemini_reference_contact_sheet.jpg"
        labels = create_contact_sheet(product_dir, images, contact_sheet)
        identity = candidate_model_reference(product_dir, images)
        tags_path = work_dir / "aigc_model_view_tags.json"
        tags = load_json(tags_path) if tags_path.exists() else {}
        tags = creative_eligible_tags(tags)
        manual_baseline = baselines.get(product_dir.name)
        if not isinstance(manual_baseline, dict) or len(manual_baseline) != 5:
            raise RuntimeError(f"Missing complete human baseline for {product_dir.name}")
        prompt = build_prompt(product_dir, manifest, labels, identity, tags, manual_baseline)
        request_images = reference_images_for_request(product_dir, images, contact_sheet)
        brief, raw = generate_brief(args.api_key, prompt, request_images)
        brief = enforce_manual_baseline(brief, manual_baseline)
        brief_path.write_text(brief, encoding="utf-8-sig")
        log_path = work_dir / "gemini_brief_generation.json"
        log_path.write_text(
            json.dumps(
                {
                    "model": MODEL,
                    "brief": str(brief_path),
                    "contact_sheet": str(contact_sheet),
                    "request_images": [str(p.relative_to(product_dir)) if p.is_relative_to(product_dir) else str(p) for p in request_images],
                    "response": raw,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        summary["products"][product_dir.name] = {
            "status": "written",
            "brief": str(brief_path),
            "identity_reference": str(identity.relative_to(product_dir)) if identity else None,
            "image_count": len(images),
        }
        print(json.dumps({"product": product_dir.name, **summary["products"][product_dir.name]}, ensure_ascii=False), flush=True)
    # Reconstruct the batch summary from per-product artifacts so interrupted or
    # deliberately per-SKU runs still finish with one complete root manifest.
    for product_dir in product_dirs(root):
        brief_path = product_dir / "_aplus_creative_work" / "aplus_creative_brief.md"
        log_path = product_dir / "_aplus_creative_work" / "gemini_brief_generation.json"
        if not brief_path.exists() or not log_path.exists():
            continue
        log = load_json(log_path)
        request_images = log.get("request_images") if isinstance(log.get("request_images"), list) else []
        summary["products"][product_dir.name] = {
            "status": "written",
            "brief": str(brief_path),
            "identity_reference": request_images[1] if len(request_images) > 1 else None,
            "image_count": len(image_inventory(product_dir)),
        }
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
