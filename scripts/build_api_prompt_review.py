#!/usr/bin/env python
"""Build a readable, de-duplicated review of exact API-submitted prompts."""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path


def read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def prompt_blocks(text: str) -> list[str]:
    return [block.strip() for block in re.split(r"\n\s*\n", text.strip()) if block.strip()]


def build_review(product_dir: Path) -> Path | None:
    prompt_dir = product_dir / "_aplus_creative_work" / "api_submitted_prompts"
    prompt_files = sorted(prompt_dir.glob("section-*.txt"))
    if not prompt_files:
        return None

    module_blocks = {path.name: prompt_blocks(read_text(path)) for path in prompt_files}
    occurrences: dict[str, list[str]] = defaultdict(list)
    for module_name, blocks in module_blocks.items():
        for block in dict.fromkeys(blocks):
            occurrences[block].append(module_name)

    repeated = {
        block: modules
        for block, modules in occurrences.items()
        if len(modules) >= 2
    }
    out_lines = [
        f"# API Prompt Review - {product_dir.name}",
        "",
        "This review is assembled from the exact prompt files written immediately before API submission.",
        "Repeated blocks are shown once below; each module section retains only its unique blocks.",
        "",
        "## Shared Prompt Blocks",
        "",
    ]
    if repeated:
        ordered_repeated = sorted(
            repeated.items(),
            key=lambda item: (-len(item[1]), item[1][0], item[0].casefold()),
        )
        for index, (block, modules) in enumerate(ordered_repeated, 1):
            out_lines.extend(
                [
                    f"### Shared Block {index}",
                    f"Applies to: {', '.join(modules)}",
                    "",
                    block,
                    "",
                ]
            )
    else:
        out_lines.extend(["No exact repeated prompt blocks were found.", ""])

    out_lines.extend(["## Per-Module Unique Prompt Content", ""])
    for module_name, blocks in module_blocks.items():
        out_lines.extend([f"### {module_name}", ""])
        unique_blocks = [block for block in blocks if block not in repeated]
        if unique_blocks:
            for block in unique_blocks:
                out_lines.extend([block, ""])
        else:
            out_lines.extend(["All blocks for this module are listed in Shared Prompt Blocks.", ""])

    out_path = product_dir / "_aplus_creative_work" / "api_prompt_review_deduplicated.md"
    out_path.write_text("\n".join(out_lines).rstrip() + "\n", encoding="utf-8-sig")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product-dir", required=True)
    args = parser.parse_args()
    path = build_review(Path(args.product_dir).expanduser().resolve())
    if not path:
        raise SystemExit("No API-submitted prompt files found.")
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

