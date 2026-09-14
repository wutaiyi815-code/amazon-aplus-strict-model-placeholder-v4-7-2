#!/usr/bin/env python
"""Create a contact sheet for one Amazon A+ product folder."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
SKIP_DIR_NAMES = {"_aplus_creative_work", "_aplus_work", "_influencer_selfie_work", "输出结果"}


def is_forbidden_root_model(path: Path, product_dir: Path, tags: dict[str, object]) -> bool:
    relative = path.relative_to(product_dir)
    if len(relative.parts) != 1:
        return False
    tag = tags.get(str(relative).replace("\\", "/")) or tags.get(str(relative))
    if not isinstance(tag, dict):
        return False
    subject = str(tag.get("subject_type") or "").casefold().replace("-", "_")
    return tag.get("contains_person") is True or subject == "model_person"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product-dir", required=True, help="Product folder containing reference images.")
    parser.add_argument("--output", help="Optional output image path.")
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--thumb-width", type=int, default=260)
    parser.add_argument("--thumb-height", type=int, default=320)
    args = parser.parse_args()

    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise SystemExit(f"Pillow is required to create contact sheets: {exc}") from exc

    product_dir = Path(args.product_dir).expanduser().resolve()
    if not product_dir.exists() or not product_dir.is_dir():
        raise SystemExit(f"Product folder does not exist or is not a directory: {product_dir}")

    tags_path = product_dir / "_aplus_creative_work" / "aigc_model_view_tags.json"
    try:
        tags = json.loads(tags_path.read_text(encoding="utf-8-sig")) if tags_path.exists() else {}
    except Exception:
        tags = {}

    images = sorted(
        [
            path
            for path in product_dir.rglob("*")
            if path.is_file()
            and path.suffix.lower() in IMAGE_EXTENSIONS
            and not any(part in SKIP_DIR_NAMES or part.startswith("_aplus") for part in path.relative_to(product_dir).parts[:-1])
            and not path.name.lower().startswith(("_manual_reference_contact_sheet", "reference_contact_sheet"))
            and not is_forbidden_root_model(path, product_dir, tags)
        ],
        key=lambda item: str(item.relative_to(product_dir)).lower(),
    )
    if not images:
        raise SystemExit(f"No reference images found in: {product_dir}")

    columns = max(1, args.columns)
    thumb_width = max(80, args.thumb_width)
    thumb_height = max(80, args.thumb_height)
    label_height = 34
    rows = (len(images) + columns - 1) // columns

    sheet = Image.new("RGB", (columns * thumb_width, rows * (thumb_height + label_height)), "white")
    draw = ImageDraw.Draw(sheet)

    for index, path in enumerate(images):
        image = Image.open(path).convert("RGB")
        image.thumbnail((thumb_width, thumb_height), Image.LANCZOS)
        cell_x = (index % columns) * thumb_width
        cell_y = (index // columns) * (thumb_height + label_height)
        x = cell_x + (thumb_width - image.width) // 2
        y = cell_y + (thumb_height - image.height) // 2
        sheet.paste(image, (x, y))
        label = str(path.relative_to(product_dir)).replace("\\", "/")
        draw.text((cell_x + 8, cell_y + thumb_height + 6), label[:48], fill=(0, 0, 0))

    output = Path(args.output).expanduser().resolve() if args.output else product_dir / "_aplus_work" / "reference_contact_sheet.jpg"
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, quality=92)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
