from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4


SKILL_ID = "ffmpeg-video-join"
VIDEO_MIME_TYPES = {
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
    "video/x-matroska": ".mkv",
}
TRANSITION_MAP = {
    "crossfade": "fade",
    "fade-black": "fadeblack",
    "dissolve": "dissolve",
}
JOIN_MODES = {"direct", "trim-last-frame", *TRANSITION_MAP.keys()}


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
    if mime_type in VIDEO_MIME_TYPES:
        return VIDEO_MIME_TYPES[mime_type]
    return mimetypes.guess_extension(mime_type) or ".mp4"


def write_data_url_video(data_url: str, destination: Path) -> Path | None:
    mime_type, data = parse_data_url(data_url)
    if not mime_type.startswith("video/"):
        return None
    path = destination.with_suffix(extension_for_mime_type(mime_type))
    path.write_bytes(data)
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


def resolve_video_source(src: str, destination: Path) -> tuple[Path, str] | None:
    artifact_path = resolve_artifact_src(src)
    if artifact_path is not None:
        return artifact_path, f"path:{artifact_path.resolve()}"

    if src.startswith("data:video/"):
        path = write_data_url_video(src, destination)
        if path is not None:
            digest = hashlib.sha256(src.encode("utf-8")).hexdigest()
            return path, f"data:{digest}"

    return None


def asset_is_video(asset: dict) -> bool:
    kind = first_text(asset.get("kind"))
    mime_type = first_text(asset.get("mimeType"))
    if kind == "video":
        return True
    return kind == "source" and mime_type.startswith("video/")


def snapshot_video_sources(snapshot: dict) -> list[str]:
    sources: list[str] = []

    assets = snapshot.get("mediaAssets")
    if isinstance(assets, list):
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            if not asset_is_video(asset):
                continue
            for source in (first_text(asset.get("src")), first_text(asset.get("dataUrl"))):
                if source and source not in sources:
                    sources.append(source)

    metadata = snapshot.get("metadata")
    if isinstance(metadata, dict) and first_text(metadata.get("kind")) == "video":
        artifact_url = first_text(metadata.get("artifactUrl"))
        if artifact_url:
            sources.append(artifact_url)

    return sources


def materialize_selected_videos(payload: dict, inputs_dir: Path) -> list[Path]:
    inputs_dir.mkdir(parents=True, exist_ok=True)
    selected = payload.get("selectedCardSnapshots")
    if not isinstance(selected, list):
        return []

    videos: list[Path] = []
    seen: set[str] = set()

    for snapshot_index, snapshot in enumerate(selected, start=1):
        if not isinstance(snapshot, dict):
            continue
        for source_index, src in enumerate(snapshot_video_sources(snapshot), start=1):
            resolved = resolve_video_source(src, inputs_dir / f"{snapshot_index:02d}-{source_index:02d}-video")
            if resolved is None:
                continue
            path, key = resolved
            if key not in seen:
                seen.add(key)
                videos.append(path)
            break

    return videos


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
        raise RuntimeError(f"Could not inspect video {path}: {message}")
    return json.loads(process.stdout or "{}")


def parse_fps(value: object) -> float | None:
    if not isinstance(value, str) or not value or value == "0/0":
        return None
    numerator, separator, denominator = value.partition("/")
    try:
        if separator:
            parsed = float(numerator) / float(denominator)
        else:
            parsed = float(value)
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


def even_dimension(value: int) -> int:
    return max(2, value - (value % 2))


def format_seconds(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".") or "0"


