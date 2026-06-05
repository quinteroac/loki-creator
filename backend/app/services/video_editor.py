from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

from app.models import (
    VideoEditArtifact,
    VideoTimelineResponse,
    VideoTimelineThumbnail,
)


class VideoEditorError(RuntimeError):
    pass


class VideoEditorService:
    DEFAULT_THUMBNAILS = 16
    MAX_THUMBNAILS = 24
    MIN_TRIM_SECONDS = 0.1

    def __init__(self, artifacts_root: Path) -> None:
        self.artifacts_root = artifacts_root.resolve()
        self.deleted_root = self.artifacts_root / "deleted"
        self.editor_root = self.artifacts_root / "video-editor"

    def timeline(self, artifact_url: str, max_thumbnails: int | None = None) -> VideoTimelineResponse:
        source = self._resolve_artifact_url(artifact_url)
        self._require_tools()
        info = self.video_info(source)
        thumbnail_count = self._thumbnail_count(max_thumbnails)
        timeline_dir = self.editor_root / "timelines" / self._timeline_cache_key(source, thumbnail_count)
        timeline_dir.mkdir(parents=True, exist_ok=True)
        times = self._thumbnail_times(float(info["duration"]), thumbnail_count, float(info["fps"]))
        thumbnails = [
            self._timeline_thumbnail(source=source, destination=timeline_dir / f"thumb-{index:02d}.jpg", time_seconds=time)
            for index, time in enumerate(times, start=1)
        ]

        return VideoTimelineResponse(
            artifactUrl=artifact_url,
            durationSeconds=float(info["duration"]),
            width=int(info["width"]),
            height=int(info["height"]),
            fps=float(info["fps"]),
            thumbnails=thumbnails,
        )

    def export_frame(self, artifact_url: str, time_seconds: float) -> VideoEditArtifact:
        source = self._resolve_artifact_url(artifact_url)
        self._require_tools()
        info = self.video_info(source)
        timestamp = self._validate_time(time_seconds, float(info["duration"]), float(info["fps"]))
        output_dir = self.editor_root / "exports" / uuid4().hex
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{source.stem}-frame-{self._milliseconds(timestamp)}.png"
        self._run_command(
            [
                "ffmpeg",
                "-y",
                "-ss",
                self._format_seconds(timestamp),
                "-i",
                str(source),
                "-frames:v",
                "1",
                "-update",
                "1",
                str(output_path),
            ]
        )
        if not output_path.is_file():
            raise VideoEditorError("ffmpeg did not create the requested frame artifact.")

        return VideoEditArtifact(
            artifactUrl=self._artifact_url_for_path(output_path),
            sourceArtifactUrl=artifact_url,
            name=f"{source.stem} frame {self._format_seconds(timestamp)}s",
            kind="image",
            mimeType="image/png",
            size=output_path.stat().st_size,
            width=int(info["width"]),
            height=int(info["height"]),
            timeSeconds=timestamp,
        )

    def trim(self, artifact_url: str, start_seconds: float, end_seconds: float) -> VideoEditArtifact:
        source = self._resolve_artifact_url(artifact_url)
        self._require_tools()
        info = self.video_info(source)
        start, end = self._validate_trim_range(start_seconds, end_seconds, float(info["duration"]))
        output_dir = self.editor_root / "exports" / uuid4().hex
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{source.stem}-trim-{self._milliseconds(start)}-{self._milliseconds(end)}.mp4"
        command = [
            "ffmpeg",
            "-y",
            "-ss",
            self._format_seconds(start),
            "-i",
            str(source),
            "-t",
            self._format_seconds(end - start),
            "-map",
            "0:v:0",
        ]
        if info["has_audio"]:
            command.extend(["-map", "0:a:0"])
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
                str(output_path),
            ]
        )
        self._run_command(command)
        if not output_path.is_file():
            raise VideoEditorError("ffmpeg did not create the requested trim artifact.")

        output_info = self.video_info(output_path)
        return VideoEditArtifact(
            artifactUrl=self._artifact_url_for_path(output_path),
            sourceArtifactUrl=artifact_url,
            name=f"{source.stem} trim",
            kind="video",
            mimeType="video/mp4",
            size=output_path.stat().st_size,
            width=int(output_info["width"]),
            height=int(output_info["height"]),
            durationSeconds=float(output_info["duration"]),
            startSeconds=start,
            endSeconds=end,
        )

    def video_info(self, path: Path) -> dict[str, object]:
        probe = self._ffprobe(path)
        video_stream = self._first_stream(probe, "video")
        if video_stream is None:
            raise VideoEditorError(f"Selected artifact is not a video: {path.name}")

        format_info = probe.get("format") if isinstance(probe.get("format"), dict) else {}
        duration = self._parse_duration(video_stream.get("duration")) or self._parse_duration(format_info.get("duration"))
        fps = self._parse_fps(video_stream.get("avg_frame_rate")) or self._parse_fps(video_stream.get("r_frame_rate"))
        width = int(video_stream.get("width") or 0)
        height = int(video_stream.get("height") or 0)
        if width <= 0 or height <= 0:
            raise VideoEditorError(f"Could not read video dimensions: {path.name}")
        if duration is None:
            raise VideoEditorError(f"Could not read video duration: {path.name}")
        if fps is None:
            raise VideoEditorError(f"Could not read video FPS: {path.name}")

        return {
            "width": width,
            "height": height,
            "duration": duration,
            "fps": fps,
            "has_audio": self._first_stream(probe, "audio") is not None,
        }

    def _resolve_artifact_url(self, artifact_url: str) -> Path:
        if not artifact_url.startswith("/api/artifacts/"):
            raise VideoEditorError("Video editing only supports local artifact URLs.")

        artifact = (self.artifacts_root / artifact_url.removeprefix("/api/artifacts/")).resolve()
        try:
            artifact.relative_to(self.artifacts_root)
        except ValueError as exc:
            raise VideoEditorError("Artifact URL is outside the Loki artifacts directory.") from exc

        try:
            artifact.relative_to(self.deleted_root)
            raise VideoEditorError("Archived artifacts cannot be edited.")
        except ValueError:
            pass

        if not artifact.is_file():
            raise VideoEditorError("Artifact file was not found.")
        return artifact

    def _artifact_url_for_path(self, path: Path) -> str:
        return f"/api/artifacts/{path.resolve().relative_to(self.artifacts_root).as_posix()}"

    def _timeline_cache_key(self, source: Path, thumbnail_count: int) -> str:
        relative = source.resolve().relative_to(self.artifacts_root).as_posix()
        stat = source.stat()
        digest = hashlib.sha256(
            f"timeline-v2|{relative}|{stat.st_mtime_ns}|{stat.st_size}|{thumbnail_count}".encode("utf-8")
        ).hexdigest()
        return digest[:24]

    def _thumbnail_count(self, value: int | None) -> int:
        if value is None:
            return self.DEFAULT_THUMBNAILS
        return min(max(1, int(value)), self.MAX_THUMBNAILS)

    def _thumbnail_times(self, duration: float, count: int, fps: float) -> list[float]:
        safe_duration = max(duration, 0.001)
        frame_duration = 1.0 / fps if fps > 0 else 0.001
        last_decodable_time = max(0, safe_duration - frame_duration)
        return [min(last_decodable_time, safe_duration * (index + 0.5) / count) for index in range(count)]

    def _timeline_thumbnail(self, *, source: Path, destination: Path, time_seconds: float) -> VideoTimelineThumbnail:
        if not destination.is_file():
            self._run_command(
                [
                    "ffmpeg",
                    "-y",
                    "-ss",
                    self._format_seconds(time_seconds),
                    "-i",
                    str(source),
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale=360:-2",
                    "-q:v",
                    "3",
                    "-update",
                    "1",
                    str(destination),
                ]
            )
        if not destination.is_file():
            raise VideoEditorError("ffmpeg did not create a timeline thumbnail.")

        width, height = self._image_dimensions(destination)
        return VideoTimelineThumbnail(
            artifactUrl=self._artifact_url_for_path(destination),
            timeSeconds=time_seconds,
            width=width,
            height=height,
        )

    def _validate_time(self, value: float, duration: float, fps: float) -> float:
        try:
            time_seconds = float(value)
        except (TypeError, ValueError) as exc:
            raise VideoEditorError("timeSeconds must be a number.") from exc
        if not math.isfinite(time_seconds) or time_seconds < 0:
            raise VideoEditorError("timeSeconds must be greater than or equal to 0.")
        if time_seconds > duration:
            raise VideoEditorError("timeSeconds cannot be greater than the video duration.")
        frame_duration = 1.0 / fps if fps > 0 else 0.001
        return min(time_seconds, max(duration - frame_duration, 0))

    def _validate_trim_range(self, start_value: float, end_value: float, duration: float) -> tuple[float, float]:
        try:
            start = float(start_value)
            end = float(end_value)
        except (TypeError, ValueError) as exc:
            raise VideoEditorError("Trim start and end times must be numbers.") from exc
        if not math.isfinite(start) or not math.isfinite(end):
            raise VideoEditorError("Trim start and end times must be finite.")
        if start < 0:
            raise VideoEditorError("Trim startSeconds must be greater than or equal to 0.")
        if end <= start:
            raise VideoEditorError("Trim endSeconds must be greater than startSeconds.")
        if end - start < self.MIN_TRIM_SECONDS:
            raise VideoEditorError("Trim range is too short.")
        if end > duration:
            raise VideoEditorError("Trim endSeconds cannot be greater than the video duration.")
        return start, end

    def _require_tools(self) -> None:
        missing = [tool for tool in ("ffmpeg", "ffprobe") if shutil.which(tool) is None]
        if missing:
            raise VideoEditorError(f"Missing required tool(s): {', '.join(missing)}")

    def _run_command(self, command: list[str]) -> None:
        process = subprocess.run(command, text=True, capture_output=True, check=False)
        if process.returncode != 0:
            message = process.stderr.strip() or process.stdout.strip() or "command failed"
            raise VideoEditorError(f"{command[0]} failed: {message[-2000:]}")

    def _ffprobe(self, path: Path) -> dict:
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
            raise VideoEditorError(f"Could not inspect video {path.name}: {message}")
        return json.loads(process.stdout or "{}")

    def _image_dimensions(self, path: Path) -> tuple[int, int]:
        probe = self._ffprobe(path)
        image_stream = self._first_stream(probe, "video")
        if image_stream is None:
            raise VideoEditorError(f"Could not inspect thumbnail dimensions: {path.name}")
        return int(image_stream.get("width") or 0), int(image_stream.get("height") or 0)

    def _first_stream(self, probe: dict, codec_type: str) -> dict | None:
        streams = probe.get("streams")
        if not isinstance(streams, list):
            return None
        for stream in streams:
            if isinstance(stream, dict) and stream.get("codec_type") == codec_type:
                return stream
        return None

    def _parse_fps(self, value: object) -> float | None:
        if not isinstance(value, str) or not value or value == "0/0":
            return None
        numerator, separator, denominator = value.partition("/")
        try:
            parsed = float(numerator) / float(denominator) if separator else float(value)
        except (TypeError, ValueError, ZeroDivisionError):
            return None
        return parsed if parsed > 0 else None

    def _parse_duration(self, value: object) -> float | None:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    def _format_seconds(self, value: float) -> str:
        return f"{value:.6f}".rstrip("0").rstrip(".") or "0"

    def _milliseconds(self, value: float) -> int:
        return max(0, int(round(value * 1000)))
