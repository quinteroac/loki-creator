from __future__ import annotations

import json
import mimetypes
import os
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4


SKILL_ID = "ffmpeg-audio-split"
ALLOWED_CLIP_DURATIONS = {3, 5, 7, 10, 15}
AUDIO_MIME_TYPES = {
    "audio/aac": ".aac",
    "audio/flac": ".flac",
    "audio/m4a": ".m4a",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/ogg": ".ogg",
    "audio/wav": ".wav",
    "audio/webm": ".webm",
    "audio/x-m4a": ".m4a",
    "audio/x-wav": ".wav",
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


def extension_for_mime_type(mime_type: str) -> str:
    if mime_type in AUDIO_MIME_TYPES:
        return AUDIO_MIME_TYPES[mime_type]
    return mimetypes.guess_extension(mime_type) or ".audio"


def resolve_artifact_src(src: str) -> Path | None:
    if not src.startswith("/api/artifacts/"):
        return None

    artifact_path = (artifacts_root() / src.removeprefix("/api/artifacts/")).resolve()
    try:
        artifact_path.relative_to(artifacts_root())
    except ValueError:
        return None

    return artifact_path if artifact_path.is_file() else None


def resolve_audio_source(src: str, destination: Path) -> tuple[Path, str] | None:
    artifact_path = resolve_artifact_src(src)
    if artifact_path is not None:
        return artifact_path, f"path:{artifact_path.resolve()}"

    return None


def asset_is_audio(asset: dict) -> bool:
    kind = first_text(asset.get("kind"))
    mime_type = first_text(asset.get("mimeType"))
    if kind == "audio":
        return True
    return kind == "source" and mime_type.startswith("audio/")


def snapshot_audio_sources(snapshot: dict) -> list[str]:
    sources: list[str] = []

    assets = snapshot.get("mediaAssets")
    if isinstance(assets, list):
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            if not asset_is_audio(asset):
                continue
            source = first_text(asset.get("src"))
            if source and source not in sources:
                sources.append(source)

    metadata = snapshot.get("metadata")
    if isinstance(metadata, dict) and first_text(metadata.get("kind")) == "audio":
        artifact_url = first_text(metadata.get("artifactUrl"))
        if artifact_url and artifact_url not in sources:
            sources.append(artifact_url)

    return sources


def materialize_selected_audio(payload: dict, inputs_dir: Path) -> Path | None:
    inputs_dir.mkdir(parents=True, exist_ok=True)
    selected = payload.get("selectedCardSnapshots")
    if not isinstance(selected, list):
        return None

    seen: set[str] = set()
    for snapshot_index, snapshot in enumerate(selected, start=1):
        if not isinstance(snapshot, dict):
            continue
        for source_index, src in enumerate(snapshot_audio_sources(snapshot), start=1):
            resolved = resolve_audio_source(src, inputs_dir / f"{snapshot_index:02d}-{source_index:02d}-audio")
            if resolved is None:
                continue
            path, key = resolved
            if key in seen:
                continue
            return path
    return None


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
        raise RuntimeError(f"Could not inspect audio {path}: {message}")
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


def audio_info(path: Path) -> dict:
    probe = ffprobe(path)
    audio_stream = first_stream(probe, "audio")
    if audio_stream is None:
        raise RuntimeError(f"Selected artifact is not an audio file: {path}")

    format_info = probe.get("format") if isinstance(probe.get("format"), dict) else {}
    duration = parse_duration(audio_stream.get("duration")) or parse_duration(format_info.get("duration"))
    if duration is None:
        raise RuntimeError(f"Could not read audio duration: {path}")

    return {
        "path": path,
        "duration": duration,
        "codec": first_text(audio_stream.get("codec_name")),
        "sampleRate": int(audio_stream.get("sample_rate") or 0),
        "channels": int(audio_stream.get("channels") or 0),
    }


def format_seconds(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".") or "0"


def parse_clip_duration(params: dict) -> int:
    raw_value = first_text(params.get("clipDurationSeconds"), params.get("durationSeconds"), params.get("duration"))
    try:
        duration = int(float(raw_value))
    except (TypeError, ValueError):
        raise RuntimeError("clipDurationSeconds must be one of: 3, 5, 7, 10, 15.") from None
    if duration not in ALLOWED_CLIP_DURATIONS:
        raise RuntimeError("clipDurationSeconds must be one of: 3, 5, 7, 10, 15.")
    return duration


def split_points(duration: float, clip_duration: int) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    start = 0.0
    while start < duration - 0.01:
        end = min(duration, start + clip_duration)
        if end - start > 0.01:
            points.append((start, end))
        start += clip_duration
    return points


def render_clip(source: Path, destination: Path, start: float, end: float) -> None:
    run_command(
        [
            "ffmpeg",
            "-y",
            "-ss",
            format_seconds(start),
            "-t",
            format_seconds(end - start),
            "-i",
            str(source),
            "-vn",
            "-ac",
            "2",
            "-ar",
            "48000",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(destination),
        ]
    )


def base_prompt(payload: dict) -> str:
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    return first_text(params.get("skillPrompt"), params.get("prompt"), params.get("outputText"), payload.get("prompt"))


def split_selected_audio(payload: dict) -> dict:
    require_tools()
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    clip_duration = parse_clip_duration(params)
    run_dir = output_dir(payload)
    inputs_dir = run_dir.parent / "inputs"

    audio_path = materialize_selected_audio(payload, inputs_dir)
    if audio_path is None:
        raise RuntimeError("ffmpeg-audio-split requires one selected audio card.")

    source_info = audio_info(audio_path)
    points = split_points(float(source_info["duration"]), clip_duration)
    if not points:
        raise RuntimeError(f"Selected audio is too short to split: {audio_path}")

    prompt = base_prompt(payload)
    base_title = first_text(params.get("title"), "Audio clip")
    artifacts: list[dict] = []

    for index, (start, end) in enumerate(points, start=1):
        output_path = run_dir / f"audio-clip-{index:03d}.m4a"
        render_clip(audio_path, output_path, start, end)
        output_info = audio_info(output_path)
        title = f"{base_title} {index:02d}"
        artifacts.append(
            {
                "path": str(output_path),
                "kind": "audio",
                "mimeType": "audio/mp4",
                "title": title,
                "prompt": prompt,
                "metadata": {
                    "clipIndex": index,
                    "clipCount": len(points),
                    "clipDurationSeconds": clip_duration,
                    "startSeconds": start,
                    "endSeconds": end,
                    "durationSeconds": output_info["duration"],
                    "sourceDurationSeconds": source_info["duration"],
                    "sourceAudio": str(audio_path),
                    "tags": [SKILL_ID],
                },
            }
        )

    return {"artifacts": artifacts}


def main() -> None:
    print(json.dumps(split_selected_audio(read_payload())))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ffmpeg-audio-split failed: {exc}", file=sys.stderr)
        sys.exit(1)
