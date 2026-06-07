from __future__ import annotations

import json
import math
import mimetypes
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
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
COLOR_MATCH_GAIN_MIN = 0.6
COLOR_MATCH_GAIN_MAX = 1.65
COLOR_MATCH_SAMPLE_SIZE = 32
RGB_CHANNELS = ("red", "green", "blue")


@dataclass(frozen=True)
class VideoInput:
    path: Path
    key: str
    labels: tuple[str, ...]


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
    if mime_type in VIDEO_MIME_TYPES:
        return VIDEO_MIME_TYPES[mime_type]
    return mimetypes.guess_extension(mime_type) or ".mp4"


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
            source = first_text(asset.get("src"))
            if source and source not in sources:
                sources.append(source)

    metadata = snapshot.get("metadata")
    if isinstance(metadata, dict) and first_text(metadata.get("kind")) == "video":
        artifact_url = first_text(metadata.get("artifactUrl"))
        if artifact_url:
            sources.append(artifact_url)

    return sources


def normalize_match_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    normalized = " ".join(value.casefold().strip().split())
    return normalized


def source_labels(src: str, path: Path) -> list[str]:
    labels = [src, str(path), str(path.resolve()), path.name, path.stem]
    if src.startswith("/api/artifacts/"):
        labels.append(src.removeprefix("/api/artifacts/"))
    return labels


def snapshot_video_labels(snapshot: dict, src: str, path: Path) -> tuple[str, ...]:
    labels: list[str] = [
        first_text(snapshot.get("id")),
        first_text(snapshot.get("name")),
        first_text(snapshot.get("displayTitle")),
        *source_labels(src, path),
    ]
    metadata = snapshot.get("metadata")
    if isinstance(metadata, dict):
        labels.extend(
            [
                first_text(metadata.get("id")),
                first_text(metadata.get("name")),
                first_text(metadata.get("title")),
                first_text(metadata.get("displayTitle")),
                first_text(metadata.get("artifactUrl")),
            ]
        )

    unique_labels: list[str] = []
    seen: set[str] = set()
    for label in labels:
        normalized = normalize_match_text(label)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_labels.append(label)
    return tuple(unique_labels)


def materialize_selected_video_inputs(payload: dict, inputs_dir: Path) -> list[VideoInput]:
    inputs_dir.mkdir(parents=True, exist_ok=True)
    selected = payload.get("selectedCardSnapshots")
    if not isinstance(selected, list):
        return []

    videos: list[VideoInput] = []
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
                videos.append(
                    VideoInput(
                        path=path,
                        key=key,
                        labels=snapshot_video_labels(snapshot, src, path),
                    )
                )
            break

    return videos


def materialize_selected_videos(payload: dict, inputs_dir: Path) -> list[Path]:
    return [video.path for video in materialize_selected_video_inputs(payload, inputs_dir)]


def parse_video_order(params: dict) -> list[str]:
    raw_order = (
        params.get("videoOrder")
        or params.get("clipOrder")
        or params.get("sourceOrder")
        or params.get("order")
    )
    if raw_order is None:
        return []

    if isinstance(raw_order, str):
        if not raw_order.strip():
            return []
        try:
            parsed = json.loads(raw_order)
        except json.JSONDecodeError:
            parsed = [part.strip() for part in raw_order.split(",")]
        raw_order = parsed

    if not isinstance(raw_order, list):
        raise RuntimeError("videoOrder must be a list of selected video ids, titles, filenames, artifact URLs, or paths.")

    order = [first_text(item) for item in raw_order]
    order = [item for item in order if item]
    if not order:
        return []
    if len(order) != len(set(normalize_match_text(item) for item in order)):
        raise RuntimeError("videoOrder contains duplicate entries.")
    return order


def video_matches_order_item(video: VideoInput, order_item: str) -> bool:
    normalized_item = normalize_match_text(order_item)
    if not normalized_item:
        return False

    labels = [normalize_match_text(label) for label in video.labels]
    if normalized_item in labels:
        return True

    path = normalize_match_text(str(video.path))
    return path.endswith(f"/{normalized_item}") or path.endswith(normalized_item)


def apply_video_order(videos: list[VideoInput], params: dict) -> list[VideoInput]:
    order = parse_video_order(params)
    if not order:
        return videos
    if len(order) != len(videos):
        raise RuntimeError(
            f"videoOrder must include exactly {len(videos)} selected videos; received {len(order)}."
        )

    remaining = list(videos)
    ordered: list[VideoInput] = []
    for order_item in order:
        matches = [video for video in remaining if video_matches_order_item(video, order_item)]
        if not matches:
            available = ", ".join(video.labels[0] if video.labels else str(video.path) for video in remaining)
            raise RuntimeError(f"videoOrder entry could not be matched to a selected video: {order_item}. Available: {available}")
        if len(matches) > 1:
            raise RuntimeError(f"videoOrder entry is ambiguous: {order_item}")
        match = matches[0]
        remaining.remove(match)
        ordered.append(match)

    return ordered


def require_tools() -> None:
    missing = [tool for tool in ("ffmpeg", "ffprobe") if shutil.which(tool) is None]
    if missing:
        raise RuntimeError(f"Missing required tool(s): {', '.join(missing)}")


def run_command(command: list[str]) -> None:
    process = subprocess.run(command, text=True, capture_output=True, check=False)
    if process.returncode != 0:
        message = process.stderr.strip() or process.stdout.strip() or "command failed"
        raise RuntimeError(f"{command[0]} failed: {message[-2000:]}")


