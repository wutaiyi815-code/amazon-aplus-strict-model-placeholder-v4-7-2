#!/usr/bin/env python
"""Verify generated Amazon A+ module image counts and sizes."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


DEFAULT_EXPECTED_SIZE = (1464, 600)
DEFAULT_EXPECTED_COUNT = 6
SIZE_RE = re.compile(r"(\d{3,5})\s*[xX×*]\s*(\d{3,5})\s*px", re.IGNORECASE)
MODULE_COUNT_RE = re.compile(r"(?:页面拆分|拆分|模块数量|module\s*count).*?(\d+)", re.IGNORECASE)


def read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def expected_from_template(template: Path) -> tuple[int, tuple[int, int]]:
    if not template.exists():
        return DEFAULT_EXPECTED_COUNT, DEFAULT_EXPECTED_SIZE
    text = read_text(template)
    count = DEFAULT_EXPECTED_COUNT
    size = DEFAULT_EXPECTED_SIZE
    count_match = MODULE_COUNT_RE.search(text)
    if count_match:
        count = int(count_match.group(1))
    for line in text.splitlines():
        if any(label in line for label in ("单张模块尺寸", "module size", "Module size")):
            size_match = SIZE_RE.search(line)
            if size_match:
                size = (int(size_match.group(1)), int(size_match.group(2)))
                break
    return count, size


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Root folder containing product subfolders.")
    parser.add_argument("--pattern", help="Glob pattern for final modules. Defaults to *-<width>x<height>.png")
    parser.add_argument("--template", help="Template path. Defaults to <root>/模板.txt")
    parser.add_argument("--expected-count", type=int, help="Override expected module count.")
    parser.add_argument("--expected-width", type=int, help="Override expected module width.")
    parser.add_argument("--expected-height", type=int, help="Override expected module height.")
    parser.add_argument("--product", help="Optional exact SKU folder name.")
    args = parser.parse_args()

    try:
        from PIL import Image
    except ImportError as exc:
        raise SystemExit(f"Pillow is required: {exc}") from exc

    root = Path(args.root).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Root folder does not exist or is not a directory: {root}")

    template = Path(args.template).expanduser().resolve() if args.template else root / "模板.txt"
    expected_count, expected_size = expected_from_template(template)
    if args.expected_count:
        expected_count = args.expected_count
    if args.expected_width and args.expected_height:
        expected_size = (args.expected_width, args.expected_height)
    pattern = args.pattern or f"*-{expected_size[0]}x{expected_size[1]}.png"

    ok = True
    products = [
        p
        for p in root.iterdir()
        if p.is_dir()
        and (p / "_aplus_creative_work" / "module_prompts").exists()
        and (not args.product or p.name == args.product)
    ]
    for product_dir in sorted(products, key=lambda p: p.name.lower()):
        generated = product_dir / "_aplus_creative_work" / "generated_split"
        files = sorted(generated.glob(pattern)) if generated.exists() else []
        print(f"{product_dir.name}: {len(files)} final modules")
        if len(files) != expected_count:
            ok = False
        for path in files:
            size = Image.open(path).size
            print(f"  {path.name}: {size}")
            if size != expected_size:
                ok = False

    if not ok:
        raise SystemExit("Module verification failed.")
    print(f"All products have {expected_count} {expected_size[0]} x {expected_size[1]} modules.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
