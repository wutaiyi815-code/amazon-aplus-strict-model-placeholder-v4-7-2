#!/usr/bin/env python
"""Durable, atomic state helpers for one-SKU A+ generation."""

from __future__ import annotations

import json
import errno
import os
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator


STATE_FILENAME = "generation_state.json"
LOCK_FILENAME = "generation_state.lock"
TERMINAL_MODULE_STATES = {"completed", "failed", "skipped_existing"}
TERMINAL_PRODUCT_STATES = {"completed", "completed_with_errors", "failed", "stopped"}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def state_path(product_dir: Path) -> Path:
    return product_dir / "_aplus_creative_work" / STATE_FILENAME


def parse_timestamp(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).timestamp()
    except (TypeError, ValueError):
        return None


@contextmanager
def _state_lock(product_dir: Path, timeout_seconds: float = 15.0) -> Iterator[None]:
    work_dir = product_dir / "_aplus_creative_work"
    work_dir.mkdir(parents=True, exist_ok=True)
    lock_path = work_dir / LOCK_FILENAME
    handle = lock_path.open("a+b")
    acquired = False
    start = time.monotonic()
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            while time.monotonic() - start < timeout_seconds:
                try:
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    acquired = True
                    break
                except OSError:
                    time.sleep(0.05)
        else:
            import fcntl

            while time.monotonic() - start < timeout_seconds:
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                    break
                except BlockingIOError:
                    time.sleep(0.05)
        if not acquired:
            raise TimeoutError(f"Timed out locking generation state: {lock_path}")
        yield
    finally:
        if acquired:
            try:
                if os.name == "nt":
                    import msvcrt

                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        handle.close()


def load_state(product_dir: Path) -> dict[str, Any]:
    path = state_path(product_dir)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    deadline = time.monotonic() + 5.0
    delay = 0.05
    while True:
        try:
            os.replace(temp_path, path)
            return
        except OSError as exc:
            winerror = getattr(exc, "winerror", None)
            transient_access_conflict = isinstance(exc, PermissionError) or winerror in {5, 32, 33} or exc.errno in {
                errno.EACCES,
                errno.EPERM,
            }
            if not transient_access_conflict or time.monotonic() >= deadline:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass
                raise
            time.sleep(delay)
            delay = min(delay * 1.7, 0.5)


def update_product_state(product_dir: Path, *, progress: bool = True, **fields: Any) -> dict[str, Any]:
    with _state_lock(product_dir):
        data = load_state(product_dir)
        data.setdefault("schema_version", 1)
        data.setdefault("product_id", product_dir.name)
        data.setdefault("created_at", now_iso())
        data.setdefault("modules", {})
        data.update(fields)
        data["updated_at"] = now_iso()
        if progress:
            data["last_progress_at"] = data["updated_at"]
        _atomic_write(state_path(product_dir), data)
        return data


def update_module_state(
    product_dir: Path,
    module_name: str,
    *,
    progress: bool = True,
    **fields: Any,
) -> dict[str, Any]:
    with _state_lock(product_dir):
        data = load_state(product_dir)
        data.setdefault("schema_version", 1)
        data.setdefault("product_id", product_dir.name)
        data.setdefault("created_at", now_iso())
        modules = data.setdefault("modules", {})
        module = modules.setdefault(module_name, {"module": module_name, "created_at": now_iso()})
        module.update(fields)
        module["updated_at"] = now_iso()
        data["current_module"] = module_name
        data["updated_at"] = module["updated_at"]
        if progress:
            module["last_progress_at"] = module["updated_at"]
            data["last_progress_at"] = module["updated_at"]
        _atomic_write(state_path(product_dir), data)
        return module


def module_state(product_dir: Path, module_name: str) -> dict[str, Any]:
    data = load_state(product_dir)
    modules = data.get("modules")
    if not isinstance(modules, dict):
        return {}
    value = modules.get(module_name)
    return value if isinstance(value, dict) else {}


def current_module_state(data: dict[str, Any]) -> dict[str, Any]:
    current = data.get("current_module")
    modules = data.get("modules")
    if not current or not isinstance(modules, dict):
        return {}
    value = modules.get(str(current))
    return value if isinstance(value, dict) else {}
