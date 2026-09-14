#!/usr/bin/env python
"""Prepare Amazon A+ prompt drafts from product folders."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from excel_reader import find_product_workbook, read_active_worksheet_rows

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
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


def read_text(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "utf-16"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def cell_to_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def read_excel_summary(path: Path) -> dict[str, Any]:
    try:
        sheet_name, worksheet_rows, dimensions = read_active_worksheet_rows(path)
    except Exception as exc:  # noqa: BLE001 - return useful manifest errors
        return {"path": str(path), "error": str(exc), "rows": [], "key_values": {}}

    rows: list[list[str]] = []
    key_values: dict[str, str] = {}

    for row in worksheet_rows:
        values = [cell_to_text(cell) for cell in row]
        if not any(values):
            continue
        rows.append(values)
        non_empty = [value for value in values if value]
        if len(non_empty) >= 2:
            key = non_empty[0].rstrip(":：")
            value = " / ".join(non_empty[1:])
            if key and value and key not in key_values:
                key_values[key] = value

    return {
        "path": str(path),
        "sheet": sheet_name,
        "dimensions": dimensions,
        "rows": rows[:80],
        "key_values": key_values,
        "row_count": len(rows),
    }


def find_images(product_dir: Path) -> list[Path]:
    return sorted(
        [
            path
            for path in product_dir.rglob("*")
            if path.is_file()
            and path.suffix.lower() in IMAGE_EXTENSIONS
            and not hard_excluded(path, product_dir)
            and "contact_sheet" not in path.name.lower()
        ],
        key=lambda item: str(item.relative_to(product_dir)).lower(),
    )


def find_excel(product_dir: Path) -> Path | None:
    return find_product_workbook(product_dir)


def product_manifest(product_dir: Path, template_path: Path | None) -> dict[str, Any]:
    excel_path = find_excel(product_dir)
    images = find_images(product_dir)
    logo_images = [path for path in images if "logo" in path.stem.lower()]

    manifest: dict[str, Any] = {
        "product_id": product_dir.name,
        "product_dir": str(product_dir),
        "template_path": str(template_path) if template_path else None,
        "excel_path": str(excel_path) if excel_path else None,
        "excel": read_excel_summary(excel_path) if excel_path else None,
        "images": [str(path) for path in images],
        "logo_images": [str(path) for path in logo_images],
        "image_count": len(images),
    }
    return manifest


def markdown_list(paths: list[str]) -> str:
    if not paths:
        return "- None found"
    return "\n".join(f"- `{path}`" for path in paths)


def excel_markdown(excel: dict[str, Any] | None) -> str:
    if not excel:
        return "No `1-产品属性表.xlsx` file found."
    if excel.get("error"):
        return f"Excel read error: {excel['error']}"
    key_values = excel.get("key_values") or {}
    if key_values:
        return "\n".join(f"- {key}: {value}" for key, value in key_values.items())
    rows = excel.get("rows") or []
    return "\n".join(f"- {' | '.join(row)}" for row in rows[:30])


def write_prompt_draft(
    product_dir: Path,
    manifest: dict[str, Any],
    template_excerpt: str,
) -> Path:
    work_dir = product_dir / "_aplus_work"
    generated_dir = work_dir / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)

    draft_path = work_dir / "aplus_prompt_draft.md"
    final_path = work_dir / "aplus_prompt_final.md"

    content = f"""# A+ Prompt Draft - {product_dir.name}

## Product Folder

`{product_dir}`

## Product Attributes From Excel

{excel_markdown(manifest.get("excel"))}

## Reference Images To Inspect

{markdown_list(manifest["images"])}

## Logo References

{markdown_list(manifest["logo_images"])}

## Visual Observations

Fill this section after inspecting every distinct reference image:

- Product category:
- Silhouette and fit:
- Neckline / sleeve / length:
- Fabric and texture:
- Colors:
- Graphic or print:
- Front / back / detail notes:
- Model styling:
- Scene and mood:
- Logo style:

## Template Excerpt

```text
{template_excerpt}
```

## Rewrite Instructions

Create `{final_path.name}` in this folder. Merge the template, Excel facts, and visual observations into a final Amazon A+ image-generation prompt.

Use 1464 x 3600 px, six 1464 x 600 px modules, premium Amazon apparel e-commerce style, streetwear attitude, accurate garment details, concise English copy, and a strong negative prompt.

For Headline and Copy, write shopper-facing Amazon A+ advertising language from this product's actual product_type, fit, fabric, color, and feature rows. Do not reuse fixed category sentences. Each section in the same SKU must have a distinct headline and distinct copy angle: hero/style, fit/silhouette, model-plus-flat-lay product proof, detail/material/construction, and lifestyle/background should not repeat the same selling sentence.
"""
    draft_path.write_text(content, encoding="utf-8-sig")
    return draft_path


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Root folder containing product subfolders.")
    parser.add_argument("--template", help="A+ template text file path. Defaults to <root>/模板.txt.")
    parser.add_argument("--template-excerpt-chars", type=int, default=6000)
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Root folder does not exist or is not a directory: {root}")

    template_path = Path(args.template).expanduser().resolve() if args.template else root / "模板.txt"
    template_text = ""
    if not template_path.exists():
        raise SystemExit(f"Template file does not exist: {template_path}")
    template_text = read_text(template_path)
    template_excerpt = template_text[: args.template_excerpt_chars].strip()

    batch: list[dict[str, Any]] = []
    product_dirs = [
        path
        for path in root.iterdir()
        if path.is_dir()
        and not path.name.startswith("_")
        and path.name.casefold() not in {"logo", "输出结果"}
        and find_product_workbook(path) is not None
    ]
    for product_dir in sorted(product_dirs, key=lambda item: item.name.lower()):
        manifest = product_manifest(product_dir, template_path)
        work_dir = product_dir / "_aplus_work"
        work_dir.mkdir(parents=True, exist_ok=True)
        draft_path = write_prompt_draft(product_dir, manifest, template_excerpt)
        manifest["draft_prompt_path"] = str(draft_path)
        manifest["final_prompt_path"] = str(work_dir / "aplus_prompt_final.md")
        (work_dir / "product_summary.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        batch.append(manifest)

    batch_manifest = {
        "root": str(root),
        "template_path": str(template_path) if template_path else None,
        "product_count": len(batch),
        "products": batch,
    }
    output_path = root / "_aplus_batch_manifest.json"
    output_path.write_text(json.dumps(batch_manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Prepared {len(batch)} product folders.")
    print(f"Batch manifest: {output_path}")
    for product in batch:
        print(f"- {product['product_id']}: {product['image_count']} images -> {product['draft_prompt_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
