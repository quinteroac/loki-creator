from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.audio_editor import AudioEditorError, AudioEditorService


HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def run(command: list[str]) -> None:
    process = subprocess.run(command, text=True, capture_output=True, check=False)
    if process.returncode != 0:
        raise AssertionError(process.stderr or process.stdout)


def create_audio(path: Path, *, duration: float = 1.4) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:sample_rate=48000:d={duration}",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            str(path),
        ]
    )


class AudioEditorValidationTest(unittest.TestCase):
    def test_rejects_non_artifact_urls(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = AudioEditorService(Path(tmpdir))
            with self.assertRaisesRegex(AudioEditorError, "local artifact URLs"):
                service.timeline("file:///tmp/audio.m4a")

    def test_rejects_archived_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            archived = root / "deleted" / "source.m4a"
            archived.parent.mkdir(parents=True)
            archived.write_bytes(b"archived")
            service = AudioEditorService(root)

            with self.assertRaisesRegex(AudioEditorError, "Archived artifacts"):
                service.timeline("/api/artifacts/deleted/source.m4a")


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg and ffprobe are required")
class AudioEditorFfmpegTest(unittest.TestCase):
    def test_timeline_returns_metadata_and_normalized_peaks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "imports" / "source.m4a"
            create_audio(source)
            service = AudioEditorService(root)

            result = service.timeline("/api/artifacts/imports/source.m4a", max_peaks=16)

            self.assertEqual(result.artifact_url, "/api/artifacts/imports/source.m4a")
            self.assertGreater(result.duration_seconds, 1.0)
            self.assertEqual(result.sample_rate, 48000)
            self.assertEqual(result.channels, 1)
            self.assertGreater(len(result.peaks), 0)
            self.assertLessEqual(len(result.peaks), 16)
            for peak in result.peaks:
                self.assertGreaterEqual(peak, 0)
                self.assertLessEqual(peak, 1)

    def test_trim_creates_m4a_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "imports" / "source.m4a"
            create_audio(source, duration=1.8)
            service = AudioEditorService(root)

            artifact = service.trim("/api/artifacts/imports/source.m4a", 0.2, 0.9)

            output = root / artifact.artifact_url.removeprefix("/api/artifacts/")
            self.assertTrue(output.is_file())
            self.assertEqual(artifact.kind, "audio")
            self.assertEqual(artifact.mime_type, "audio/mp4")
            self.assertEqual(artifact.start_seconds, 0.2)
            self.assertEqual(artifact.end_seconds, 0.9)
            self.assertEqual(artifact.sample_rate, 48000)
            self.assertEqual(artifact.channels, 2)
            self.assertGreater(artifact.duration_seconds or 0, 0.4)
            self.assertLess(artifact.duration_seconds or 99, 1.1)

    def test_trim_rejects_invalid_ranges(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "imports" / "source.m4a"
            create_audio(source)
            service = AudioEditorService(root)

            with self.assertRaisesRegex(AudioEditorError, "greater than or equal to 0"):
                service.trim("/api/artifacts/imports/source.m4a", -0.1, 0.5)
            with self.assertRaisesRegex(AudioEditorError, "greater than startSeconds"):
                service.trim("/api/artifacts/imports/source.m4a", 0.5, 0.5)
            with self.assertRaisesRegex(AudioEditorError, "audio duration"):
                service.trim("/api/artifacts/imports/source.m4a", 0.5, 99)

    def test_rejects_non_audio_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "imports" / "source.txt"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text("not audio")
            service = AudioEditorService(root)

            with self.assertRaisesRegex(AudioEditorError, "Could not inspect audio"):
                service.timeline("/api/artifacts/imports/source.txt")


if __name__ == "__main__":
    unittest.main()
