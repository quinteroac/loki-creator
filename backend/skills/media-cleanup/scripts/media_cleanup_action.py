from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path
from uuid import uuid4


SKILL_ID = "media-cleanup"
ALLOWED_OPERATIONS = {"blur-regions", "cover-regions", "crop"}
IMAGE_MIME_TYPES = {
    "image/gif": ".gif",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
VIDEO_MIME_TYPES = {
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
    "video/x-matroska": ".mkv",
}
FORBIDDEN_TERMS = {
}


def read_payload() -> dict:
    raw_payload = sys.stdin.read()
    if not raw_payload.strip():
        return {}
    return json.loads(raw_payload)


def first_text(*values: object) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def artifacts_root() -> Path:
    return Path(os.environ.get("LOKI_ARTIFACTS_ROOT", repo_root() / ".loki")).resolve()


def safe_slug(value: str, fallback: str) -> str:
    slug = "".join(character if character.isalnum() or character in {"-", "_"} else "-" for character in value.lower())
    slug = "-".join(part for part in slug.split("-") if part)
    return slug[:80] or fallback


def output_dir(payload: dict) -> Path:
    run_id = first_text(payload.get("runId"), f"skill_run_{uuid4().hex}")
    skill_id = first_text(payload.get("skillId"), SKILL_ID)
    path = artifacts_root() / "skills" / skill_id / safe_slug(run_id, "run") / "outputs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def parse_data_url(data_url: str) -> tuple[str, bytes]:
    header, separator, encoded = data_url.partition(",")
    if separator != "," or not header.startswith("data:"):
        raise ValueError("invalid data URL")
    if ";base64" not in header:
        raise ValueError("only base64 data URLs are supported")
    mime_type = header[5:].split(";", 1)[0] or "application/octet-stream"
    return mime_type, base64.b64decode(encoded)


def extension_for_mime_type(mime_type: str) -> str:
    if mime_type in IMAGE_MIME_TYPES:
        return IMAGE_MIME_TYPES[mime_type]
    if mime_type in VIDEO_MIME_TYPES:
        return VIDEO_MIME_TYPES[mime_type]
    return mimetypes.guess_extension(mime_type) or ".bin"


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_text.lower()


def contains_forbidden_term(text: str) -> bool:
    for term in FORBIDDEN_TERMS:
        escaped = re.escape(term)
        if " " in term:
            if re.search(rf"(?<!\w){escaped}s?(?!\w)", text):
                return True
            continue
        if re.search(rf"\b{escaped}s?\b", text):
            return True
    return False


def assert_allowed_request(payload: dict, params: dict) -> None:
    text_values = [
        payload.get("prompt"),
        params.get("skillPrompt"),
        params.get("prompt"),
        params.get("outputText"),
        params.get("body"),
        params.get("reason"),
    ]
    request_text = "\n".join(value for value in text_values if isinstance(value, str))
    normalized = normalize_text(request_text)


def resolve_artifact_src(src: str) -> Path | None:
    if not src.startswith("/api/artifacts/"):
        return None

    artifact_path = (artifacts_root() / src.removeprefix("/api/artifacts/")).resolve()
    try:
        artifact_path.relative_to(artifacts_root())
    except ValueError:
        return None

    return artifact_path if artifact_path.is_file() else None


def write_data_url_media(data_url: str, destination: Path) -> tuple[Path, str] | None:
    mime_type, data = parse_data_url(data_url)
    if not (mime_type.startswith("image/") or mime_type.startswith("video/")):
        return None
    path = destination.with_suffix(extension_for_mime_type(mime_type))
    path.write_bytes(data)
    return path, mime_type


def resolve_media_source(src: str, destination: Path, fallback_mime_type = "") -> tuple[Path, str, str] | None:
    artifact_path = resolve_artifact_src(src)
    if artifact_path is not None:
        mime_type = fallback_mime_type or mimetypes.guess_type(artifact_path.name)[0] or ""
        return artifact_path, mime_type, f"path:{artifact_path.resolve()}"

    if src.startswith("data:image/") or src.startswith("data:video/"):
        written = write_data_url_media(src, destination)
        if written is None:
            return None
        path, mime_type = written
        digest = hashlib.sha256(src.encode("utf-8")).hexdigest()
        return path, mime_type, f"data:{digest}"

    return None


def asset_media_kind(asset: dict) -> str | None:
    kind = first_text(asset.get("kind"))
    mime_type = first_text(asset.get("mimeType"))
    if kind in {"image", "video"}:
        return kind
    if kind == "source":
        if mime_type.startswith("image/"):
            return "image"
        if mime_type.startswith("video/"):
            return "video"
    return None


def snapshot_media_sources(snapshot: dict) -> list[tuple[str, str]]:
    sources: list[tuple[str, str]] = []

    assets = snapshot.get("mediaAssets")
    if isinstance(assets, list):
        for asset in assets:
            if not isinstance(asset, dict) or asset_media_kind(asset) is None:
                continue
            mime_type = first_text(asset.get("mimeType"))
            for source in (first_text(asset.get("src")), first_text(asset.get("dataUrl"))):
                if source:
                    sources.append((source, mime_type))

    metadata = snapshot.get("metadata")
    if isinstance(metadata, dict):
        kind = first_text(metadata.get("kind"))
        artifact_url = first_text(metadata.get("artifactUrl"))
        if kind in {"image", "video"} and artifact_url:
            sources.append((artifact_url, ""))

    return sources


def attachment_media_sources(attachment: dict) -> list[tuple[str, str]]:
    kind = first_text(attachment.get("kind"))
    mime_type = first_text(attachment.get("mimeType"))
    data_url = first_text(attachment.get("dataUrl"))
    if attachment.get("omitted") or not data_url:
        return []
    if kind in {"image", "video"} or mime_type.startswith(("image/", "video/")):
        return [(data_url, mime_type)]
    return []


def materialize_selected_media(payload: dict, inputs_dir: Path) -> tuple[Path, str, str]:
    inputs_dir.mkdir(parents=True, exist_ok=True)

    selected = payload.get("selectedCardSnapshots")
    if isinstance(selected, list):
        for snapshot_index, snapshot in enumerate(selected, start=1):
            if not isinstance(snapshot, dict):
                continue
            for source_index, (src, mime_type) in enumerate(snapshot_media_sources(snapshot), start=1):
                resolved = resolve_media_source(src, inputs_dir / f"{snapshot_index:02d}-{source_index:02d}-media", mime_type)
                if resolved is None:
                    continue
                path, resolved_mime_type, key = resolved
                return path, resolved_mime_type, key

    attachments = payload.get("attachments")
    if isinstance(attachments, list):
        for attachment_index, attachment in enumerate(attachments, start=1):
            if not isinstance(attachment, dict):
                continue
            for source_index, (src, mime_type) in enumerate(attachment_media_sources(attachment), start=1):
                resolved = resolve_media_source(src, inputs_dir / f"attachment-{attachment_index:02d}-{source_index:02d}", mime_type)
                if resolved is None:
                    continue
                path, resolved_mime_type, key = resolved
                return path, resolved_mime_type, key

    raise RuntimeError("media-cleanup requires one selected or attached image/video artifact.")


def require_tools() -> None:
    missing = [tool for tool in ("ffmpeg", "ffprobe") if shutil.which(tool) is None]
    if missing:
        raise RuntimeError(f"Missing required tool(s): {', '.join(missing)}")


def run_command(command: list[str]) -> None:
    process = subprocess.run(command, text=True, capture_output=True, check=False)
    if process.returncode != 0:
        message = process.stderr.strip() or process.stdout.strip() or "command failed"
        raise RuntimeError(f"{command[0]} failed: {message[-2000:]}")


def ffprobe(path: Path) -> dict:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        str(path),
    ]
    process = subprocess.run(command, text=True, capture_output=True, check=False)
    if process.returncode != 0:
        message = process.stderr.strip() or process.stdout.strip() or "ffprobe failed"
        raise RuntimeError(f"Could not inspect selected media {path}: {message}")
    return json.loads(process.stdout or "{}")


