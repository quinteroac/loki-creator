from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ltx_seed_seeker_action


class LtxSeedSeekerActionTest(unittest.TestCase):
    def payload(
        self,
        root: Path,
        *,
        params: dict,
        prompt: str = "slow cinematic camera drift, natural subject motion",
        image_count: int = 1,
    ) -> dict:
        assets = []
        for index in range(1, image_count + 1):
            image = root / "inputs" / f"image-{index}.png"
            image.parent.mkdir(parents=True, exist_ok=True)
            image.write_bytes(b"image")
            assets.append(
                {
                    "kind": "image",
                    "src": f"/api/artifacts/inputs/image-{index}.png",
                    "mimeType": "image/png",
                }
            )
        return {
            "skillId": "ltx-seed-seeker",
            "runId": "skill_run_test",
            "prompt": prompt,
            "params": params,
            "selectedCardSnapshots": [{"name": "Image", "mediaAssets": assets, "metadata": {}}],
        }

    def fake_runner(self, commands: list[list[str]]):
        def run(command: list[str], _cwd: Path) -> dict:
            commands.append(command)
            out_dir = Path(command[command.index("--out") + 1])
            out_dir.mkdir(parents=True, exist_ok=True)
            video = out_dir / "video.mp4"
            video.write_bytes(b"video")
            return {"ok": True, "kind": "video", "artifacts": [str(video)]}

        return run

    def fake_half_scale(self, path: Path, inputs_dir: Path, label: str) -> Path:
        inputs_dir.mkdir(parents=True, exist_ok=True)
        destination = inputs_dir / f"{label}.png"
        destination.write_bytes(Path(path).read_bytes() if Path(path).is_file() else b"image")
        return destination

    def run_with_patches(self, root: Path, commands: list[list[str]]):
        return (
            patch("ltx_seed_seeker_action.comfy_action.artifacts_root", return_value=root),
            patch("ltx_seed_seeker_action.comfy_action.models_dir", return_value=root / "models"),
            patch("ltx_seed_seeker_action.comfy_action.run_command", side_effect=self.fake_runner(commands)),
            patch("ltx_seed_seeker_action.comfy_action.half_scale_image_input", side_effect=self.fake_half_scale),
        )

    def test_preview_i2v_generates_three_360p_seed_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            commands: list[list[str]] = []
            payload = self.payload(
                root,
                params={
                    "runMode": "preview",
                    "modelProfile": "ltx23-10eros",
                    "videoMode": "i2v",
                    "aspectRatio": "16:9",
                    "duration": "5",
                    "seed": "100",
                },
            )
            patches = self.run_with_patches(root, commands)
            with patches[0], patches[1], patches[2], patches[3]:
                result = ltx_seed_seeker_action.run_preview(payload, emit_partials=False)

        self.assertEqual(len(result["artifacts"]), 3)
        self.assertEqual([command[1] for command in commands], ["i2v", "i2v", "i2v"])
        self.assertEqual([command[command.index("--seed") + 1] for command in commands], ["100", "101", "102"])
        self.assertEqual([command[command.index("--width") + 1] for command in commands], ["320", "320", "320"])
        self.assertEqual([command[command.index("--height") + 1] for command in commands], ["176", "176", "176"])
        self.assertTrue(all("--input" in command for command in commands))
        self.assertTrue(commands[0][commands[0].index("--input") + 1].endswith("preview-01-input.png"))
        first_metadata = result["artifacts"][0]["metadata"]
        self.assertEqual(first_metadata["seed"], 100)
        self.assertEqual(first_metadata["resolution"], "360p")
        self.assertEqual(first_metadata["width"], 640)
        self.assertEqual(first_metadata["height"], 352)
        self.assertEqual(first_metadata["requestedWidth"], 640)
        self.assertEqual(first_metadata["requestedHeight"], 360)
        self.assertEqual(first_metadata["cliWidth"], 320)
        self.assertEqual(first_metadata["cliHeight"], 176)
        self.assertEqual(first_metadata["seedSeeker"]["previewCount"], 3)

    def test_preview_rejects_flf2v_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            payload = self.payload(
                root,
                image_count=2,
                params={
                    "runMode": "preview",
                    "modelProfile": "ltx23-dasiwa-golden-lace-v3",
                    "videoMode": "flf2v",
                    "aspectRatio": "9:16",
                    "duration": "3",
                    "seed": "7",
                },
            )
            with self.assertRaisesRegex(RuntimeError, "only supports i2v"):
                ltx_seed_seeker_action.run_preview(payload, emit_partials=False)

    def test_rerender_uses_selected_preview_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "inputs" / "source.png"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"image")
            commands: list[list[str]] = []
            payload = {
                "skillId": "ltx-seed-seeker",
                "runId": "skill_run_final",
                "prompt": "ignored new prompt",
                "params": {"runMode": "rerender", "targetResolution": "1080p"},
                "selectedCardSnapshots": [
                    {
                        "name": "Seed preview",
                        "mediaAssets": [],
                        "metadata": {
                            "seedSeeker": {"mode": "preview"},
                            "seed": 4242,
                            "basePrompt": "stored prompt",
                            "modelProfile": "ltx23-10eros",
                            "videoMode": "i2v",
                            "aspectRatio": "9:16",
                            "duration": 7,
                            "sourceImageArtifactUrls": ["/api/artifacts/inputs/source.png"],
                        },
                    }
                ],
            }
            patches = self.run_with_patches(root, commands)
            with patches[0], patches[1], patches[2], patches[3]:
                result = ltx_seed_seeker_action.run_rerender(payload)

        command = commands[0]
        self.assertEqual(len(result["artifacts"]), 1)
        self.assertEqual(command[command.index("--seed") + 1], "4242")
        self.assertEqual(command[command.index("--prompt") + 1], "stored prompt")
        self.assertEqual(command[command.index("--width") + 1], "528")
        self.assertEqual(command[command.index("--height") + 1], "960")
        self.assertEqual(command[command.index("--length") + 1], str(7 * 24))
        self.assertEqual(result["artifacts"][0]["metadata"]["resolution"], "1080p")
        self.assertEqual(result["artifacts"][0]["metadata"]["width"], 1056)
        self.assertEqual(result["artifacts"][0]["metadata"]["height"], 1920)
        self.assertEqual(result["artifacts"][0]["metadata"]["requestedWidth"], 1080)
        self.assertEqual(result["artifacts"][0]["metadata"]["requestedHeight"], 1920)
        self.assertIn("Seed: 4242", result["artifacts"][0]["prompt"])

    def test_rerender_requires_selected_preview(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "requires selecting one LTX Seed Seeker preview card"):
            ltx_seed_seeker_action.run_rerender(
                {
                    "skillId": "ltx-seed-seeker",
                    "runId": "skill_run_final",
                    "prompt": "prompt",
                    "params": {"runMode": "rerender", "targetResolution": "720p"},
                    "selectedCardSnapshots": [],
                }
            )

    def test_preview_partial_failure_keeps_valid_artifacts_and_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            commands: list[list[str]] = []
            payload = self.payload(
                root,
                params={
                    "runMode": "preview",
                    "modelProfile": "ltx23-10eros",
                    "videoMode": "i2v",
                    "aspectRatio": "16:9",
                    "duration": "5",
                    "seed": "1",
                },
            )

            def run(command: list[str], _cwd: Path) -> dict:
                commands.append(command)
                if len(commands) == 1:
                    raise RuntimeError("first seed failed")
                out_dir = Path(command[command.index("--out") + 1])
                out_dir.mkdir(parents=True, exist_ok=True)
                video = out_dir / "video.mp4"
                video.write_bytes(b"video")
                return {"ok": True, "kind": "video", "artifacts": [str(video)]}

            with (
                patch("ltx_seed_seeker_action.comfy_action.artifacts_root", return_value=root),
                patch("ltx_seed_seeker_action.comfy_action.models_dir", return_value=root / "models"),
                patch("ltx_seed_seeker_action.comfy_action.run_command", side_effect=run),
                patch("ltx_seed_seeker_action.comfy_action.half_scale_image_input", side_effect=self.fake_half_scale),
            ):
                result = ltx_seed_seeker_action.run_preview(payload, emit_partials=False)

        self.assertEqual(len(result["artifacts"]), 2)
        self.assertEqual(len(result["diagnostics"]), 1)
        self.assertEqual(result["diagnostics"][0]["level"], "warning")
        self.assertIn("first seed failed", result["diagnostics"][0]["message"])

    def test_preview_fails_when_no_seed_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            payload = self.payload(
                root,
                params={
                    "runMode": "preview",
                    "modelProfile": "ltx23-10eros",
                    "videoMode": "i2v",
                    "aspectRatio": "16:9",
                    "duration": "5",
                    "seed": "1",
                },
            )
            with (
                patch("ltx_seed_seeker_action.comfy_action.artifacts_root", return_value=root),
                patch("ltx_seed_seeker_action.comfy_action.models_dir", return_value=root / "models"),
                patch("ltx_seed_seeker_action.comfy_action.run_command", side_effect=RuntimeError("all failed")),
                patch("ltx_seed_seeker_action.comfy_action.half_scale_image_input", side_effect=self.fake_half_scale),
            ):
                with self.assertRaisesRegex(RuntimeError, "failed for all seeds"):
                    ltx_seed_seeker_action.run_preview(payload, emit_partials=False)


if __name__ == "__main__":
    unittest.main()
