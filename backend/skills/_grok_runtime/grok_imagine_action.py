from __future__ import annotations

import base64
import json
import mimetypes
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from uuid import uuid4


XAI_BASE_URL = "https://api.x.ai"
DEFAULT_IMAGE_MODEL = "grok-imagine-image-quality"
DEFAULT_VIDEO_MODEL = "grok-imagine-video"
IMAGE_MIME_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/jpg": ".jpg", "image/webp": ".webp"}
VIDEO_MIME_TYPES = {"video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov"}


def read_payload() -> dict[str, Any]:
    raw = sys.stdin.read()
    return json.loads(raw) if raw.strip() else {}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def artifacts_root() -> Path:
    return Path(os.environ.get("LOKI_ARTIFACTS_ROOT", repo_root() / ".loki")).resolve()


def output_dir(payload: dict[str, Any]) -> Path:
    run_id = first_text(payload.get("runId"), f"skill_run_{uuid4().hex}")
    skill_id = first_text(payload.get("skillId"), "grok-imagine")
    path = artifacts_root() / "skills" / skill_id / run_id / "outputs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_artifact_src(src: str) -> Path | None:
    if not src.startswith("/api/artifacts/"):
        return None

    artifact_path = (artifacts_root() / src.removeprefix("/api/artifacts/")).resolve()
    try:
        artifact_path.relative_to(artifacts_root())
    except ValueError:
        return None

    return artifact_path if artifact_path.is_file() else None


def image_path_to_data_url(path: Path) -> str:
    mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
    if not mime_type.startswith("image/"):
        raise RuntimeError(f"Selected artifact is not an image: {path}")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def normalize_image_source(src: str) -> str:
    artifact_path = resolve_artifact_src(src)
    if artifact_path is not None:
        return image_path_to_data_url(artifact_path)

    path = Path(src).expanduser().resolve()
    try:
        path.relative_to(artifacts_root())
    except ValueError as exc:
        raise RuntimeError(f"Grok image inputs must be local Loki artifacts, got: {src[:80]}") from exc
    if not path.is_file():
        raise RuntimeError(f"Grok image input path does not exist: {path}")
    return image_path_to_data_url(path)


def first_text(*values: object) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def as_int(value: object) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def base_prompt(payload: dict[str, Any]) -> str:
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    return first_text(params.get("prompt"), params.get("skillPrompt"), params.get("outputText"), payload.get("prompt"))