def parse_duration(value: object) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def first_stream(probe: dict, codec_type: str) -> dict | None:
    streams = probe.get("streams")
    if not isinstance(streams, list):
        return None
    for stream in streams:
        if isinstance(stream, dict) and stream.get("codec_type") == codec_type:
            return stream
    return None


def media_info(path: Path) -> dict:
    probe = ffprobe(path)
    video_stream = first_stream(probe, "video")
    if video_stream is None:
        raise RuntimeError(f"Selected artifact is not an image or video: {path}")

    format_info = probe.get("format") if isinstance(probe.get("format"), dict) else {}
    duration = parse_duration(video_stream.get("duration")) or parse_duration(format_info.get("duration"))
    width = int(video_stream.get("width") or 0)
    height = int(video_stream.get("height") or 0)
    if width <= 0 or height <= 0:
        raise RuntimeError(f"Could not read media dimensions: {path}")

    return {
        "path": path,
        "width": width,
        "height": height,
        "duration": duration,
        "has_audio": first_stream(probe, "audio") is not None,
    }


def positive_float(value: object, fallback: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback


def parse_operation(params: dict) -> str:
    operation = first_text(params.get("operation"), params.get("mode"))
    if operation not in ALLOWED_OPERATIONS:
        raise RuntimeError("operation must be one of: blur-regions, cover-regions, crop.")
    return operation


def parse_regions_json(value: object) -> object:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"regionsJson must be valid JSON: {exc.msg}") from exc
    if isinstance(value, (dict, list)):
        return value
    raise RuntimeError("regionsJson is required.")