def normalize_clip(
    *,
    source: Path,
    destination: Path,
    info: dict,
    target_width: int,
    target_height: int,
    target_fps: float,
    trim_last_frame: bool,
) -> None:
    duration = float(info["duration"])
    output_duration = duration
    if trim_last_frame:
        frame_duration = 1.0 / target_fps
        output_duration = duration - frame_duration
        if output_duration <= 0.05:
            raise RuntimeError(f"Video is too short to trim its final frame: {source}")

    video_filter = (
        f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,"
        f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2,"
        f"fps={format_seconds(target_fps)},setsar=1,format=yuv420p"
    )
    command = ["ffmpeg", "-y", "-i", str(source)]
    if info["has_audio"]:
        command.extend(
            [
                "-map",
                "0:v:0",
                "-map",
                "0:a:0",
                "-filter:v",
                video_filter,
                "-af",
                "aformat=channel_layouts=stereo,aresample=48000",
            ]
        )
    else:
        command.extend(
            [
                "-f",
                "lavfi",
                "-i",
                "anullsrc=r=48000:cl=stereo",
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-filter:v",
                video_filter,
                "-shortest",
            ]
        )
    if trim_last_frame:
        command.extend(["-t", format_seconds(output_duration)])
    command.extend(
        [
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
    run_command(command)


def escape_concat_path(path: Path) -> str:
    return str(path).replace("'", "'\\''")


def concat_direct(clips: list[Path], destination: Path, work_dir: Path) -> None:
    concat_file = work_dir / "concat-list.txt"
    concat_file.write_text(
        "".join(f"file '{escape_concat_path(path)}'\n" for path in clips),
        encoding="utf-8",
    )
    run_command(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(destination),
        ]
    )


def transition_duration(params: dict, durations: list[float]) -> tuple[float, float]:
    raw_value = params.get("fadeDurationSeconds")
    requested = 0.5 if raw_value is None else parse_duration(raw_value)
    if requested is None or requested <= 0:
        raise RuntimeError("fadeDurationSeconds must be greater than 0.")
    max_fade = min(durations) / 2.0
    if max_fade < 0.05:
        raise RuntimeError("Selected videos are too short for a transition.")
    return requested, min(requested, max_fade)


def concat_with_transition(
    *,
    clips: list[Path],
    durations: list[float],
    destination: Path,
    transition: str,
    fade_seconds: float,
) -> None:
    command = ["ffmpeg", "-y"]
    for clip in clips:
        command.extend(["-i", str(clip)])

    filters: list[str] = []
    for index in range(len(clips)):
        filters.append(f"[{index}:v]settb=AVTB,setpts=PTS-STARTPTS[v{index}b]")
        filters.append(f"[{index}:a]asetpts=PTS-STARTPTS[a{index}b]")

    current_video = "[v0b]"
    current_audio = "[a0b]"
    accumulated_duration = durations[0]
    for index in range(1, len(clips)):
        next_video = f"[v{index}b]"
        next_audio = f"[a{index}b]"
        video_out = f"[vxf{index}]"
        audio_out = f"[axf{index}]"
        offset = max(0.0, accumulated_duration - fade_seconds)
        filters.append(
            f"{current_video}{next_video}xfade=transition={transition}:"
            f"duration={format_seconds(fade_seconds)}:offset={format_seconds(offset)}{video_out}"
        )
        filters.append(
            f"{current_audio}{next_audio}acrossfade=d={format_seconds(fade_seconds)}:"
            f"c1=tri:c2=tri{audio_out}"
        )
        current_video = video_out
        current_audio = audio_out
        accumulated_duration += durations[index] - fade_seconds

    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            current_video,
            "-map",
            current_audio,
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
    run_command(command)


def normalize_join_mode(params: dict) -> str:
    join_mode = first_text(params.get("joinMode"), params.get("mode"), "direct")
    if join_mode not in JOIN_MODES:
        raise RuntimeError(f"Unsupported joinMode: {join_mode}")
    return join_mode


def base_prompt(payload: dict) -> str:
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    return first_text(params.get("skillPrompt"), params.get("prompt"), params.get("outputText"), payload.get("prompt"))


def join_selected_videos(payload: dict) -> dict:
    require_tools()
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    join_mode = normalize_join_mode(params)
    run_dir = output_dir(payload)
    inputs_dir = run_dir.parent / "inputs"
    normalized_dir = run_dir.parent / "normalized"
    normalized_dir.mkdir(parents=True, exist_ok=True)

    videos = materialize_selected_videos(payload, inputs_dir)
    if len(videos) < 2:
        raise RuntimeError("ffmpeg-video-join requires at least two selected video cards.")

    infos = [video_info(path) for path in videos]
    target_width = even_dimension(int(infos[0]["width"]))
    target_height = even_dimension(int(infos[0]["height"]))
    target_fps = float(infos[0]["fps"])
    trim_last_frame = join_mode == "trim-last-frame"

    normalized_clips: list[Path] = []
    for index, (path, info) in enumerate(zip(videos, infos, strict=True), start=1):
        clip = normalized_dir / f"clip-{index:02d}.mp4"
        normalize_clip(
            source=path,
            destination=clip,
            info=info,
            target_width=target_width,
            target_height=target_height,
            target_fps=target_fps,
            trim_last_frame=trim_last_frame and index < len(videos),
        )
        normalized_clips.append(clip)

    output_path = run_dir / "joined-video.mp4"
    metadata: dict[str, object] = {
        "joinMode": join_mode,
        "inputCount": len(videos),
        "width": target_width,
        "height": target_height,
        "targetFps": target_fps,
        "sourceVideos": [str(path) for path in videos],
        "tags": [SKILL_ID],
        "preferredAspectRatio": "auto",
    }

    if join_mode in TRANSITION_MAP:
        normalized_infos = [video_info(path) for path in normalized_clips]
        durations = [float(info["duration"]) for info in normalized_infos]
        requested_fade, effective_fade = transition_duration(params, durations)
        concat_with_transition(
            clips=normalized_clips,
            durations=durations,
            destination=output_path,
            transition=TRANSITION_MAP[join_mode],
            fade_seconds=effective_fade,
        )
        metadata["requestedFadeDurationSeconds"] = requested_fade
        metadata["fadeDurationSeconds"] = effective_fade
    else:
        concat_direct(normalized_clips, output_path, run_dir.parent)

    final_info = video_info(output_path)
    metadata["durationSeconds"] = final_info["duration"]
    metadata["hasAudio"] = bool(final_info["has_audio"])

    prompt = base_prompt(payload)
    title = first_text(params.get("title"), "Joined video")
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
    print(json.dumps(join_selected_videos(read_payload())))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ffmpeg-video-join failed: {exc}", file=sys.stderr)
        sys.exit(1)
