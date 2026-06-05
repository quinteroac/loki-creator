from __future__ import annotations

import json
import math
import shutil
import subprocess
import sys
from array import array
from pathlib import Path
from uuid import uuid4

from app.models import AudioTimelineResponse, VideoEditArtifact


class AudioEditorError(RuntimeError):
    pass


class AudioEditorService:
    DEFAULT_PEAKS = 160
    MAX_PEAKS = 512
    MIN_TRIM_SECONDS = 0.1
    WAVEFORM_SAMPLE_RATE = 8000

    def __init__(self, artifacts_root: Path) -> None:
        self.artifacts_root = artifacts_root.resolve()
        self.deleted_root = self.artifacts_root / "deleted"
        self.editor_root = self.artifacts_root / "audio-editor"

    def timeline(self, artifact_url: str, max_peaks: int | None = None) -> AudioTimelineResponse:
        source = self._resolve_artifact_url(artifact_url)
        self._require_tools()
        info = self.audio_info(source)
        peak_count = self._peak_count(max_peaks)

        return AudioTimelineResponse(
            artifactUrl=artifact_url,
            durationSeconds=float(info["duration"]),
            sampleRate=int(info["sampleRate"]),
            channels=int(info["channels"]),
            peaks=self._waveform_peaks(source, peak_count),
        )

    def trim(self, artifact_url: str, start_seconds: float, end_seconds: float) -> VideoEditArtifact:
        source = self._resolve_artifact_url(artifact_url)
        self._require_tools()
        info = self.audio_info(source)
        start, end = self._validate_trim_range(start_seconds, end_seconds, float(info["duration"]))
        output_dir = self.editor_root / "exports" / uuid4().hex
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{source.stem}-trim-{self._milliseconds(start)}-{self._milliseconds(end)}.m4a"

        self._run_command(
            [
                "ffmpeg",
                "-y",
                "-ss",
                self._format_seconds(start),
                "-i",
                str(source),
                "-t",
                self._format_seconds(end - start),
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
                str(output_path),
            ]
        )
        if not output_path.is_file():
            raise AudioEditorError("ffmpeg did not create the requested trim artifact.")

        output_info = self.audio_info(output_path)
        return VideoEditArtifact(
            artifactUrl=self._artifact_url_for_path(output_path),
            sourceArtifactUrl=artifact_url,
            name=f"{source.stem} trim",
            kind="audio",
            mimeType="audio/mp4",
            size=output_path.stat().st_size,
            durationSeconds=float(output_info["duration"]),
            startSeconds=start,
            endSeconds=end,
            sampleRate=int(output_info["sampleRate"]),
            channels=int(output_info["channels"]),
        )

    def audio_info(self, path: Path) -> dict[str, object]:
        probe = self._ffprobe(path)
        audio_stream = self._first_stream(probe, "audio")
        if audio_stream is None:
            raise AudioEditorError(f"Selected artifact is not an audio file: {path.name}")

        format_info = probe.get("format") if isinstance(probe.get("format"), dict) else {}
        duration = self._parse_duration(audio_stream.get("duration")) or self._parse_duration(format_info.get("duration"))
        sample_rate = self._parse_positive_int(audio_stream.get("sample_rate"))
        channels = self._parse_positive_int(audio_stream.get("channels"))
        if duration is None:
            raise AudioEditorError(f"Could not read audio duration: {path.name}")
        if sample_rate is None:
            raise AudioEditorError(f"Could not read audio sample rate: {path.name}")
        if channels is None:
            raise AudioEditorError(f"Could not read audio channel count: {path.name}")

        return {
            "duration": duration,
            "sampleRate": sample_rate,
            "channels": channels,
        }

    def _resolve_artifact_url(self, artifact_url: str) -> Path:
        if not artifact_url.startswith("/api/artifacts/"):
            raise AudioEditorError("Audio editing only supports local artifact URLs.")

        artifact = (self.artifacts_root / artifact_url.removeprefix("/api/artifacts/")).resolve()
        try:
            artifact.relative_to(self.artifacts_root)
        except ValueError as exc:
            raise AudioEditorError("Artifact URL is outside the Loki artifacts directory.") from exc

        try:
            artifact.relative_to(self.deleted_root)
            raise AudioEditorError("Archived artifacts cannot be edited.")
        except ValueError:
            pass

        if not artifact.is_file():
            raise AudioEditorError("Artifact file was not found.")
        return artifact

    def _artifact_url_for_path(self, path: Path) -> str:
        return f"/api/artifacts/{path.resolve().relative_to(self.artifacts_root).as_posix()}"

    def _peak_count(self, value: int | None) -> int:
        if value is None:
            return self.DEFAULT_PEAKS
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise AudioEditorError("maxPeaks must be a number.") from exc
        return min(max(1, parsed), self.MAX_PEAKS)

    def _waveform_peaks(self, source: Path, max_peaks: int) -> list[float]:
        process = subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(source),
                "-vn",
                "-ac",
                "1",
                "-ar",
                str(self.WAVEFORM_SAMPLE_RATE),
                "-f",
                "s16le",
                "pipe:1",
            ],
            capture_output=True,
            check=False,
        )
        if process.returncode != 0:
            message = process.stderr.decode("utf-8", errors="replace").strip() or "ffmpeg failed"
            raise AudioEditorError(f"Could not decode audio waveform: {message[-2000:]}")

        samples = array("h")
        samples.frombytes(process.stdout)
        if sys.byteorder != "little":
            samples.byteswap()
        if not samples:
            raise AudioEditorError("Could not decode audio waveform.")

        peak_count = min(max_peaks, len(samples))
        bucket_size = max(1, math.ceil(len(samples) / peak_count))
        raw_peaks: list[float] = []
        for start in range(0, len(samples), bucket_size):
            bucket = samples[start : start + bucket_size]
            raw_peaks.append(max(abs(sample) for sample in bucket) / 32768)

        max_peak = max(raw_peaks) if raw_peaks else 0
        if max_peak <= 0:
            return [0 for _ in raw_peaks]
        return [round(min(1, peak / max_peak), 4) for peak in raw_peaks]

    def _validate_trim_range(self, start_value: float, end_value: float, duration: float) -> tuple[float, float]:
        try:
            start = float(start_value)
            end = float(end_value)
        except (TypeError, ValueError) as exc:
            raise AudioEditorError("Trim start and end times must be numbers.") from exc
        if not math.isfinite(start) or not math.isfinite(end):
            raise AudioEditorError("Trim start and end times must be finite.")
        if start < 0:
            raise AudioEditorError("Trim startSeconds must be greater than or equal to 0.")
        if end <= start:
            raise AudioEditorError("Trim endSeconds must be greater than startSeconds.")
        if end - start < self.MIN_TRIM_SECONDS:
            raise AudioEditorError("Trim range is too short.")
        if end > duration:
            raise AudioEditorError("Trim endSeconds cannot be greater than the audio duration.")
        return start, end

    def _require_tools(self) -> None:
        missing = [tool for tool in ("ffmpeg", "ffprobe") if shutil.which(tool) is None]
        if missing:
            raise AudioEditorError(f"Missing required tool(s): {', '.join(missing)}")

    def _run_command(self, command: list[str]) -> None:
        process = subprocess.run(command, text=True, capture_output=True, check=False)
        if process.returncode != 0:
            message = process.stderr.strip() or process.stdout.strip() or "command failed"
            raise AudioEditorError(f"{command[0]} failed: {message[-2000:]}")

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
            raise AudioEditorError(f"Could not inspect audio {path.name}: {message}")
        return json.loads(process.stdout or "{}")

    def _first_stream(self, probe: dict, codec_type: str) -> dict | None:
        streams = probe.get("streams")
        if not isinstance(streams, list):
            return None
        for stream in streams:
            if isinstance(stream, dict) and stream.get("codec_type") == codec_type:
                return stream
        return None

    def _parse_duration(self, value: object) -> float | None:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    def _parse_positive_int(self, value: object) -> int | None:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    def _format_seconds(self, value: float) -> str:
        return f"{value:.6f}".rstrip("0").rstrip(".") or "0"

    def _milliseconds(self, value: float) -> int:
        return max(0, int(round(value * 1000)))