def parse_regions(params: dict, operation: str) -> list[dict]:
    raw_regions = parse_regions_json(params.get("regionsJson", params.get("regionJson")))
    if isinstance(raw_regions, dict):
        regions = [raw_regions]
    elif isinstance(raw_regions, list):
        regions = raw_regions
    else:
        raise RuntimeError("regionsJson must be a rectangle object or a list of rectangles.")

    if operation == "crop" and len(regions) != 1:
        raise RuntimeError("crop requires exactly one rectangle.")
    if operation != "crop" and not regions:
        raise RuntimeError(f"{operation} requires at least one rectangle.")
    if not all(isinstance(region, dict) for region in regions):
        raise RuntimeError("Each region must be a JSON object.")
    return regions


def number_field(region: dict, field: str) -> float:
    try:
        return float(region[field])
    except KeyError:
        raise RuntimeError(f"Region is missing '{field}'.") from None
    except (TypeError, ValueError):
        raise RuntimeError(f"Region field '{field}' must be numeric.") from None


def rect_to_pixels(region: dict, width: int, height: int) -> dict[str, int]:
    x = number_field(region, "x")
    y = number_field(region, "y")
    rect_width = number_field(region, "width")
    rect_height = number_field(region, "height")
    unit = first_text(region.get("unit")).lower()
    if not unit:
        unit = "relative" if max(abs(x), abs(y), abs(rect_width), abs(rect_height)) <= 1.0 else "pixels"
    if unit not in {"relative", "normalized", "percent", "pixels", "px"}:
        raise RuntimeError("Region unit must be 'relative' or 'pixels'.")

    if unit in {"relative", "normalized", "percent"}:
        x *= width
        y *= height
        rect_width *= width
        rect_height *= height

    left = max(0, min(width - 1, round(x)))
    top = max(0, min(height - 1, round(y)))
    right = max(left + 1, min(width, round(x + rect_width)))
    bottom = max(top + 1, min(height, round(y + rect_height)))
    pixel_width = right - left
    pixel_height = bottom - top
    if pixel_width <= 0 or pixel_height <= 0:
        raise RuntimeError("Region resolves to an empty rectangle.")
    return {"x": left, "y": top, "width": pixel_width, "height": pixel_height}


def even(value: int) -> int:
    return max(2, value - (value % 2))


def escape_filter_color(color: str) -> str:
    if re.fullmatch(r"#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?", color):
        return f"0x{color[1:]}"
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9_@.]*", color):
        return color
    raise RuntimeError("coverColor must be a simple ffmpeg color name or hex color.")


def format_seconds(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".") or "0"


def blur_radii_for_rect(rect: dict[str, int], requested_radius: float) -> tuple[float, float]:
    max_luma_radius = max(1.0, min(rect["width"], rect["height"]) / 2.0 - 1.0)
    max_chroma_radius = max(0.0, min(rect["width"], rect["height"]) / 4.0 - 1.0)
    luma_radius = min(requested_radius, max_luma_radius)
    chroma_radius = min(luma_radius, max_chroma_radius)
    return luma_radius, chroma_radius


def is_video_source(path: Path, mime_type: str, info: dict) -> bool:
    if mime_type.startswith("video/"):
        return True
    if mime_type.startswith("image/"):
        return False
    if path.suffix.lower() in {".mp4", ".mov", ".webm", ".mkv"}:
        return True
    if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        return False
    return info.get("duration") is not None


def render_with_simple_filter(source: Path, destination: Path, filter_value: str, video: bool, has_audio: bool) -> None:
    command = ["ffmpeg", "-y", "-i", str(source)]
    if video:
        command.extend(["-map", "0:v:0"])
        if has_audio:
            command.extend(["-map", "0:a?"])
        command.extend(
            [
                "-vf",
                f"{filter_value},format=yuv420p",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "18",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
                str(destination),
            ]
        )
    else:
        command.extend(["-frames:v", "1", "-vf", filter_value, str(destination)])
    run_command(command)


