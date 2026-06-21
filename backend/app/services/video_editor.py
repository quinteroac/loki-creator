from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from app.models import (
    VideoEditArtifact,
    VideoEffectOption,
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


@dataclass(frozen=True)
class VideoEffectPreset:
    id: str
    label: str
    filter_name: str | None = None
    filter_params: str | None = None


INSTALLED_FREI0R_EFFECT_IDS = (
    "3dflippo",
    "B",
    "G",
    "IIRblur",
    "R",
    "RGB",
    "addition",
    "addition_alpha",
    "aech0r",
    "alpha0ps",
    "alphaatop",
    "alphagrad",
    "alphain",
    "alphainjection",
    "alphaout",
    "alphaover",
    "alphaspot",
    "alphaxor",
    "balanc0r",
    "baltan",
    "bgsubtract0r",
    "blend",
    "bluescreen0r",
    "brightness",
    "burn",
    "bw0r",
    "c0rners",
    "cairoaffineblend",
    "cairoblend",
    "cairogradient",
    "cairoimagegrid",
    "cartoon",
    "cluster",
    "colgate",
    "color_only",
    "coloradj_RGB",
    "colordistance",
    "colorhalftone",
    "colorize",
    "colortap",
    "composition",
    "contrast0r",
    "curves",
    "d90stairsteppingfix",
    "darken",
    "defish0r",
    "delay0r",
    "delaygrab",
    "difference",
    "distort0r",
    "dither",
    "divide",
    "dodge",
    "edgeglow",
    "elastic_scale",
    "emboss",
    "equaliz0r",
    "facebl0r",
    "facedetect",
    "flippo",
    "gamma",
    "glitch0r",
    "glow",
    "grain_extract",
    "grain_merge",
    "hardlight",
    "hqdn3d",
    "hue",
    "hueshift0r",
    "invert0r",
    "ising0r",
    "keyspillm0pup",
    "lenscorrection",
    "letterb0xed",
    "levels",
    "lighten",
    "lightgraffiti",
    "lissajous0r",
    "luminance",
    "mask0mate",
    "medians",
    "multiply",
    "ndvi",
    "nervous",
    "nois0r",
    "normaliz0r",
    "nosync0r",
    "onecol0r",
    "overlay",
    "partik0l",
    "perspective",
    "pixeliz0r",
    "plasma",
    "posterize",
    "pr0be",
    "pr0file",
    "premultiply",
    "primaries",
    "rgbnoise",
    "rgbparade",
    "rgbsplit0r",
    "saturat0r",
    "saturation",
    "scale0tilt",
    "scanline0r",
    "screen",
    "select0r",
    "sharpness",
    "sigmoidaltransfer",
    "sobel",
    "softglow",
    "softlight",
    "sopsat",
    "spillsupress",
    "squareblur",
    "subtract",
    "tehroxx0r",
    "test_pat_B",
    "test_pat_C",
    "test_pat_G",
    "test_pat_I",
    "test_pat_L",
    "test_pat_R",
    "three_point_balance",
    "threelay0r",
    "threshold0r",
    "timeout",
    "tint0r",
    "transparency",
    "twolay0r",
    "uvmap",
    "value",
    "vectorscope",
    "vertigo",
    "vignette",
    "xfade0r",
)


def _frei0r_effect_label(effect_id: str) -> str:
    if effect_id.isupper():
        return effect_id
    words = effect_id.replace("_", " ").replace("-", " ").split()
    return " ".join(word[:1].upper() + word[1:] for word in words) or effect_id


class VideoEditorService:
    DEFAULT_THUMBNAILS = 16
    MAX_THUMBNAILS = 24
    MIN_TRIM_SECONDS = 0.1
    FREI0R_COMPATIBILITY_TIMEOUT_SECONDS = 4
    _ffmpeg_supports_frei0r_cache: bool | None = None
    _frei0r_filter_compatibility_cache: dict[str, bool] = {}
    ORIGINAL_LUT_ID = "original"
    NO_EFFECT_ID = "none"
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
    EFFECT_PRESETS = (
        VideoEffectPreset(id=NO_EFFECT_ID, label="None"),
        *(VideoEffectPreset(id=effect_id, label=_frei0r_effect_label(effect_id), filter_name=effect_id) for effect_id in INSTALLED_FREI0R_EFFECT_IDS),
    )

    def __init__(self, artifacts_root: Path) -> None:
        self.artifacts_root = artifacts_root.resolve()
        self.deleted_root = self.artifacts_root / "deleted"
        self.editor_root = self.artifacts_root / "video-editor"
        self.luts_root = Path(__file__).resolve().parents[1] / "assets" / "video_luts"
        self.imported_luts_root = self.artifacts_root / "video-luts" / "imported"
        self._frei0r_plugin_paths_cache: dict[str, Path | None] = {}

    def list_luts(self) -> list[VideoLutOption]:
        return [VideoLutOption(id=preset.id, label=preset.label) for preset in self._all_lut_presets()]

    def list_effects(self) -> list[VideoEffectOption]:
        return [
            VideoEffectOption(id=preset.id, label=preset.label, available=self._effect_available(preset))
            for preset in self.EFFECT_PRESETS
        ]

    def timeline(
        self,
        artifact_url: str,
        max_thumbnails: int | None = None,
        lut_id: str | None = None,
        effect_id: str | None = None,
    ) -> VideoTimelineResponse:
        source = self._resolve_artifact_url(artifact_url)
        self._require_tools()
        lut = self._resolve_lut(lut_id)
        effect = self._resolve_effect(effect_id)
        info = self.video_info(source)
        thumbnail_count = self._thumbnail_count(max_thumbnails)
        timeline_dir = self.editor_root / "timelines" / self._timeline_cache_key(source, thumbnail_count, lut, effect)
        timeline_dir.mkdir(parents=True, exist_ok=True)
        times = self._thumbnail_times(float(info["duration"]), thumbnail_count, float(info["fps"]))
        thumbnails = [
            self._timeline_thumbnail(
                source=source,
                destination=timeline_dir / f"thumb-{index:02d}.jpg",
                time_seconds=time,
                lut=lut,
                effect=effect,
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

    def export_frame(
        self,
        artifact_url: str,
        time_seconds: float,
        lut_id: str | None = None,
        effect_id: str | None = None,
    ) -> VideoEditArtifact:
        source = self._resolve_artifact_url(artifact_url)
        self._require_tools()
        lut = self._resolve_lut(lut_id)
        effect = self._resolve_effect(effect_id)
        info = self.video_info(source)
        timestamp = self._validate_time(time_seconds, float(info["duration"]), float(info["fps"]))
        output_dir = self.editor_root / "exports" / uuid4().hex
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{source.stem}-frame-{self._milliseconds(timestamp)}-{lut.id}-{effect.id}.png"
        command = [
            "ffmpeg",
            "-y",
            "-ss",
            self._format_seconds(timestamp),
            "-i",
            str(source),
        ]
        filter_value = self._video_filter(lut, effect)
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
            effectId=effect.id,
            effectLabel=effect.label,
        )

    def trim(
        self,
        artifact_url: str,
        start_seconds: float,
        end_seconds: float,
        lut_id: str | None = None,
        effect_id: str | None = None,
    ) -> VideoEditArtifact:
        source = self._resolve_artifact_url(artifact_url)
        self._require_tools()
        lut = self._resolve_lut(lut_id)
        effect = self._resolve_effect(effect_id)
        info = self.video_info(source)
        start, end = self._validate_trim_range(start_seconds, end_seconds, float(info["duration"]))
        output_dir = self.editor_root / "exports" / uuid4().hex
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{source.stem}-trim-{self._milliseconds(start)}-{self._milliseconds(end)}-{lut.id}-{effect.id}.mp4"
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
        filter_value = self._video_filter(lut, effect)
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
            effectId=effect.id,
            effectLabel=effect.label,
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

    def _timeline_cache_key(
        self,
        source: Path,
        thumbnail_count: int,
        lut: VideoLutPreset,
        effect: VideoEffectPreset,
    ) -> str:
        relative = source.resolve().relative_to(self.artifacts_root).as_posix()
        stat = source.stat()
        digest = hashlib.sha256(
            f"timeline-v5|{relative}|{stat.st_mtime_ns}|{stat.st_size}|{thumbnail_count}|{self._lut_cache_token(lut)}|{self._effect_cache_token(effect)}".encode(
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
        effect: VideoEffectPreset,
    ) -> VideoTimelineThumbnail:
        if not destination.is_file():
            filter_value = self._video_filter(lut, effect, "scale=360:-2")
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

    def _resolve_effect(self, effect_id: str | None) -> VideoEffectPreset:
        normalized_id = (effect_id or self.NO_EFFECT_ID).strip() or self.NO_EFFECT_ID
        preset = next((candidate for candidate in self.EFFECT_PRESETS if candidate.id == normalized_id), None)
        if preset is None:
            raise VideoEditorError(f"Unknown video effect: {normalized_id}")
        self._require_effect_available(preset)
        return preset

    def _video_filter(self, lut: VideoLutPreset, effect: VideoEffectPreset, *filters: str) -> str:
        parts: list[str] = []
        lut_path = self._lut_path(lut)
        if lut_path is not None:
            parts.append(f"lut3d=file={self._escape_filter_value(str(lut_path))}:interp=tetrahedral")
        effect_filter = self._effect_filter(effect)
        if effect_filter:
            parts.append(effect_filter)
        parts.extend(filter_value for filter_value in filters if filter_value)
        return ",".join(parts)

    def _effect_filter(self, effect: VideoEffectPreset) -> str:
        if effect.filter_name is None:
            return ""
        value = f"frei0r=filter_name={self._escape_filter_value(effect.filter_name)}"
        if effect.filter_params:
            value = f"{value}:filter_params={self._escape_filter_value(effect.filter_params)}"
        return value

    def _escape_filter_value(self, value: str) -> str:
        return value.replace("\\", "\\\\").replace(":", "\\:").replace(",", "\\,")

    def _lut_cache_token(self, lut: VideoLutPreset) -> str:
        lut_path = self._lut_path(lut)
        if lut_path is None:
            return lut.id
        stat = lut_path.stat()
        return f"{lut.id}|{stat.st_mtime_ns}|{stat.st_size}"

    def _effect_cache_token(self, effect: VideoEffectPreset) -> str:
        if effect.filter_name is None:
            return effect.id
        return f"{effect.id}|{effect.filter_name}|{effect.filter_params or ''}|{self._frei0r_plugin_path(effect) or 'missing'}"

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

    def _effect_available(self, effect: VideoEffectPreset) -> bool:
        return effect.filter_name is None or (
            self._ffmpeg_supports_frei0r()
            and self._frei0r_plugin_path(effect) is not None
            and self._frei0r_filter_compatible(effect)
        )

    def _require_effect_available(self, effect: VideoEffectPreset) -> None:
        if effect.filter_name is None:
            return
        if not self._ffmpeg_supports_frei0r():
            raise VideoEditorError("FFmpeg was not built with frei0r filter support.")
        if self._frei0r_plugin_path(effect) is None:
            raise VideoEditorError(f"frei0r plugin was not found: {effect.filter_name}")
        if not self._frei0r_filter_compatible(effect):
            raise VideoEditorError(f"frei0r plugin is not compatible with the video filter editor: {effect.filter_name}")

    def _ffmpeg_supports_frei0r(self) -> bool:
        if VideoEditorService._ffmpeg_supports_frei0r_cache is not None:
            return VideoEditorService._ffmpeg_supports_frei0r_cache
        if shutil.which("ffmpeg") is None:
            VideoEditorService._ffmpeg_supports_frei0r_cache = False
            return False
        process = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], text=True, capture_output=True, check=False)
        VideoEditorService._ffmpeg_supports_frei0r_cache = process.returncode == 0 and " frei0r " in process.stdout
        return VideoEditorService._ffmpeg_supports_frei0r_cache

    def _frei0r_filter_compatible(self, effect: VideoEffectPreset) -> bool:
        if effect.filter_name is None:
            return True
        cache_key = self._effect_cache_token(effect)
        if cache_key in VideoEditorService._frei0r_filter_compatibility_cache:
            return VideoEditorService._frei0r_filter_compatibility_cache[cache_key]
        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=red:s=64x48:r=10:d=0.2",
            "-vf",
            self._effect_filter(effect),
            "-frames:v",
            "1",
            "-f",
            "null",
            "-",
        ]
        try:
            process = subprocess.run(
                command,
                text=True,
                capture_output=True,
                check=False,
                timeout=self.FREI0R_COMPATIBILITY_TIMEOUT_SECONDS,
            )
            compatible = process.returncode == 0
        except subprocess.TimeoutExpired:
            compatible = False
        VideoEditorService._frei0r_filter_compatibility_cache[cache_key] = compatible
        return compatible

    def _frei0r_plugin_path(self, effect: VideoEffectPreset) -> Path | None:
        if effect.filter_name is None:
            return None
        if effect.filter_name in self._frei0r_plugin_paths_cache:
            return self._frei0r_plugin_paths_cache[effect.filter_name]
        plugin_name = effect.filter_name
        for directory in self._frei0r_search_paths():
            if not directory.is_dir():
                continue
            for suffix in (".so", ".dylib", ".dll"):
                candidate = directory / f"{plugin_name}{suffix}"
                if candidate.is_file():
                    self._frei0r_plugin_paths_cache[plugin_name] = candidate
                    return candidate
        self._frei0r_plugin_paths_cache[plugin_name] = None
        return None

    def _frei0r_search_paths(self) -> list[Path]:
        paths: list[Path] = []
        env_value = os.environ.get("FREI0R_PATH")
        if env_value:
            paths.extend(Path(part) for part in env_value.split(os.pathsep) if part)
        paths.extend(
            [
                Path.home() / ".frei0r-1" / "lib",
                Path("/usr/local/lib/frei0r-1"),
                Path("/usr/lib/frei0r-1"),
            ]
        )
        paths.extend(Path(path) for path in sorted(Path("/usr/lib").glob("*/frei0r-1")))
        unique_paths: list[Path] = []
        seen: set[str] = set()
        for path in paths:
            key = str(path)
            if key not in seen:
                unique_paths.append(path)
                seen.add(key)
        return unique_paths

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
