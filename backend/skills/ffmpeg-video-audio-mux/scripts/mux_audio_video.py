from __future__ import annotations

import json
import mimetypes
import os
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4


SKILL_ID = "ffmpeg-video-audio-mux"
VIDEO_MIME_TYPES = {
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
    "video/x-matroska": ".mkv",
}
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


def extension_for_mime_type(mime_type: str, kind: str) -> str:
    if kind == "video" and mime_type in VIDEO_MIME_TYPES:
        return VIDEO_MIME_TYPES[mime_type]
    if kind == "audio" and mime_type in AUDIO_MIME_TYPES:
        return AUDIO_MIME_TYPES[mime_type]
    fallback = ".mp4" if kind == "video" else ".audio"
    return mimetypes.guess_extension(mime_type) or fallback


def resolve_artifact_src(src: str) -> Path | None:
    if not src.startswith("/api/artifacts/"):
        return None

    artifact_path = (artifacts_root() / src.removeprefix("/api/artifacts/")).resolve()
    try:
        artifact_path.relative_to(artifacts_root())
    except ValueError:
        return None

    return artifact_path if artifact_path.is_file() else None


def resolve_media_source(src: str, destination: Path, kind: str) -> tuple[Path, str] | None:
    artifact_path = resolve_artifact_src(src)
    if artifact_path is not None:
        return artifact_path, f"path:{artifact_path.resolve()}"

    return None


def asset_is_kind(asset: dict, kind: str) -> bool:
    asset_kind = first_text(asset.get("kind"))
    mime_type = first_text(asset.get("mimeType"))
    if asset_kind == kind:
        return True
    return asset_kind == "source" and mime_type.startswith(f"{kind}/")


def snapshot_sources(snapshot: dict, kind: str) -> list[str]:
    sources: list[str] = []

    assets = snapshot.get("mediaAssets")
    if isinstance(assets, list):
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            if not asset_is_kind(asset, kind):
                continue
            source = first_text(asset.get("src"))
            if source and source not in sources:
                sources.append(source)

    metadata = snapshot.get("metadata")
    if isinstance(metadata, dict) and first_text(metadata.get("kind")) == kind:
        artifact_url = first_text(metadata.get("artifactUrl"))
        if artifact_url and artifact_url not in sources:
            sources.append(artifact_url)

    return sources


def materialize_selected_media(payload: dict, inputs_dir: Path, kind: str) -> Path | None:
    inputs_dir.mkdir(parents=True, exist_ok=True)
    selected = payload.get("selectedCardSnapshots")
    if not isinstance(selected, list):
        return None

    seen: set[str] = set()
    for snapshot_index, snapshot in enumerate(selected, start=1):
        if not isinstance(snapshot, dict):
            continue
        for source_index, src in enumerate(snapshot_sources(snapshot, kind), start=1):
            resolved = resolve_media_source(src, inputs_dir / f"{snapshot_index:02d}-{source_index:02d}-{kind}", kind)
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
        raise RuntimeError(f"Could not inspect media {path}: {message}")
    return json.loads(process.stdout or "{}")


def parse_fps(value: object) -> float | None:
    if not isinstance(value, str) or not value or value == "0/0":
        return None
    numerator, separator, denominator = value.partition("/")
    try:
        parsed = float(numerator) / float(denominator) if separator else float(value)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    return parsed if parsed > 0 else None


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


def video_info(path: Path) -> dict:
    probe = ffprobe(path)
    video_stream = first_stream(probe, "video")
    if video_stream is None:
        raise RuntimeError(f"Selected artifact is not a video: {path}")

    format_info = probe.get("format") if isinstance(probe.get("format"), dict) else {}
    duration = parse_duration(video_stream.get("duration")) or parse_duration(format_info.get("duration"))
    fps = parse_fps(video_stream.get("avg_frame_rate")) or parse_fps(video_stream.get("r_frame_rate"))
    width = int(video_stream.get("width") or 0)
    height = int(video_stream.get("height") or 0)
    if width <= 0 or height <= 0:
        raise RuntimeError(f"Could not read video dimensions: {path}")
    if duration is None:
        raise RuntimeError(f"Could not read video duration: {path}")
    if fps is None:
        raise RuntimeError(f"Could not read video FPS: {path}")

    return {
        "path": path,
        "width": width,
        "height": height,
        "duration": duration,
        "fps": fps,
        "has_audio": first_stream(probe, "audio") is not None,
    }


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
        "sampleRate": int(audio_stream.get("sample_rate") or 0),
        "channels": int(audio_stream.get("channels") or 0),
    }


def format_seconds(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".") or "0"


def audio_fit_mode(video_duration: float, audio_duration: float) -> str:
    if audio_duration > video_duration + 0.05:
        return "trimmed-to-video"
    if audio_duration < video_duration - 0.05:
        return "padded-with-silence"
    return "matched"


def render_video_with_audio(video: Path, audio: Path, destination: Path, duration: float) -> None:
    formatted_duration = format_seconds(duration)
    run_command(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video),
            "-i",
            str(audio),
            "-filter_complex",
            (
                f"[1:a:0]atrim=0:{formatted_duration},asetpts=PTS-STARTPTS,"
                f"apad,atrim=0:{formatted_duration},"
                "aformat=channel_layouts=stereo,aresample=48000[a]"
            ),
            "-map",
            "0:v:0",
            "-map",
            "[a]",
            "-t",
            formatted_duration,
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
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


def mux_selected_audio_video(payload: dict) -> dict:
    require_tools()
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    run_dir = output_dir(payload)
    inputs_dir = run_dir.parent / "inputs"

    video = materialize_selected_media(payload, inputs_dir, "video")
    audio = materialize_selected_media(payload, inputs_dir, "audio")
    if video is None:
        raise RuntimeError("ffmpeg-video-audio-mux requires one selected video card.")
    if audio is None:
        raise RuntimeError("ffmpeg-video-audio-mux requires one selected audio card.")

    video_metadata = video_info(video)
    audio_metadata = audio_info(audio)
    output_path = run_dir / "video-with-audio.mp4"
    render_video_with_audio(video, audio, output_path, float(video_metadata["duration"]))

    final_info = video_info(output_path)
    fit_mode = audio_fit_mode(float(video_metadata["duration"]), float(audio_metadata["duration"]))
    metadata = {
        "durationSeconds": final_info["duration"],
        "width": final_info["width"],
        "height": final_info["height"],
        "fps": final_info["fps"],
        "hasAudio": bool(final_info["has_audio"]),
        "audioFitMode": fit_mode,
        "sourceVideo": str(video),
        "sourceAudio": str(audio),
        "sourceVideoDurationSeconds": video_metadata["duration"],
        "sourceAudioDurationSeconds": audio_metadata["duration"],
        "tags": [SKILL_ID],
        "preferredAspectRatio": "auto",
    }

    prompt = base_prompt(payload)
    title = first_text(params.get("title"), "Video with audio")
    return {
        "artifacts": [
            {
                "path": str(output_path),
                "kind": "video",
                "mimeType": "video/mp4",
                "title": title,
                "prompt": prompt,
                "metadata": metadata,
            }
        ]
    }


def main() -> None:
    print(json.dumps(mux_selected_audio_video(read_payload())))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ffmpeg-video-audio-mux failed: {exc}", file=sys.stderr)
        sys.exit(1)