def grok_auth_token_from_cache() -> str | None:
    if os.environ.get("PI_GROK_BUILD_DISABLE_GROK_AUTH_CACHE") == "1":
        return None

    auth_path = Path.home() / ".grok" / "auth.json"
    if not auth_path.is_file():
        return None

    try:
        data = json.loads(auth_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    now = time.time()
    for cache_key, entry in data.items():
        if not isinstance(entry, dict):
            continue
        issuer = first_text(entry.get("oidc_issuer"), str(cache_key).split("::", 1)[0])
        token = first_text(entry.get("key"))
        if issuer != "https://auth.x.ai" or not token:
            continue
        expires_at = first_text(entry.get("expires_at"))
        if not expires_at:
            return token
        try:
            # ISO timestamps from Grok are UTC with a Z suffix.
            expires = datetime.fromisoformat(expires_at.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return token
        if expires > now:
            return token

    return None


def xai_api_key() -> str:
    key = first_text(os.environ.get("XAI_API_KEY"), os.environ.get("GROK_CODE_XAI_API_KEY"), grok_auth_token_from_cache())
    if not key:
        raise RuntimeError(
            "xAI auth not found. Set XAI_API_KEY or GROK_CODE_XAI_API_KEY, or run grok login so ~/.grok/auth.json has a valid auth.x.ai token."
        )
    return key


def request_json(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Authorization": f"Bearer {xai_api_key()}"}
    if body is not None:
        headers["Content-Type"] = "application/json"

    request = Request(f"{XAI_BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"xAI API returned HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"xAI API request failed: {exc.reason}") from exc


def download_url(url: str, destination: Path, fallback_mime: str) -> tuple[Path, str]:
    request = Request(url, headers={"User-Agent": "loki-creator"})
    with urlopen(request, timeout=300) as response:
        content_type = response.headers.get_content_type() or fallback_mime
        extension = (
            IMAGE_MIME_TYPES.get(content_type)
            or VIDEO_MIME_TYPES.get(content_type)
            or mimetypes.guess_extension(content_type)
            or mimetypes.guess_extension(fallback_mime)
            or ".bin"
        )
        path = destination.with_suffix(extension)
        path.write_bytes(response.read())
        return path, content_type


def write_b64_json(encoded: str, destination: Path, mime_type: str = "image/png") -> Path:
    extension = IMAGE_MIME_TYPES.get(mime_type) or ".png"
    path = destination.with_suffix(extension)
    path.write_bytes(base64.b64decode(encoded))
    return path


def selected_image_inputs(payload: dict[str, Any], limit: int = 3) -> list[str]:
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    inputs: list[str] = []

    def add_input(source: str) -> None:
        if len(inputs) >= limit:
            return
        if source.startswith("data:"):
            raise RuntimeError("Grok image inputs must be local Loki artifact paths; inline dataUrl is not an executable media input.")
        normalized = normalize_image_source(source)
        if normalized and normalized not in inputs:
            inputs.append(normalized)

    for references in (params.get("localMediaReferences"), context.get("localMediaReferences")):
        if isinstance(references, list):
            for reference in references:
                if isinstance(reference, dict) and first_text(reference.get("kind")) == "image":
                    add_input(first_text(reference.get("path"), reference.get("artifactUrl")))

    explicit = first_text(params.get("image"), params.get("imageUrl"), params.get("imageDataUrl"))
    if explicit:
        add_input(explicit)

    explicit_images = params.get("images") or params.get("imageUrls") or params.get("imageDataUrls")
    if isinstance(explicit_images, list):
        for image in explicit_images:
            if isinstance(image, dict):
                add_input(first_text(image.get("src"), image.get("url"), image.get("path")))
            else:
                add_input(first_text(image))

    attachments = payload.get("attachments")
    if isinstance(attachments, list):
        for attachment in attachments:
            if isinstance(attachment, dict) and not attachment.get("omitted"):
                source = first_text(attachment.get("artifactUrl"), attachment.get("src"))
                if source:
                    add_input(source)

    snapshots = payload.get("selectedCardSnapshots")
    if not isinstance(snapshots, list):
        return inputs

    for snapshot in snapshots:
        if not isinstance(snapshot, dict):
            continue
        assets = snapshot.get("mediaAssets")
        if isinstance(assets, list):
            for asset in assets:
                if isinstance(asset, dict) and first_text(asset.get("kind")) == "image":
                    source = first_text(asset.get("src"))
                    if source:
                        add_input(source)
        metadata = snapshot.get("metadata")
        if isinstance(metadata, dict) and first_text(metadata.get("kind")) == "image":
            source = first_text(metadata.get("artifactUrl"))
            if source:
                add_input(source)

    return inputs


def selected_image_input(payload: dict[str, Any]) -> str:
    return next(iter(selected_image_inputs(payload, limit=1)), "")


def artifact(path: Path, kind: str, mime_type: str, prompt: str, title: str, metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": str(path),
        "kind": kind,
        "mimeType": mime_type,
        "title": title,
        "prompt": prompt,
        "metadata": metadata,
    }


def imagine_image(payload: dict[str, Any]) -> dict[str, Any]:
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    prompt = base_prompt(payload)
    if not prompt:
        raise RuntimeError("Grok Imagine image generation requires a prompt.")

    image_inputs = selected_image_inputs(payload)
    request_body: dict[str, Any] = {
        "model": first_text(params.get("model"), DEFAULT_IMAGE_MODEL),
        "prompt": prompt,
    }
    n = as_int(params.get("n"))
    if n is not None:
        request_body["n"] = n
    aspect_ratio = first_text(params.get("aspectRatio"), params.get("aspect_ratio"))
    if aspect_ratio:
        request_body["aspect_ratio"] = aspect_ratio
    resolution = first_text(params.get("resolution"), "1k")
    if resolution:
        request_body["resolution"] = resolution

    endpoint = "/v1/images/edits" if image_inputs else "/v1/images/generations"
    if len(image_inputs) == 1:
        request_body["image"] = {"url": image_inputs[0], "type": "image_url"}
    elif len(image_inputs) > 1:
        request_body["images"] = [{"url": image_input, "type": "image_url"} for image_input in image_inputs[:3]]
    response_format = first_text(
        params.get("responseFormat"),
        params.get("response_format"),
        "" if image_inputs else "b64_json",
    )
    if response_format:
        request_body["response_format"] = response_format

    data = request_json("POST", endpoint, request_body)
    images = data.get("data") if isinstance(data.get("data"), list) else []
    if not images:
        raise RuntimeError("xAI image response did not include any images.")

    out_dir = output_dir(payload)
    artifacts: list[dict[str, Any]] = []
    for index, image in enumerate(images, start=1):
        if not isinstance(image, dict):
            continue
        destination = out_dir / f"grok-image-{index:02d}"
        if first_text(image.get("b64_json")):
            path = write_b64_json(first_text(image.get("b64_json")), destination)
            mime_type = "image/png"
        elif first_text(image.get("url")):
            path, mime_type = download_url(first_text(image.get("url")), destination, "image/png")
        else:
            continue
        artifacts.append(
            artifact(
                path,
                "image",
                mime_type,
                prompt,
                "Grok Imagine image",
                {
                    "provider": "xai",
                    "model": request_body["model"],
                    "aspectRatio": aspect_ratio,
                    "resolution": resolution,
                    "source": "image-edit" if image_inputs else "text-to-image",
                    "inputImageCount": len(image_inputs),
                    "revisedPrompt": image.get("revised_prompt"),
                },
            )
        )

    if not artifacts:
        raise RuntimeError("xAI image response did not include downloadable image data.")

    return {"artifacts": artifacts}


def poll_video(request_id: str, interval_ms: int, timeout_ms: int) -> dict[str, Any]:
    deadline = time.time() + (timeout_ms / 1000)
    last: dict[str, Any] = {}
    while time.time() <= deadline:
        last = request_json("GET", f"/v1/videos/{quote(request_id)}")
        status = first_text(last.get("status"))
        if status in {"done", "expired", "failed"}:
            return last
        time.sleep(max(interval_ms, 250) / 1000)
    raise RuntimeError(f"Timed out waiting for xAI video generation after {timeout_ms}ms.")


def imagine_video(payload: dict[str, Any]) -> dict[str, Any]:
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    prompt = base_prompt(payload)
    if not prompt:
        raise RuntimeError("Grok Imagine video generation requires a prompt.")

    request_body: dict[str, Any] = {
        "model": first_text(params.get("model"), DEFAULT_VIDEO_MODEL),
        "prompt": prompt,
    }
    image_input = selected_image_input(payload)
    if image_input:
        request_body["image"] = {"url": image_input}
    duration = as_int(params.get("duration"))
    if duration is not None:
        request_body["duration"] = duration
    aspect_ratio = first_text(params.get("aspectRatio"), params.get("aspect_ratio"))
    if aspect_ratio:
        request_body["aspect_ratio"] = aspect_ratio
    resolution = first_text(params.get("resolution"), "720p")
    if resolution:
        request_body["resolution"] = resolution

    started = request_json("POST", "/v1/videos/generations", request_body)
    request_id = first_text(started.get("request_id"))
    if not request_id:
        raise RuntimeError("xAI video response did not include request_id.")

    poll = params.get("poll")
    if poll is False or first_text(poll).lower() == "false":
        return {
            "text": json.dumps({"status": "pending", "request_id": request_id}, indent=2),
            "metadata": {"requestId": request_id, "status": "pending"},
        }

    status = poll_video(
        request_id,
        as_int(params.get("pollIntervalMs")) or 5000,
        as_int(params.get("pollTimeoutMs")) or 10 * 60 * 1000,
    )
    if first_text(status.get("status")) == "failed":
        error = status.get("error") if isinstance(status.get("error"), dict) else {}
        message = first_text(error.get("message") if isinstance(error, dict) else "", error.get("code") if isinstance(error, dict) else "")
        raise RuntimeError(message or "xAI video generation failed.")
    if first_text(status.get("status")) == "expired":
        raise RuntimeError("xAI video generation expired before a video was available.")

    video = status.get("video") if isinstance(status.get("video"), dict) else {}
    url = first_text(video.get("url") if isinstance(video, dict) else "")
    if not url:
        raise RuntimeError("xAI video response did not include a video URL.")

    path, mime_type = download_url(url, output_dir(payload) / "grok-video", "video/mp4")
    return {
        "artifacts": [
            artifact(
                path,
                "video",
                mime_type,
                prompt,
                "Grok Imagine video",
                {
                    "provider": "xai",
                    "model": request_body["model"],
                    "requestId": request_id,
                    "status": first_text(status.get("status")),
                    "duration": video.get("duration") if isinstance(video, dict) else duration,
                    "aspectRatio": aspect_ratio,
                    "resolution": resolution,
                    "source": "image-to-video" if image_input else "text-to-video",
                },
            )
        ]
    }


def main() -> None:
    payload = read_payload()
    skill_id = first_text(payload.get("skillId"))
    if skill_id == "grok-imagine-image":
        result = imagine_image(payload)
    elif skill_id == "grok-imagine-video":
        result = imagine_video(payload)
    else:
        raise RuntimeError(f"Unsupported Grok Imagine skill: {skill_id}")
    print(json.dumps(result))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
