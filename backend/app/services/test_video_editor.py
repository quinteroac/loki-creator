from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.video_editor import VideoEditorError, VideoEditorService


HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def run(command: list[str]) -> None:
    process = subprocess.run(command, text=True, capture_output=True, check=False)
    if process.returncode != 0:
        raise AssertionError(process.stderr or process.stdout)


def create_clip(path: Path, *, audio: bool = True, color: str = "red", duration: float = 1.2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c={color}:s=64x48:r=10:d={duration}",
    ]
    if audio:
        command.extend(
            [
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency=440:sample_rate=48000:d={duration}",
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
            ]
        )
    else:
        command.extend(["-map", "0:v:0"])
    command.extend(
        [
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(path),
        ]
    )
    run(command)


class VideoEditorValidationTest(unittest.TestCase):
    def test_rejects_non_artifact_urls(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = VideoEditorService(Path(tmpdir))
            with self.assertRaisesRegex(VideoEditorError, "local artifact URLs"):
                service.timeline("file:///tmp/video.mp4")


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg and ffprobe are required")
class VideoEditorFfmpegTest(unittest.TestCase):
    def test_timeline_returns_metadata_and_local_thumbnails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "imports" / "source.mp4"
            create_clip(source)
            service = VideoEditorService(root)

            result = service.timeline("/api/artifacts/imports/source.mp4", max_thumbnails=4)

            self.assertEqual(result.artifact_url, "/api/artifacts/imports/source.mp4")
            self.assertEqual(result.width, 64)
            self.assertEqual(result.height, 48)
            self.assertGreater(result.duration_seconds, 1.0)
            self.assertEqual(len(result.thumbnails), 4)
            for thumbnail in result.thumbnails:
                self.assertTrue(thumbnail.artifact_url.startswith("/api/artifacts/video-editor/timelines/"))
                self.assertTrue((root / thumbnail.artifact_url.removeprefix("/api/artifacts/")).is_file())
                self.assertGreater(thumbnail.width, 0)
                self.assertGreater(thumbnail.height, 0)

    def test_one_second_timeline_does_not_seek_past_last_frame(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "imports" / "short.mp4"
            create_clip(source, duration=1.0)
            service = VideoEditorService(root)

            result = service.timeline("/api/artifacts/imports/short.mp4", max_thumbnails=16)

            self.assertEqual(len(result.thumbnails), 16)
            self.assertLessEqual(result.thumbnails[-1].time_seconds, 0.938)
            for thumbnail in result.thumbnails:
                self.assertTrue((root / thumbnail.artifact_url.removeprefix("/api/artifacts/")).is_file())

    def test_export_frame_creates_png_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "imports" / "source.mp4"
            create_clip(source)
            service = VideoEditorService(root)

            artifact = service.export_frame("/api/artifacts/imports/source.mp4", 0.4)

            output = root / artifact.artifact_url.removeprefix("/api/artifacts/")
            self.assertTrue(output.is_file())
            self.assertEqual(artifact.kind, "image")
            self.assertEqual(artifact.mime_type, "image/png")
            self.assertEqual(artifact.width, 64)
            self.assertEqual(artifact.height, 48)
            self.assertEqual(artifact.source_artifact_url, "/api/artifacts/imports/source.mp4")

    def test_trim_creates_shorter_mp4_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "imports" / "source.mp4"
            create_clip(source, duration=1.6)
            service = VideoEditorService(root)

            artifact = service.trim("/api/artifacts/imports/source.mp4", 0.2, 0.9)

            output = root / artifact.artifact_url.removeprefix("/api/artifacts/")
            self.assertTrue(output.is_file())
            self.assertEqual(artifact.kind, "video")
            self.assertEqual(artifact.mime_type, "video/mp4")
            self.assertEqual(artifact.start_seconds, 0.2)
            self.assertEqual(artifact.end_seconds, 0.9)
            self.assertGreater(artifact.duration_seconds or 0, 0.4)
            self.assertLess(artifact.duration_seconds or 99, 1.1)
            info = VideoEditorService(root).video_info(output)
            self.assertTrue(info["has_audio"])

    def test_trim_rejects_invalid_ranges(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "imports" / "source.mp4"
            create_clip(source)
            service = VideoEditorService(root)

            with self.assertRaisesRegex(VideoEditorError, "greater than or equal to 0"):
                service.trim("/api/artifacts/imports/source.mp4", -0.1, 0.5)
            with self.assertRaisesRegex(VideoEditorError, "greater than startSeconds"):
                service.trim("/api/artifacts/imports/source.mp4", 0.5, 0.5)
            with self.assertRaisesRegex(VideoEditorError, "video duration"):
                service.trim("/api/artifacts/imports/source.mp4", 0.5, 99)


if __name__ == "__main__":
    unittest.main()
