from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ABS_PATH_RE = re.compile(r"`?[A-Za-z]:\\[^`\n\r]+`?")
CJK_RE = re.compile(
    r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3040-\u30ff\uac00-\ud7af]"
)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8-sig")


def section_index_from_prompt(path: Path) -> int | None:
    match = re.search(r"section-0?(\d+)", path.name, re.IGNORECASE)
    return int(match.group(1)) if match else None


def is_placeholder_instruction(instruction: str) -> bool:
    lowered = instruction.lower()
    placeholder_terms = (
        "占位符",
        "色块",
        "等大色块",
        "等大的色块",
        "placeholder",
        "color block",
        "color blocks",
    )
    return any(term in lowered for term in placeholder_terms)


def is_no_influencer_instruction(instruction: str) -> bool:
    lowered = instruction.lower()
    no_influencer_terms = (
        "不需要生成网红图",
        "无需生成网红图",
        "并不需要生成网红图",
        "不生成网红图",
        "用于后续替换为网红图",
        "后续替换为网红图",
    )
    return any(term in lowered for term in no_influencer_terms)


def influencer_section_indices(analysis: dict[str, Any]) -> list[int]:
    indices: list[int] = []
    for module in analysis.get("modules", []):
        instruction = str(module.get("instruction", ""))
        if is_placeholder_instruction(instruction) or is_no_influencer_instruction(instruction):
            continue
        if "网红图" in instruction or "网红" in instruction.lower() or "influencer" in instruction.lower() or "ugc" in instruction.lower():
            indices.append(int(module.get("index", 0)))
    return sorted(set(index for index in indices if index > 0))


def sanitize_for_generation(text: str) -> str:
    text = ABS_PATH_RE.sub("[attached reference image]", text)
    text = CJK_RE.sub("", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def influencer_images(product_dir: Path) -> list[Path]:
    generated = product_dir / "_influencer_selfie_work" / "generated"
    if not generated.exists():
        return []
    return sorted(path for path in generated.glob("*-4x5.png") if "-raw" not in path.stem)


def append_influencer_instruction(prompt_path: Path, images: list[Path], section_instruction: str) -> None:
    text = read_text(prompt_path)
    image_list = "\n".join(f"- attached influencer reference {idx + 1}: {path.name}" for idx, path in enumerate(images))
    clean_instruction = sanitize_for_generation(section_instruction)
    addition = f"""

Influencer UGC reference integration:
- The root template page presentation asks this section to use influencer UGC content: {clean_instruction}
- Use the attached influencer selfie images as real UGC-style layout/reference images for this section.
- Treat these influencer images as the primary photo tiles or screenshot-style content inside this A+ module, not as random mood references.
- Build a clean Amazon A+ composition around them: collage grid, video-screenshot rhythm, small labels only if useful, consistent page typography, and enough spacing.
- Preserve the product appearance shown in the influencer images and product references.
- Do not redraw the section as a studio-only module; this section should visibly read as influencer UGC / social proof styling.
- Any visible text in the generated image must be English only. Do not render Chinese characters, CJK characters, bilingual labels, file paths, or prompt metadata.

Influencer reference image files to attach for this module:
{image_list}
"""
    if "Influencer UGC reference integration:" not in text:
        write_text(prompt_path, text.rstrip() + "\n" + addition)


def main() -> int:
    parser = argparse.ArgumentParser(description="Attach generated influencer selfie images to A+ modules whose template instructions mention 网红图.")
    parser.add_argument("--root", required=True)
    parser.add_argument("--template-analysis", required=True)
    parser.add_argument("--max-images-per-section", type=int, default=5)
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    analysis = read_json(Path(args.template_analysis).expanduser().resolve())
    target_indices = influencer_section_indices(analysis)
    modules_by_index = {int(m.get("index", 0)): str(m.get("instruction", "")) for m in analysis.get("modules", [])}
    summary: dict[str, Any] = {
        "root": str(root),
        "influencer_section_indices": target_indices,
        "products": {},
    }

    for product_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        prompt_dir = product_dir / "_aplus_creative_work" / "module_prompts"
        if not prompt_dir.exists():
            continue
        images = influencer_images(product_dir)[: args.max_images_per_section]
        reference_path = product_dir / "_aplus_creative_work" / "module_reference_images.json"
        mapping: dict[str, list[str]] = {}
        if reference_path.exists():
            try:
                existing = json.loads(reference_path.read_text(encoding="utf-8"))
                if isinstance(existing, dict):
                    mapping = {
                        str(key): [str(item) for item in value]
                        for key, value in existing.items()
                        if isinstance(value, list)
                    }
            except json.JSONDecodeError:
                mapping = {}
        product_summary: dict[str, Any] = {
            "influencer_images": [str(path) for path in images],
            "modules": {},
        }
        for prompt_path in sorted(prompt_dir.glob("*.txt")):
            index = section_index_from_prompt(prompt_path)
            if index in target_indices:
                if images:
                    append_influencer_instruction(prompt_path, images, modules_by_index.get(index, ""))
                    mapping[prompt_path.name] = [str(path) for path in images]
                    product_summary["modules"][prompt_path.name] = {
                        "section_index": index,
                        "references": [str(path) for path in images],
                    }
                else:
                    product_summary["modules"][prompt_path.name] = {
                        "section_index": index,
                        "references": [],
                        "warning": "No generated influencer images found for this product.",
                    }
        if mapping:
            reference_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
            product_summary["module_reference_images"] = str(reference_path)
        summary["products"][product_dir.name] = product_summary

    out_path = root / "_aplus_influencer_section_injection.json"
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
