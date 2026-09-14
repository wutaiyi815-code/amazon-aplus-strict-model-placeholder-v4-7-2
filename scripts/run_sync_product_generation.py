#!/usr/bin/env python3
"""Run exactly one SKU generation synchronously with status and timeout cleanup."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def update_status(root: Path, product: str, status: str, **details: Any) -> None:
    path = root / "_aplus_sync_run_status.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        data = {}
    data.setdefault("schema_version", 1)
    data["updated_at"] = now_iso()
    entry = data.setdefault("products", {}).setdefault(product, {})
    entry["generation"] = {"status": status, "updated_at": now_iso(), **details}
    atomic_json(path, data)


def terminate_tree(process: subprocess.Popen[Any]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], check=False, capture_output=True, text=True)
    else:
        try:
            os.killpg(process.pid, 15)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=15)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--template-analysis")
    parser.add_argument("--provider", choices=("gpt-toapi", "gpt-rh"), required=True)
    parser.add_argument("--product", required=True, help="Exactly one direct-child SKU folder name")
    parser.add_argument("--size", default="21:9")
    parser.add_argument("--resolution", default="2K")
    parser.add_argument("--model", default="gpt-image-2")
    parser.add_argument("--quality", choices=("low", "medium", "high"), default="medium")
    parser.add_argument("--module")
    parser.add_argument("--max-reference-images", type=int, default=0)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if not args.product.strip() or "," in args.product:
        raise SystemExit("--product must contain exactly one SKU; comma-separated or whole-root generation is forbidden")
    root = Path(args.root).expanduser().resolve()
    product_dir = root / args.product
    if not product_dir.is_dir() or product_dir.parent.resolve() != root.resolve():
        raise SystemExit(f"Product is not an exact direct-child directory: {args.product}")
    generator = Path(__file__).with_name("generate_modules_toapi.py")
    template = Path(args.template_analysis).expanduser().resolve() if args.template_analysis else root / "_aplus_creative_template_analysis.json"
    command = [
        sys.executable, str(generator), "--root", str(root), "--template-analysis", str(template),
        "--provider", args.provider, "--product", args.product, "--size", args.size,
        "--resolution", args.resolution, "--quality", args.quality,
        "--max-reference-images", str(args.max_reference_images),
    ]
    if args.provider == "gpt-toapi":
        command.extend(["--model", args.model])
    if args.module:
        command.extend(["--module", args.module])
    if args.overwrite:
        command.append("--overwrite")

    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    popen_kwargs: dict[str, Any] = {"env": env, "creationflags": creationflags}
    if os.name != "nt":
        popen_kwargs["start_new_session"] = True
    update_status(root, args.product, "running", provider=args.provider, quality=args.quality, timeout_seconds=args.timeout_seconds)
    process = subprocess.Popen(command, **popen_kwargs)
    try:
        return_code = process.wait(timeout=args.timeout_seconds)
    except subprocess.TimeoutExpired:
        terminate_tree(process)
        update_status(root, args.product, "timed_out", provider=args.provider, quality=args.quality, pid=process.pid, timeout_seconds=args.timeout_seconds)
        raise SystemExit(124)
    except KeyboardInterrupt:
        terminate_tree(process)
        update_status(root, args.product, "interrupted", provider=args.provider, quality=args.quality, pid=process.pid)
        raise
    if return_code != 0:
        update_status(root, args.product, "failed", provider=args.provider, quality=args.quality, return_code=return_code)
        return return_code
    update_status(root, args.product, "completed", provider=args.provider, quality=args.quality, return_code=0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
