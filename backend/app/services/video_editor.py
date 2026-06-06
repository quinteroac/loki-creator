from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from app.models import (
    VideoEditArtifact,
    VideoLutOption,
    VideoTimelineResponse,
    VideoTimelineThumbnail,
)


class VideoEditorError(RuntimeError):
    pass


@dataclass(frozen=True)
class VideoLutPreset:
    id: str
    label: str
    filename: str | None = None
    path: Path | None = None


class VideoEditorService:
    DEFAULT_THUMBNAILS = 16
    MAX_THUMBNAILS = 24
    MIN_TRIM_SECONDS = 0.1
    ORIGINAL_LUT_ID = "original"
    LUT_PRESETS = (
        VideoLutPreset(id=ORIGINAL_LUT_ID, label="Original"),
        VideoLutPreset(id="cinematic", label="Cinematic", filename="cinematic.cube"),
        VideoLutPreset(id="film-warm", label="Film Warm", filename="film-warm.cube"),
        VideoLutPreset(id="teal-orange", label="Teal Orange", filename="teal-orange.cube"),
        VideoLutPreset(id="blue-boost", label="Blue Boost", filename="blue-boost.cube"),
        VideoLutPreset(id="soft-fade", label="Soft Fade", filename="soft-fade.cube"),
        VideoLutPreset(id="clean-contrast", label="Clean Contrast", filename="clean-contrast.cube"),
        VideoLutPreset(id="mono", label="Mono", filename="mono.cube"),
    )

    def __init__(self, artifacts_root: Path) -> None:
        self.artifacts_root = artifacts_root.resolve()
        self.deleted_root = self.artifacts_root / "deleted"
        self.editor_root = self.artifacts_root / "video-editor"
        self.luts_root = Path(__file__).resolve().parents[1] / "assets" / "video_luts"
        self.imported_luts_root = self.artifacts_root / "video-luts" / "imported"

    def list_luts(self) -> list[VideoLutOption]:
        return [VideoLutOption(id=preset.id, label=preset.label) for preset in self._all_lut_presets()]

    def timeline(
        self,
        artifact_url: str,
        max_thumbnails: int | None = None,
        lut_id: str | None = None,
    ) -> VideoTimelineResponse:
        source = self._resolve_artifact_url(artifact_url)
        self._require_tools()
        lut = self._resolve_lut(lut_id)
        info = self.video_info(source)
        thumbnail_count = self._thumbnail_count(max_thumbnails)
        timeline_dir = self.editor_root / "timelines" / self._timeline_cache_key(source, thumbnail_count, lut)
        timeline_dir.mkdir(parents=True, exist_ok=True)
        times = self._thumbnail_times(float(info["duration"]), thumbnail_count, float(info["fps"]))
        thumbnails = [
            self._timeline_thumbnail(
                source=source,
                destination=timeline_dir / f"thumb-{index:02d}.jpg",
                time_seconds=time,
                lut=lut,
            )
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

    def export_frame(self, artifact_url: str, time_seconds: float, lut_id: str | None = None) -> VideoEditArtifact:
        source = self._resolve_artifact_url(artifact_url)
        self._require_tools()
        lut = self._resolve_lut(lut_id)
        info = self.video_info(source)
        timestamp = self._validate_time(time_seconds, float(info["duration"]), float(info["fps"]))
        output_dir = self.editor_root / "exports" / uuid4().hex
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{source.stem}-frame-{self._milliseconds(timestamp)}-{lut.id}.png"
        command = [
            "ffmpeg",
            "-y",
            "-ss",
            self._format_seconds(timestamp),
            "-i",
            str(source),
        ]
        filter_value = self._video_filter(lut)
        if filter_value:
            command.extend(["-vf", filter_value])
        command.extend(
            [
                "-frames:v",
                "1",
                "-update",
                "1",
                str(output_path),
            ]
        )
        self._run_command(command)
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
            lutId=lut.id,
            lutLabel=lut.label,
        )

    def trim(
        self,
        artifact_url: str,
        start_seconds: float,
        end_seconds: float,
        lut_id: str | None = None,
    ) -> VideoEditArtifact:
        source = self._resolve_artifact_url(artifact_url)
        self._require_tools()
        lut = self._resolve_lut(lut_id)
        info = self.video_info(source)
        start, end = self._validate_trim_range(start_seconds, end_seconds, float(info["duration"]))
        output_dir = self.editor_root / "exports" / uuid4().hex
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{source.stem}-trim-{self._milliseconds(start)}-{self._milliseconds(end)}-{lut.id}.mp4"
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
        filter_value = self._video_filter(lut)
        if filter_value:
            command.extend(["-filter:v", filter_value])
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
            lutId=lut.id,
            lutLabel=lut.label,
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

    def _timeline_cache_key(self, source: Path, thumbnail_count: int, lut: VideoLutPreset) -> str:
        relative = source.resolve().relative_to(self.artifacts_root).as_posix()
        stat = source.stat()
        digest = hashlib.sha256(
            f"timeline-v4|{relative}|{stat.st_mtime_ns}|{stat.st_size}|{thumbnail_count}|{self._lut_cache_token(lut)}".encode(
                "utf-8"
            )
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

    def _timeline_thumbnail(
        self,
        *,
        source: Path,
        destination: Path,
        time_seconds: float,
        lut: VideoLutPreset,
    ) -> VideoTimelineThumbnail:
        if not destination.is_file():
            filter_value = self._video_filter(lut, "scale=360:-2")
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
                    filter_value or "scale=360:-2",
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

    def _resolve_lut(self, lut_id: str | None) -> VideoLutPreset:
        normalized_id = (lut_id or self.ORIGINAL_LUT_ID).strip() or self.ORIGINAL_LUT_ID
        preset = next((candidate for candidate in self._all_lut_presets() if candidate.id == normalized_id), None)
        if preset is None:
            raise VideoEditorError(f"Unknown video LUT: {normalized_id}")
        lut_path = self._lut_path(preset)
        if lut_path is None:
            return preset
        if not lut_path.is_file():
            raise VideoEditorError(f"Video LUT was not found: {preset.id}")
        return preset

    def _video_filter(self, lut: VideoLutPreset, *filters: str) -> str:
        parts: list[str] = []
        lut_path = self._lut_path(lut)
        if lut_path is not None:
            parts.append(f"lut3d=file={self._escape_filter_value(str(lut_path))}:interp=tetrahedral")
        parts.extend(filter_value for filter_value in filters if filter_value)
        return ",".join(parts)

    def _escape_filter_value(self, value: str) -> str:
        return value.replace("\\", "\\\\").replace(":", "\\:").replace(",", "\\,")

    def _lut_cache_token(self, lut: VideoLutPreset) -> str:
        lut_path = self._lut_path(lut)
        if lut_path is None:
            return lut.id
        stat = lut_path.stat()
        return f"{lut.id}|{stat.st_mtime_ns}|{stat.st_size}"

    def _all_lut_presets(self) -> list[VideoLutPreset]:
        return [*self.LUT_PRESETS, *self._imported_lut_presets()]

    def _imported_lut_presets(self) -> list[VideoLutPreset]:
        if not self.imported_luts_root.is_dir():
            return []

        presets: list[VideoLutPreset] = []
        root = self.imported_luts_root.resolve()
        for path in sorted(self.imported_luts_root.rglob("*")):
            if not path.is_file() or path.suffix.lower() != ".cube":
                continue
            resolved_path = path.resolve()
            try:
                relative = resolved_path.relative_to(root)
            except ValueError:
                continue
            if any(part.startswith(".") or part == "__MACOSX" for part in relative.parts):
                continue
            presets.append(
                VideoLutPreset(
                    id=self._imported_lut_id(relative),
                    label=self._imported_lut_label(relative),
                    path=resolved_path,
                )
            )
        return presets

    def _lut_path(self, lut: VideoLutPreset) -> Path | None:
        if lut.filename is not None:
            lut_path = (self.luts_root / lut.filename).resolve()
            try:
                lut_path.relative_to(self.luts_root.resolve())
            except ValueError as exc:
                raise VideoEditorError("Video LUT is outside the bundled LUT directory.") from exc
            return lut_path

        if lut.path is not None:
            lut_path = lut.path.resolve()
            try:
                lut_path.relative_to(self.imported_luts_root.resolve())
            except ValueError as exc:
                raise VideoEditorError("Video LUT is outside the imported LUT directory.") from exc
            return lut_path

        return None

    def _imported_lut_id(self, relative_path: Path) -> str:
        normalized = relative_path.with_suffix("").as_posix()
        slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-") or "lut"
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:8]
        return f"imported-{slug[:72]}-{digest}"

    def _imported_lut_label(self, relative_path: Path) -> str:
        stem = relative_path.stem.replace("_", " ").replace("-", " ").strip()
        name = re.sub(r"\s+", " ", stem)
        if len(relative_path.parts) <= 1:
            return f"Imported - {name}"
        category = re.sub(r"\s+", " ", relative_path.parts[0].replace("_", " ").strip())
        return f"{category} - {name}"

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
