from __future__ import annotations

import base64
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parent))

import media_cleanup_action


HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def run(command: list[str]) -> None:
    process = subprocess.run(command, text=True, capture_output=True, check=False)
    if process.returncode != 0:
        raise AssertionError(process.stderr or process.stdout)


def create_image(path: Path, *, color: str = "red", size = "64x48") -> None:
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={color}:s={size}", "-frames:v", "1", str(path)])


def create_video(path: Path, *, color: str = "red", duration: float = 0.8) -> None:
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s=64x48:r=10:d={duration}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:sample_rate=48000:d={duration}",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
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


def artifact_url(root: Path, path: Path) -> str:
    return f"/api/artifacts/{path.relative_to(root).as_posix()}"


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg and ffprobe are required")
class MediaCleanupFfmpegTest(unittest.TestCase):
    def image_payload(self, root: Path, image: Path, operation: str, regions_json: str, **params: object) -> dict:
        return {
            "runId": f"skill_run_{operation.replace('-', '_')}",
            "skillId": "media-cleanup",
            "prompt": "clean selected media",
            "params": {"operation": operation, "regionsJson": regions_json, **params},
            "selectedCardSnapshots": [
                {
                    "name": image.stem,
                    "mediaAssets": [{"kind": "image", "src": artifact_url(root, image)}],
                }
            ],
        }

    def test_cover_regions_on_image_returns_png_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(os.environ, {"LOKI_ARTIFACTS_ROOT": tmpdir}):
            root = Path(tmpdir)
            image = root / "imports" / "image.png"
            image.parent.mkdir(parents=True)
            create_image(image)

            result = media_cleanup_action.cleanup_selected_media(
                self.image_payload(root, image, "cover-regions", '[{"x":0,"y":0,"width":0.5,"height":0.5}]')
            )
            artifact = result["artifacts"][0]

            self.assertEqual(artifact["kind"], "image")
            self.assertEqual(artifact["mimeType"], "image/png")
            self.assertTrue(Path(artifact["path"]).is_file())
            self.assertEqual(artifact["metadata"]["operation"], "cover-regions")
            self.assertEqual(artifact["metadata"]["width"], 64)
            self.assertEqual(artifact["metadata"]["height"], 48)
            self.assertIn("unsupported", result["diagnostics"][0]["message"])

    def test_crop_image_changes_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(os.environ, {"LOKI_ARTIFACTS_ROOT": tmpdir}):
            root = Path(tmpdir)
            image = root / "imports" / "image.png"
            image.parent.mkdir(parents=True)
            create_image(image)

            result = media_cleanup_action.cleanup_selected_media(
                self.image_payload(root, image, "crop", '{"x":0,"y":0,"width":0.5,"height":0.5}')
            )
            artifact = result["artifacts"][0]

            self.assertEqual(artifact["kind"], "image")
            self.assertEqual(artifact["metadata"]["width"], 32)
            self.assertEqual(artifact["metadata"]["height"], 24)

    def test_blur_regions_on_video_preserves_video_kind(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(os.environ, {"LOKI_ARTIFACTS_ROOT": tmpdir}):
            root = Path(tmpdir)
            video = root / "imports" / "video.mp4"
            video.parent.mkdir(parents=True)
            create_video(video)
            payload = {
                "runId": "skill_run_video_blur",
                "skillId": "media-cleanup",
                "prompt": "blur a private area",
                "params": {
                    "operation": "blur-regions",
                    "regionsJson": '[{"x":0.1,"y":0.1,"width":0.5,"height":0.5}]',
                    "blurRadius": 8,
                },
                "selectedCardSnapshots": [
                    {
                        "name": "video",
                        "metadata": {"kind": "video", "artifactUrl": artifact_url(root, video)},
                    }
                ],
            }

            result = media_cleanup_action.cleanup_selected_media(payload)
            artifact = result["artifacts"][0]

            self.assertEqual(artifact["kind"], "video")
            self.assertEqual(artifact["mimeType"], "video/mp4")
            self.assertTrue(Path(artifact["path"]).is_file())
            info = media_cleanup_action.media_info(Path(artifact["path"]))
            self.assertEqual(info["width"], 64)
            self.assertEqual(info["height"], 48)
            self.assertTrue(info["has_audio"])

    def test_attachment_data_url_can_be_used_as_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(os.environ, {"LOKI_ARTIFACTS_ROOT": tmpdir}):
            root = Path(tmpdir)
            image = root / "image.png"
            create_image(image)
            data_url = "data:image/png;base64," + base64.b64encode(image.read_bytes()).decode("ascii")
            payload = {
                "runId": "skill_run_attachment",
                "skillId": "media-cleanup",
                "prompt": "cover private area",
                "params": {
                    "operation": "cover-regions",
                    "regionsJson": '[{"x":0,"y":0,"width":0.25,"height":0.25}]',
                },
                "selectedCardSnapshots": [],
                "attachments": [
                    {
                        "kind": "image",
                        "mimeType": "image/png",
                        "dataUrl": data_url,
                    }
                ],
            }

            result = media_cleanup_action.cleanup_selected_media(payload)

            self.assertEqual(result["artifacts"][0]["kind"], "image")
            self.assertTrue(Path(result["artifacts"][0]["path"]).is_file())


if __name__ == "__main__":
    unittest.main()
