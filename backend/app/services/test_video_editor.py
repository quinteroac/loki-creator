from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.video_editor import INSTALLED_FREI0R_EFFECT_IDS, VideoEditorError, VideoEditorService


HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
HAS_FREI0R = HAS_FFMPEG and any(effect.available for effect in VideoEditorService(Path(tempfile.gettempdir())).list_effects() if effect.id != "none")


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

    def test_lut_catalog_returns_original_and_prepackaged_luts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = VideoEditorService(Path(tmpdir))

            catalog = service.list_luts()

            self.assertEqual(catalog[0].id, "original")
            self.assertIn("cinematic", {lut.id for lut in catalog})
            self.assertIn("film-warm", {lut.id for lut in catalog})
            self.assertIn("teal-orange", {lut.id for lut in catalog})
            self.assertIn("blue-boost", {lut.id for lut in catalog})
            self.assertIn("soft-fade", {lut.id for lut in catalog})
            self.assertIn("clean-contrast", {lut.id for lut in catalog})
            self.assertIn("mono", {lut.id for lut in catalog})

    def test_lut_catalog_includes_installed_local_luts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".loki"
            installed = root / "video-luts" / "imported" / "test-pack" / "Cool Look.cube"
            installed.parent.mkdir(parents=True)
            shutil.copyfile(
                Path(__file__).resolve().parents[1] / "assets" / "video_luts" / "mono.cube",
                installed,
            )
            service = VideoEditorService(root)

            catalog = service.list_luts()
            installed_lut = next(lut for lut in catalog if lut.label == "test-pack - Cool Look")

            self.assertTrue(installed_lut.id.startswith("imported-test-pack-cool-look-"))

    def test_effect_catalog_returns_none_and_installed_frei0r_allowlist(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = VideoEditorService(Path(tmpdir))

            catalog = service.list_effects()
            by_id = {effect.id: effect for effect in catalog}

            self.assertTrue(by_id["none"].available)
            for effect_id in INSTALLED_FREI0R_EFFECT_IDS:
                self.assertIn(effect_id, by_id)

    def test_effect_catalog_only_marks_filter_compatible_plugins_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = VideoEditorService(Path(tmpdir))
            catalog = {effect.id: effect for effect in service.list_effects()}

            has_frei0r = service._ffmpeg_supports_frei0r()
            if has_frei0r and service._frei0r_plugin_path(next(effect for effect in service.EFFECT_PRESETS if effect.id == "glow")):
                self.assertTrue(catalog["glow"].available)
            if has_frei0r and service._frei0r_plugin_path(next(effect for effect in service.EFFECT_PRESETS if effect.id == "pixeliz0r")):
                self.assertTrue(catalog["pixeliz0r"].available)
            if has_frei0r and service._frei0r_plugin_path(next(effect for effect in service.EFFECT_PRESETS if effect.id == "cartoon")):
                self.assertTrue(catalog["cartoon"].available)
            if has_frei0r and service._frei0r_plugin_path(next(effect for effect in service.EFFECT_PRESETS if effect.id == "blend")):
                self.assertFalse(catalog["blend"].available)
            if has_frei0r and service._frei0r_plugin_path(next(effect for effect in service.EFFECT_PRESETS if effect.id == "xfade0r")):
                self.assertFalse(catalog["xfade0r"].available)

    def test_rejects_unknown_effect_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = VideoEditorService(Path(tmpdir))

            with self.assertRaisesRegex(VideoEditorError, "Unknown video effect"):
                service._resolve_effect("freeform-filter")

    def test_video_filter_combines_lut_frei0r_and_scale_in_stable_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = VideoEditorService(Path(tmpdir))
            lut = service._resolve_lut("mono")
            effect = next(candidate for candidate in service.EFFECT_PRESETS if candidate.id == "pixeliz0r")

            filter_value = service._video_filter(lut, effect, "scale=360:-2")

            self.assertRegex(
                filter_value,
                r"^lut3d=file=.*mono\.cube:interp=tetrahedral,frei0r=filter_name=pixeliz0r,scale=360:-2$",
            )


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

    def test_timeline_with_lut_uses_separate_thumbnail_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "imports" / "source.mp4"
            create_clip(source)
            service = VideoEditorService(root)

            original = service.timeline("/api/artifacts/imports/source.mp4", max_thumbnails=3)
            graded = service.timeline("/api/artifacts/imports/source.mp4", max_thumbnails=3, lut_id="film-warm")

            self.assertEqual(len(original.thumbnails), 3)
            self.assertEqual(len(graded.thumbnails), 3)
            self.assertNotEqual(original.thumbnails[0].artifact_url, graded.thumbnails[0].artifact_url)
            self.assertTrue((root / graded.thumbnails[0].artifact_url.removeprefix("/api/artifacts/")).is_file())

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
            self.assertEqual(artifact.effect_id, "none")
            self.assertEqual(artifact.effect_label, "None")

    def test_export_frame_at_duration_uses_last_decodable_frame(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "imports" / "source.mp4"
            create_clip(source)
            service = VideoEditorService(root)
            duration = float(service.video_info(source)["duration"])

            artifact = service.export_frame("/api/artifacts/imports/source.mp4", duration)

            output = root / artifact.artifact_url.removeprefix("/api/artifacts/")
            self.assertTrue(output.is_file())
            self.assertEqual(artifact.kind, "image")
            self.assertLess(artifact.time_seconds or 99, duration)

    def test_export_frame_with_lut_creates_png_artifact_with_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "imports" / "source.mp4"
            create_clip(source)
            service = VideoEditorService(root)

            artifact = service.export_frame("/api/artifacts/imports/source.mp4", 0.4, lut_id="mono")

            output = root / artifact.artifact_url.removeprefix("/api/artifacts/")
            self.assertTrue(output.is_file())
            self.assertEqual(artifact.kind, "image")
            self.assertEqual(artifact.mime_type, "image/png")
            self.assertEqual(artifact.lut_id, "mono")
            self.assertEqual(artifact.lut_label, "Mono")

    def test_export_frame_with_installed_lut_creates_png_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "imports" / "source.mp4"
            installed = root / "video-luts" / "imported" / "test-pack" / "Cool Look.cube"
            installed.parent.mkdir(parents=True)
            create_clip(source)
            shutil.copyfile(
                Path(__file__).resolve().parents[1] / "assets" / "video_luts" / "mono.cube",
                installed,
            )
            service = VideoEditorService(root)
            installed_lut = next(lut for lut in service.list_luts() if lut.label == "test-pack - Cool Look")

            artifact = service.export_frame("/api/artifacts/imports/source.mp4", 0.4, lut_id=installed_lut.id)

            output = root / artifact.artifact_url.removeprefix("/api/artifacts/")
            self.assertTrue(output.is_file())
            self.assertEqual(artifact.kind, "image")
            self.assertEqual(artifact.lut_id, installed_lut.id)
            self.assertEqual(artifact.lut_label, "test-pack - Cool Look")

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

    def test_trim_with_lut_creates_mp4_and_preserves_audio(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "imports" / "source.mp4"
            create_clip(source, duration=1.6)
            service = VideoEditorService(root)

            artifact = service.trim("/api/artifacts/imports/source.mp4", 0.2, 0.9, lut_id="teal-orange")

            output = root / artifact.artifact_url.removeprefix("/api/artifacts/")
            self.assertTrue(output.is_file())
            self.assertEqual(artifact.kind, "video")
            self.assertEqual(artifact.mime_type, "video/mp4")
            self.assertEqual(artifact.lut_id, "teal-orange")
            self.assertEqual(artifact.lut_label, "Teal Orange")
            self.assertEqual(artifact.effect_id, "none")
            self.assertEqual(artifact.effect_label, "None")
            info = VideoEditorService(root).video_info(output)
            self.assertTrue(info["has_audio"])

    def test_rejects_unknown_lut_ids_and_external_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "imports" / "source.mp4"
            create_clip(source)
            service = VideoEditorService(root)

            with self.assertRaisesRegex(VideoEditorError, "Unknown video LUT"):
                service.timeline("/api/artifacts/imports/source.mp4", max_thumbnails=1, lut_id="missing")
            with self.assertRaisesRegex(VideoEditorError, "Unknown video LUT"):
                service.export_frame("/api/artifacts/imports/source.mp4", 0.2, lut_id="/tmp/look.cube")

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

    def test_rejects_frei0r_plugins_that_are_not_simple_video_filters(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "imports" / "source.mp4"
            create_clip(source)
            service = VideoEditorService(root)
            blend = next(effect for effect in service.EFFECT_PRESETS if effect.id == "blend")
            if service._frei0r_plugin_path(blend) is None:
                self.skipTest("blend frei0r plugin is not installed")

            with self.assertRaisesRegex(VideoEditorError, "not compatible"):
                service.timeline("/api/artifacts/imports/source.mp4", max_thumbnails=1, effect_id="blend")
            with self.assertRaisesRegex(VideoEditorError, "not compatible"):
                service.export_frame("/api/artifacts/imports/source.mp4", 0.2, effect_id="blend")
            with self.assertRaisesRegex(VideoEditorError, "not compatible"):
                service.trim("/api/artifacts/imports/source.mp4", 0.1, 0.6, effect_id="blend")


@unittest.skipUnless(HAS_FREI0R, "ffmpeg, ffprobe, and at least one frei0r plugin are required")
class VideoEditorFrei0rTest(unittest.TestCase):
    def test_frei0r_effect_creates_timeline_frame_and_trim_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "imports" / "source.mp4"
            create_clip(source, duration=1.6)
            service = VideoEditorService(root)
            effect = next(candidate for candidate in service.list_effects() if candidate.id == "glow" and candidate.available)

            timeline = service.timeline("/api/artifacts/imports/source.mp4", max_thumbnails=2, effect_id=effect.id)
            frame = service.export_frame("/api/artifacts/imports/source.mp4", 0.3, effect_id=effect.id)
            trim = service.trim("/api/artifacts/imports/source.mp4", 0.2, 0.8, effect_id=effect.id)

            self.assertEqual(len(timeline.thumbnails), 2)
            self.assertTrue((root / timeline.thumbnails[0].artifact_url.removeprefix("/api/artifacts/")).is_file())
            self.assertTrue((root / frame.artifact_url.removeprefix("/api/artifacts/")).is_file())
            self.assertEqual(frame.effect_id, effect.id)
            self.assertEqual(frame.effect_label, effect.label)
            self.assertTrue((root / trim.artifact_url.removeprefix("/api/artifacts/")).is_file())
            self.assertEqual(trim.effect_id, effect.id)
            self.assertEqual(trim.effect_label, effect.label)
            self.assertTrue(service.video_info(root / trim.artifact_url.removeprefix("/api/artifacts/"))["has_audio"])


if __name__ == "__main__":
    unittest.main()
