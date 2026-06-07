from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parent))

import hyperframes_text_video_action as action


def valid_script(**overrides: object) -> dict:
    script = {
        "durationSeconds": 3,
        "fps": 30,
        "backgroundFit": "cover",
        "blocks": [
            {
                "kind": "title",
                "text": "Launch Night",
                "start": 0,
                "duration": 1.5,
                "preset": "title-card",
                "position": "center",
            }
        ],
    }
    script.update(overrides)
    return script


class HyperFramesTextVideoActionTest(unittest.TestCase):
    def valid_params(self, **overrides: object) -> dict:
        params = {
            "scriptJson": valid_script(),
            "title": "Animated title",
            "videoResolution": "720p",
            "aspectRatio": "9:16",
        }
        params.update(overrides)
        return params

    def payload(self, root: Path, media: Path, *, kind: str = "image", params: dict | None = None) -> dict:
        return {
            "runId": "skill_run_test",
            "skillId": "hyperframes-text-video",
            "prompt": "add animated text",
            "params": params or self.valid_params(),
            "selectedCardSnapshots": [
                {
                    "name": media.name,
                    "mediaAssets": [
                        {
                            "kind": kind,
                            "src": f"/api/artifacts/{media.relative_to(root).as_posix()}",
                            "mimeType": "image/png" if kind == "image" else "video/mp4",
                        }
                    ],
                    "metadata": {},
                }
            ],
        }

    def test_image_background_generates_project_and_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(os.environ, {"LOKI_ARTIFACTS_ROOT": tmpdir}):
            root = Path(tmpdir)
            image = root / "imports" / "background.png"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"image")

            def fake_render(project_dir: Path, output_path: Path, fps: int) -> None:
                self.assertEqual(fps, 30)
                index_html = (project_dir / "index.html").read_text(encoding="utf-8")
                self.assertIn('data-duration="3"', index_html)
                self.assertIn('data-duration="1.5"', index_html)
                self.assertIn('id="duration-anchor"', index_html)
                self.assertIn("duration() { return durationSeconds; }", index_html)
                self.assertIn("renderAt(this.currentTime * 1000);", index_html)
                self.assertNotIn('data-duration="3000"', index_html)
                self.assertNotIn('data-duration="1500"', index_html)
                output_path.write_bytes(b"rendered")

            with (
                patch("hyperframes_text_video_action.require_tools"),
                patch("hyperframes_text_video_action.image_info", return_value={"width": 1080, "height": 1920}),
                patch("hyperframes_text_video_action.render_hyperframes", side_effect=fake_render),
            ):
                result = action.create_text_video(self.payload(root, image))

            artifact = result["artifacts"][0]
            output = Path(artifact["path"])
            self.assertTrue(output.is_file())
            self.assertEqual(output.read_bytes(), b"rendered")
            self.assertEqual(artifact["kind"], "video")
            self.assertEqual(artifact["mimeType"], "video/mp4")
            self.assertEqual(artifact["metadata"]["backgroundKind"], "image")
            self.assertEqual(artifact["metadata"]["blockCount"], 1)
            self.assertEqual(artifact["metadata"]["videoResolution"], "720p")
            self.assertEqual(artifact["metadata"]["aspectRatio"], "9:16")
            self.assertEqual(artifact["metadata"]["width"], 720)
            self.assertEqual(artifact["metadata"]["height"], 1280)

    def test_video_background_with_audio_muxes_original_audio(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(os.environ, {"LOKI_ARTIFACTS_ROOT": tmpdir}):
            root = Path(tmpdir)
            video = root / "imports" / "background.mp4"
            video.parent.mkdir(parents=True)
            video.write_bytes(b"video")

            def fake_render(_project_dir: Path, output_path: Path, _fps: int) -> None:
                output_path.write_bytes(b"rendered")

            def fake_mux(rendered: Path, source: Path, destination: Path, duration: float) -> None:
                self.assertEqual(rendered.read_bytes(), b"rendered")
                self.assertEqual(source, video)
                self.assertEqual(duration, 2.0)
                destination.write_bytes(b"muxed")

            payload = self.payload(root, video, kind="video", params=self.valid_params(scriptJson=valid_script(durationSeconds=2)))
            with (
                patch("hyperframes_text_video_action.require_tools"),
                patch(
                    "hyperframes_text_video_action.video_info",
                    return_value={"duration": 2.0, "fps": 24.0, "width": 1920, "height": 1080, "hasAudio": True},
                ),
                patch("hyperframes_text_video_action.render_hyperframes", side_effect=fake_render),
                patch("hyperframes_text_video_action.mux_original_audio", side_effect=fake_mux),
            ):
                result = action.create_text_video(payload)

            artifact = result["artifacts"][0]
            self.assertEqual(Path(artifact["path"]).read_bytes(), b"muxed")
            self.assertEqual(artifact["metadata"]["backgroundKind"], "video")
            self.assertEqual(artifact["metadata"]["hasAudio"], True)

    def test_preview_only_media_fails_before_render(self) -> None:
        payload = {
            "runId": "skill_run_preview",
            "skillId": "hyperframes-text-video",
            "params": self.valid_params(),
            "selectedCardSnapshots": [
                {
                    "mediaAssets": [
                        {
                            "kind": "image",
                            "dataUrl": "data:image/png;base64,aW1hZ2U=",
                        }
                    ]
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(os.environ, {"LOKI_ARTIFACTS_ROOT": tmpdir}):
            with self.assertRaisesRegex(RuntimeError, "preview/dataUrl"):
                action.selected_background(payload)

    def test_requires_exactly_one_background(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(os.environ, {"LOKI_ARTIFACTS_ROOT": tmpdir}):
            root = Path(tmpdir)
            first = root / "imports" / "one.png"
            second = root / "imports" / "two.png"
            first.parent.mkdir(parents=True)
            first.write_bytes(b"one")
            second.write_bytes(b"two")

            with self.assertRaisesRegex(RuntimeError, "requires exactly one selected"):
                action.selected_background({"selectedCardSnapshots": []})

            payload = {
                "selectedCardSnapshots": [
                    {
                        "mediaAssets": [
                            {"kind": "image", "src": "/api/artifacts/imports/one.png"},
                            {"kind": "image", "src": "/api/artifacts/imports/two.png"},
                        ]
                    }
                ]
            }
            with self.assertRaisesRegex(RuntimeError, "multiple selected"):
                action.selected_background(payload)

    def test_script_json_validation(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "valid JSON"):
            action.parse_json_object("{bad", "params.scriptJson")

        with self.assertRaisesRegex(RuntimeError, "at least one"):
            action.validate_script(
                {"durationSeconds": 2, "blocks": []},
                background_kind="image",
                media={"width": 100, "height": 100},
                params=self.valid_params(),
            )

        with self.assertRaisesRegex(RuntimeError, "timing exceeds"):
            action.validate_script(
                valid_script(durationSeconds=1),
                background_kind="image",
                media={"width": 100, "height": 100},
                params=self.valid_params(),
            )

        with self.assertRaisesRegex(RuntimeError, "videoResolution"):
            action.validate_script(
                valid_script(),
                background_kind="image",
                media={"width": 100, "height": 100},
                params={"scriptJson": valid_script(), "aspectRatio": "9:16"},
            )

        with self.assertRaisesRegex(RuntimeError, "aspectRatio"):
            action.validate_script(
                valid_script(),
                background_kind="image",
                media={"width": 100, "height": 100},
                params={"scriptJson": valid_script(), "videoResolution": "720p"},
            )

    def test_missing_expected_render_output_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "project"
            output_path = Path(tmpdir) / "outputs" / "missing.mp4"
            output_path.parent.mkdir(parents=True)
            commands: list[list[str]] = []

            def fake_run(command: list[str], *, cwd: Path | None = None) -> None:
                commands.append(command)

            with patch("hyperframes_text_video_action.run_command", side_effect=fake_run):
                with self.assertRaisesRegex(RuntimeError, "did not create expected output"):
                    action.render_hyperframes(project_dir, output_path, 30)

        self.assertEqual(commands[0][:4], ["npx", "--yes", "hyperframes@0.6.79", "lint"])
        self.assertIn("render", commands[-1])
        self.assertIn(str(output_path), commands[-1])


if __name__ == "__main__":
    unittest.main()
