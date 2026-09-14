from __future__ import annotations

import argparse
import getpass
import io
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps


UPLOAD_URL = "https://toapis.com/v1/uploads/images"
GENERATE_URL = "https://toapis.com/v1/images/generations"
DEFAULT_BACKOFF = [15, 30, 60, 120, 240]
SHORT_BACKOFF = [5, 10, 20]


def configure_stdout() -> None:
    try:
        import sys

        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass


def normalize_api_key(value: str | None) -> str:
    if value and value.strip():
        return value.strip()
    return getpass.getpass("Enter ToAPIs/OpenAI-compatible API key: ").strip()


def request_with_retry(label: str, request_fn: Any, backoff: list[int] | None = None) -> Any:
    waits = backoff or SHORT_BACKOFF
    last_error = ""
    for attempt in range(1, len(waits) + 2):
        try:
            response = request_fn()
            if response.status_code >= 500 or response.status_code in {408, 409, 425, 429}:
                raise RuntimeError(f"HTTP {response.status_code}: {response.text[:500]}")
            if response.status_code >= 400:
                raise RuntimeError(f"HTTP {response.status_code}: {response.text[:1000]}")
            return response
        except Exception as exc:
            last_error = str(exc)
            if attempt <= len(waits):
                wait_time = waits[attempt - 1]
                print(f"  {label} attempt {attempt} failed: {last_error}. Retrying in {wait_time}s.")
                time.sleep(wait_time)
            else:
                raise RuntimeError(f"{label} failed after retries: {last_error}") from exc
    raise RuntimeError(f"{label} failed after retries: {last_error}")


def preprocess_image(image_path: Path, max_side: int = 1600) -> tuple[io.BytesIO, str]:
    img = Image.open(image_path).convert("RGB")
    img = ImageOps.exif_transpose(img)
    img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    stream = io.BytesIO()
    img.save(stream, format="JPEG", quality=92, optimize=True)
    stream.seek(0)
    return stream, "image/jpeg"


def upload_image(requests_mod: Any, api_key: str, image_path: Path) -> str:
    print(f"  Uploading reference: {image_path.name}", flush=True)

    def post_upload() -> Any:
        stream, content_type = preprocess_image(image_path)
        files = {"file": (image_path.name, stream, content_type)}
        return requests_mod.post(UPLOAD_URL, headers={"Authorization": api_key}, files=files, timeout=60)

    response = request_with_retry(f"upload {image_path.name}", post_upload)
    body = response.json()
    url = body.get("data", {}).get("url") or body.get("url")
    if not url:
        raise RuntimeError(f"Upload returned no URL for {image_path}: {body}")
    return url


def poll_generation(
    requests_mod: Any,
    api_key: str,
    task_id: str,
    timeout_seconds: int,
    queued_timeout_seconds: int,
) -> str:
    poll_url = f"{GENERATE_URL}/{task_id}"
    start = time.time()
    queued_start: float | None = None
    while time.time() - start < timeout_seconds:
        response = request_with_retry(
            f"poll {task_id}",
            lambda: requests_mod.get(poll_url, headers={"Authorization": api_key}, timeout=30),
        )
        body = response.json()
        status = body.get("status")
        if status == "completed":
            result_url = body.get("url") or body.get("result", {}).get("data", [{}])[0].get("url")
            if result_url:
                return result_url
            raise RuntimeError(f"Completed task did not return an image URL: {body}")
        if status == "failed":
            raise RuntimeError(f"Generation failed: {body}")
        progress = body.get("progress", 0)
        if status == "queued" and progress == 0:
            queued_start = queued_start or time.time()
            if time.time() - queued_start >= queued_timeout_seconds:
                raise TimeoutError(f"Task {task_id} stayed queued at 0% for {queued_timeout_seconds}s")
        else:
            queued_start = None
        print(f"    polling {task_id}: {status} {progress}%")
        time.sleep(5)
    raise TimeoutError(f"Timed out polling task {task_id}")


