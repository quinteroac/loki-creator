from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


sys.path.insert(0, str(repo_root() / "backend"))

from app.models import SeedanceVideoGenerationRequest  # noqa: E402
from app.services.seedance_video import SeedanceVideoGenerationService  # noqa: E402


def first_text(*values: object) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def read_payload() -> dict[str, Any]:
    raw = sys.stdin.read()
    return json.loads(raw) if raw.strip() else {}


def main() -> None:
    payload = read_payload()
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    prompt = first_text(params.get("prompt"), params.get("skillPrompt"), payload.get("prompt"))
    aspect_ratio = first_text(params.get("aspectRatio"), "16:9")
    duration_text = first_text(params.get("duration"), "5")
    try:
        duration = int(duration_text)
    except ValueError:
        duration = 5

    request = SeedanceVideoGenerationRequest.model_validate({
        "prompt": prompt,
        "aspectRatio": aspect_ratio,
        "duration": duration,
        "selectedCardSnapshots": payload.get("selectedCardSnapshots") if isinstance(payload.get("selectedCardSnapshots"), list) else [],
        "attachments": payload.get("attachments") if isinstance(payload.get("attachments"), list) else [],
        "context": payload.get("context") if isinstance(payload.get("context"), dict) else {},
    })
    service = SeedanceVideoGenerationService(repo_root() / ".loki")
    response = service.generate(request)
    print(json.dumps({"cards": [card.model_dump(mode="json", by_alias=True) for card in response.cards]}))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
