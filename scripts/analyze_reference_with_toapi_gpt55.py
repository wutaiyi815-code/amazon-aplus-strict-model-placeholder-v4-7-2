"""Analyze text and reference images with ToAPIs GPT-5.5.

This utility is intentionally small: it gives the skill a second analysis
backend without changing the image-generation provider code.
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
from pathlib import Path
from typing import Any

import requests


ENDPOINT = "https://toapis.com/v1/chat/completions"


def data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def image_content(path_or_url: str) -> dict[str, Any]:
    if path_or_url.lower().startswith(("http://", "https://", "data:")):
        url = path_or_url
    else:
        url = data_url(Path(path_or_url).expanduser().resolve())
    return {"type": "image_url", "image_url": {"url": url}}


def response_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(parts)
    return ""


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-key", default=os.getenv("TOAPIS_API_KEY") or os.getenv("OPENAI_API_KEY"))
    parser.add_argument("--model", default="gpt-5.5")
    parser.add_argument("--prompt", default="Analyze these product and model reference images for Amazon A+ planning. Describe garment color, silhouette, print/detail, fabric impression, model identity cues, pose, background mood, and suitable visual baseline. Keep the answer concise.")
    parser.add_argument("--image", action="append", default=[], help="Local image path. May be passed multiple times.")
    parser.add_argument("--image-url", action="append", default=[], help="Public URL or data URL. May be passed multiple times.")
    parser.add_argument("--max-tokens", type=int, default=600)
    parser.add_argument("--out", help="Optional JSON output path for the raw API response.")
    args = parser.parse_args()

    if not args.api_key:
        raise SystemExit("Missing API key. Pass --api-key or set TOAPIS_API_KEY.")

    content: list[dict[str, Any]] = [{"type": "text", "text": args.prompt}]
    for item in [*args.image, *args.image_url]:
        content.append(image_content(item))

    payload = {
        "model": args.model,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": args.max_tokens,
    }
    response = requests.post(
        ENDPOINT,
        headers={"Authorization": f"Bearer {args.api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=120,
    )
    try:
        response_payload = response.json()
    except ValueError:
        response.raise_for_status()
        raise
    if response.status_code >= 400:
        raise SystemExit(json.dumps(response_payload, ensure_ascii=False, indent=2))

    if args.out:
        out_path = Path(args.out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(response_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(response_text(response_payload) or json.dumps(response_payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