def postprocess_to_4x5(source_bytes: bytes, raw_path: Path, final_path: Path, target: tuple[int, int]) -> None:
    final_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(source_bytes)
    img = Image.open(io.BytesIO(source_bytes)).convert("RGB")
    scale = max(target[0] / img.width, target[1] / img.height)
    resized = img.resize((round(img.width * scale), round(img.height * scale)), Image.Resampling.LANCZOS)
    left = max(0, (resized.width - target[0]) // 2)
    top = max(0, (resized.height - target[1]) // 2)
    cropped = resized.crop((left, top, left + target[0], top + target[1]))
    cropped.save(final_path, quality=95)


def append_failure(plan_path: Path, occasion_name: str, prompt_path: Path, error: str, retries: int) -> None:
    failure_path = plan_path.parent / "generation_failures.md"
    with failure_path.open("a", encoding="utf-8") as f:
        f.write(f"\n## {datetime.now().isoformat(timespec='seconds')}\n")
        f.write(f"- Occasion: {occasion_name}\n")
        f.write(f"- Prompt: {prompt_path.name}\n")
        f.write(f"- Retries: {retries}\n")
        f.write(f"- Error: {error}\n")


def generate_one(
    requests_mod: Any,
    api_key: str,
    plan_path: Path,
    item: dict[str, Any],
    prompt_path: Path,
    image_urls: list[str],
    size: str,
    resolution: str,
    target: tuple[int, int],
    poll_timeout: int,
    queued_timeout: int,
    overwrite: bool,
) -> bool:
    final_path = Path(item["output_path"])
    raw_path = final_path.with_name(final_path.stem + "-raw.png")
    if final_path.exists() and not overwrite:
        print(f"  Exists, skipped: {final_path.name}")
        return True
    prompt = prompt_path.read_text(encoding="utf-8")
    last_error = ""
    for attempt in range(1, len(DEFAULT_BACKOFF) + 2):
        try:
            print(f"  Submitting generation: {prompt_path.name} (attempt {attempt})", flush=True)
            payload: dict[str, Any] = {
                "model": "gpt-image-2",
                "prompt": prompt,
                "size": size,
                "resolution": resolution,
                "response_format": "url",
                "image_urls": image_urls,
            }
            response = request_with_retry(
                f"submit generation {prompt_path.name}",
                lambda: requests_mod.post(GENERATE_URL, json=payload, headers={"Authorization": api_key}, timeout=60),
            )
            body = response.json()
            task_id = body.get("id") or body.get("task_id")
            if not task_id:
                raise RuntimeError(f"Generation API returned no task id: {body}")
            result_url = poll_generation(requests_mod, api_key, task_id, poll_timeout, queued_timeout)
            image_response = request_with_retry(
                f"download result {prompt_path.name}",
                lambda: requests_mod.get(result_url, timeout=120),
            )
            postprocess_to_4x5(image_response.content, raw_path, final_path, target)
            print(f"  Saved: {final_path}")
            return True
        except Exception as exc:
            last_error = str(exc)
            if attempt <= len(DEFAULT_BACKOFF):
                wait_time = DEFAULT_BACKOFF[attempt - 1]
                print(f"  Attempt {attempt} failed: {last_error}. Retrying in {wait_time}s.")
                time.sleep(wait_time)
            else:
                print(f"  Failed after retries: {prompt_path.name}: {last_error}")
                append_failure(plan_path, item.get("name", ""), prompt_path, last_error, len(DEFAULT_BACKOFF))
                return False
    return False


def main() -> int:
    configure_stdout()
    parser = argparse.ArgumentParser(description="Generate influencer selfie images through ToAPIs gpt-image-2.")
    parser.add_argument("--root", required=True)
    parser.add_argument("--api-key")
    parser.add_argument("--size", default="4:5")
    parser.add_argument("--resolution", default="2K")
    parser.add_argument("--target-width", type=int, default=1080)
    parser.add_argument("--target-height", type=int, default=1350)
    parser.add_argument("--poll-timeout", type=int, default=600)
    parser.add_argument("--queued-timeout", type=int, default=60)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    try:
        import requests
    except ImportError as exc:
        raise SystemExit(f"requests is required: {exc}") from exc

    api_key = normalize_api_key(args.api_key or os.environ.get("TOAPIS_API_KEY") or os.environ.get("OPENAI_API_KEY"))
    root = Path(args.root).expanduser().resolve()
    target = (args.target_width, args.target_height)

    for plan_path in sorted(root.glob("*/_influencer_selfie_work/selfie_plan.json")):
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        print(f"\nProduct: {plan.get('product_id')}")
        image1 = Path(plan.get("front_model_reference", ""))
        if not image1.exists():
            print(f"  Missing Image 1, skipped product: {image1}")
            continue
        cache: dict[str, str] = {}
        for item in plan.get("occasions", []):
            prompt_path = Path(item.get("prompt_path", ""))
            image2 = Path(item.get("background_reference", ""))
            print(f"- Occasion: {item.get('index')} {item.get('name')}")
            if not prompt_path.exists() or not image2.exists():
                print("  Missing prompt or Image 2, skipped.")
                continue
            image_urls = []
            for ref in [image1, image2]:
                key = str(ref)
                if key not in cache:
                    cache[key] = upload_image(requests, api_key, ref)
                    print(f"  Uploaded reference: {ref.name}")
                image_urls.append(cache[key])
            generate_one(
                requests,
                api_key,
                plan_path,
                item,
                prompt_path,
                image_urls,
                args.size,
                args.resolution,
                target,
                args.poll_timeout,
                args.queued_timeout,
                args.overwrite,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
