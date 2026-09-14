#!/usr/bin/env python
"""Sync main-agent-authored Visual Direction fields into the full A+ prompt."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime
from pathlib import Path


PAIR_RE = re.compile(
    r"(?ims)^\s*Layout task:\s*.+?^\s*Layout execution:\s*.+?(?=^\s*Product Accuracy\s*:)"
)
TASK_TO_ACCURACY_RE = re.compile(
    r"(?ims)^\s*Layout task:\s*.+?(?=^\s*Product Accuracy\s*:)"
)


def read_text(path: Path) -> tuple[str, bool]:
    raw = path.read_bytes()
    return raw.decode("utf-8-sig"), raw.startswith(b"\xef\xbb\xbf")


def write_text(path: Path, text: str, bom: bool) -> None:
    path.write_bytes(text.encode("utf-8-sig" if bom else "utf-8"))


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product-dir", required=True)
    args = parser.parse_args()

    product_dir = Path(args.product_dir).expanduser().resolve()
    work_dir = product_dir / "_aplus_creative_work"
    prompt_dir = work_dir / "module_prompts"
    full_prompt = work_dir / "aplus_full_prompt.txt"
    module_paths = sorted(prompt_dir.glob("section-*.txt"))
    if not module_paths:
        raise SystemExit(f"No module prompts found: {prompt_dir}")
    if not full_prompt.exists():
        raise SystemExit(f"Full prompt not found: {full_prompt}")

    manual_pairs: list[str] = []
    for path in module_paths:
        text, _ = read_text(path)
        matches = list(PAIR_RE.finditer(text))
        if len(matches) != 1:
            raise SystemExit(f"Expected one Layout task/execution pair in {path}, found {len(matches)}")
        manual_pairs.append(matches[0].group(0).strip())

    full_text, full_bom = read_text(full_prompt)
    full_matches = list(PAIR_RE.finditer(full_text))
    replacement_re = PAIR_RE
    if len(full_matches) != len(manual_pairs):
        draft_matches = list(TASK_TO_ACCURACY_RE.finditer(full_text))
        if len(draft_matches) != len(manual_pairs):
            raise SystemExit(
                f"Full prompt has {len(full_matches)} layout pairs and {len(draft_matches)} task drafts, "
                f"expected {len(manual_pairs)} from module prompts"
            )
        replacement_re = TASK_TO_ACCURACY_RE

    index = 0

    def replace_pair(_: re.Match[str]) -> str:
        nonlocal index
        value = manual_pairs[index]
        index += 1
        return value + "\n\n"

    updated = replacement_re.sub(replace_pair, full_text)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = work_dir / "manual_visual_direction_sync_backups" / stamp
    backup_dir.mkdir(parents=True, exist_ok=False)
    backup_path = backup_dir / full_prompt.name
    shutil.copy2(full_prompt, backup_path)
    before = full_prompt.read_bytes()
    write_text(full_prompt, updated, full_bom)
    after = full_prompt.read_bytes()
    report = {
        "schema_version": 1,
        "status": "completed",
        "timestamp": stamp,
        "product": product_dir.name,
        "source_module_prompts": [str(path) for path in module_paths],
        "full_prompt": str(full_prompt),
        "backup": str(backup_path),
        "sha256_before": digest(before),
        "sha256_after": digest(after),
        "pairs_synced": len(manual_pairs),
        "authorship_note": "This script copied existing fields verbatim and did not author layout content.",
    }
    report_path = work_dir / "manual_visual_direction_sync.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