def render_with_blur_filter(
    source: Path,
    destination: Path,
    rects: list[dict[str, int]],
    *,
    video: bool,
    has_audio: bool,
    radius: float,
) -> None:
    filters: list[str] = []
    current = "[0:v]"
    for index, rect in enumerate(rects):
        base = f"[base{index}]"
        blurbase = f"[blurbase{index}]"
        patch = f"[patch{index}]"
        output = f"[v{index}]"
        luma_radius, chroma_radius = blur_radii_for_rect(rect, radius)
        filters.append(f"{current}split=2{base}{blurbase}")
        filters.append(
            f"{blurbase}crop={rect['width']}:{rect['height']}:{rect['x']}:{rect['y']},"
            f"boxblur=luma_radius={format_seconds(luma_radius)}:luma_power=1:"
            f"chroma_radius={format_seconds(chroma_radius)}:chroma_power=1{patch}"
        )
        filters.append(f"{base}{patch}overlay={rect['x']}:{rect['y']}{output}")
        current = output

    output_label = "[outv]"
    if video:
        filters.append(f"{current}format=yuv420p{output_label}")
    else:
        filters.append(f"{current}format=rgb24{output_label}")

    command = ["ffmpeg", "-y", "-i", str(source), "-filter_complex", ";".join(filters), "-map", output_label]
    if video:
        if has_audio:
            command.extend(["-map", "0:a?"])
        command.extend(
            [
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "18",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
                str(destination),
            ]
        )
    else:
        command.extend(["-frames:v", "1", str(destination)])
    run_command(command)


def render_cleanup(source: Path, destination: Path, operation: str, rects: list[dict[str, int]], params: dict, info: dict, video: bool) -> None:
    if operation == "crop":
        rect = rects[0]
        width = even(rect["width"]) if video else rect["width"]
        height = even(rect["height"]) if video else rect["height"]
        filter_value = f"crop={width}:{height}:{rect['x']}:{rect['y']},setsar=1"
        render_with_simple_filter(source, destination, filter_value, video, bool(info["has_audio"]))
        return

    if operation == "cover-regions":
        color = escape_filter_color(first_text(params.get("coverColor"), "black"))
        filters = [
            f"drawbox=x={rect['x']}:y={rect['y']}:w={rect['width']}:h={rect['height']}:color={color}:t=fill"
            for rect in rects
        ]
        render_with_simple_filter(source, destination, ",".join(filters), video, bool(info["has_audio"]))
        return

    blur_radius = positive_float(params.get("blurRadius"), 18.0)
    render_with_blur_filter(source, destination, rects, video=video, has_audio=bool(info["has_audio"]), radius=blur_radius)


def base_prompt(payload: dict) -> str:
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    return first_text(params.get("skillPrompt"), params.get("prompt"), params.get("outputText"), payload.get("prompt"))


def cleanup_selected_media(payload: dict) -> dict:
    require_tools()
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    assert_allowed_request(payload, params)
    operation = parse_operation(params)
    regions = parse_regions(params, operation)
    run_dir = output_dir(payload)
    inputs_dir = run_dir.parent / "inputs"

    source_path, mime_type, source_key = materialize_selected_media(payload, inputs_dir)
    info = media_info(source_path)
    video = is_video_source(source_path, mime_type, info)
    width = int(info["width"])
    height = int(info["height"])
    rects = [rect_to_pixels(region, width, height) for region in regions]
    extension = ".mp4" if video else ".png"
    output_path = run_dir / f"cleaned-media{extension}"
    render_cleanup(source_path, output_path, operation, rects, params, info, video)
    output_info = media_info(output_path)

    prompt = base_prompt(payload)
    default_title = "Cleaned video" if video else "Cleaned image"
    return {
        "artifacts": [
            {
                "path": str(output_path),
                "kind": "video" if video else "image",
                "mimeType": "video/mp4" if video else "image/png",
                "title": first_text(params.get("title"), default_title),
                "prompt": prompt,
                "metadata": {
                    "operation": operation,
                    "regions": rects,
                    "sourceMedia": str(source_path),
                    "sourceKey": source_key,
                    "sourceWidth": width,
                    "sourceHeight": height,
                    "width": int(output_info["width"]),
                    "height": int(output_info["height"]),
                    "durationSeconds": output_info["duration"],
                    "safetyBoundary": "no-watermark-logo-signature-credit-attribution-removal",
                    "tags": [SKILL_ID],
                    "preferredAspectRatio": "auto",
                },
            }
        ],
        "diagnostics": [
            {
                "level": "info",
                "message": "Created a non-destructive cleaned copy. Watermark, logo, signature, credit, copyright, provenance, platform mark, and attribution removal is intentionally unsupported.",
            }
        ],
    }


def main() -> None:
    print(json.dumps(cleanup_selected_media(read_payload())))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"media-cleanup failed: {exc}", file=sys.stderr)
        sys.exit(1)