def run_binary_command(command: list[str]) -> bytes:
    process = subprocess.run(command, capture_output=True, check=False)
    if process.returncode != 0:
        stderr = process.stderr.decode("utf-8", errors="replace").strip()
        stdout = process.stdout.decode("utf-8", errors="replace").strip()
        message = stderr or stdout or "command failed"
        raise RuntimeError(f"{command[0]} failed: {message[-2000:]}")
    return process.stdout


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


def clamp_float(value: float, minimum: float, maximum: float) -> float:
    if not math.isfinite(value):
        raise RuntimeError("Color matching produced a non-finite value.")
    return min(max(value, minimum), maximum)


def rounded_rgb(values: dict[str, float]) -> dict[str, float]:
    return {channel: round(values[channel], 4) for channel in RGB_CHANNELS}


def last_decodable_time(info: dict) -> float:
    duration = float(info["duration"])
    fps = float(info["fps"])
    frame_duration = 1.0 / fps if fps > 0 else 0.001
    return max(0.0, duration - frame_duration)


def frame_mean_rgb(path: Path, time_seconds: float, sample_size: int = COLOR_MATCH_SAMPLE_SIZE) -> dict[str, float]:
    if sample_size <= 0:
        raise RuntimeError("Color match sample size must be greater than 0.")
    raw_frame = run_binary_command(
        [
            "ffmpeg",
            "-v",
            "error",
            "-ss",
            format_seconds(max(0.0, time_seconds)),
            "-i",
            str(path),
            "-frames:v",
            "1",
            "-vf",
            f"scale={sample_size}:{sample_size},format=rgb24",
            "-f",
            "rawvideo",
            "pipe:1",
        ]
    )
    expected_size = sample_size * sample_size * 3
    if len(raw_frame) != expected_size:
        raise RuntimeError(f"Could not sample video frame for color matching: {path}")

    pixel_count = sample_size * sample_size
    totals = {channel: 0 for channel in RGB_CHANNELS}
    for offset in range(0, len(raw_frame), 3):
        totals["red"] += raw_frame[offset]
        totals["green"] += raw_frame[offset + 1]
        totals["blue"] += raw_frame[offset + 2]

    return {channel: totals[channel] / pixel_count for channel in RGB_CHANNELS}


def color_match_gains(source_rgb: dict[str, float], target_rgb: dict[str, float]) -> dict[str, float]:
    gains: dict[str, float] = {}
    for channel in RGB_CHANNELS:
        source_value = source_rgb[channel]
        target_value = target_rgb[channel]
        if not math.isfinite(source_value) or not math.isfinite(target_value):
            raise RuntimeError("Color matching sampled a non-finite RGB value.")
        gain = target_value / max(source_value, 1.0)
        gains[channel] = clamp_float(gain, COLOR_MATCH_GAIN_MIN, COLOR_MATCH_GAIN_MAX)
    return gains


def colorchannelmixer_filter(gains: dict[str, float]) -> str:
    return (
        f"colorchannelmixer=rr={gains['red']:.6f}:"
        f"gg={gains['green']:.6f}:bb={gains['blue']:.6f},format=yuv420p"
    )


def apply_color_match(source: Path, destination: Path, gains: dict[str, float]) -> None:
    run_command(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(source),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0",
            "-filter:v",
            colorchannelmixer_filter(gains),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(destination),
        ]
    )


def color_match_cut_to_cut(clips: list[Path], destination_dir: Path) -> tuple[list[Path], list[dict[str, object]]]:
    if len(clips) < 2:
        return clips, []

    destination_dir.mkdir(parents=True, exist_ok=True)
    matched_clips = [clips[0]]
    boundaries: list[dict[str, object]] = []

    for index, source_clip in enumerate(clips[1:], start=2):
        target_clip = matched_clips[-1]
        target_info = video_info(target_clip)
        target_rgb = frame_mean_rgb(target_clip, last_decodable_time(target_info))
        source_rgb = frame_mean_rgb(source_clip, 0.0)
        gains = color_match_gains(source_rgb, target_rgb)
        matched_clip = destination_dir / f"clip-{index:02d}.mp4"
        apply_color_match(source_clip, matched_clip, gains)
        matched_clips.append(matched_clip)
        boundaries.append(
            {
                "sourceClipIndex": index,
                "targetClipIndex": index - 1,
                "sourceMeanRgb": rounded_rgb(source_rgb),
                "targetMeanRgb": rounded_rgb(target_rgb),
                "gains": rounded_rgb(gains),
            }
        )

    return matched_clips, boundaries


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

    video_inputs = apply_video_order(materialize_selected_video_inputs(payload, inputs_dir), params)
    videos = [video.path for video in video_inputs]
    if len(video_inputs) < 2:
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

    color_matched_clips = normalized_clips
    color_match_boundaries: list[dict[str, object]] = []
    if trim_last_frame:
        color_matched_clips, color_match_boundaries = color_match_cut_to_cut(
            normalized_clips,
            normalized_dir / "color-matched",
        )

    output_path = run_dir / "joined-video.mp4"
    metadata: dict[str, object] = {
        "joinMode": join_mode,
        "inputCount": len(videos),
        "width": target_width,
        "height": target_height,
        "targetFps": target_fps,
        "sourceVideos": [str(path) for path in videos],
        "sourceVideoLabels": [list(video.labels) for video in video_inputs],
        "tags": [SKILL_ID],
        "preferredAspectRatio": "auto",
    }
    if trim_last_frame:
        metadata["colorMatchEnabled"] = True
        metadata["colorMatchMode"] = "cut-to-cut"
        metadata["colorMatchBoundaries"] = color_match_boundaries

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
        concat_direct(color_matched_clips, output_path, run_dir.parent)

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
