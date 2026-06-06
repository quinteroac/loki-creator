from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import wan_seed_seeker_action


class WanSeedSeekerActionTest(unittest.TestCase):
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
            "skillId": "wan-seed-seeker",
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

    def run_with_patches(self, root: Path, commands: list[list[str]]):
        return (
            patch("wan_seed_seeker_action.comfy_action.artifacts_root", return_value=root),
            patch("wan_seed_seeker_action.comfy_action.models_dir", return_value=root / "models"),
            patch("wan_seed_seeker_action.comfy_action.run_command", side_effect=self.fake_runner(commands)),
        )

    def test_preview_i2v_generates_three_direct_360p_seed_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            commands: list[list[str]] = []
            payload = self.payload(
                root,
                params={
                    "runMode": "preview",
                    "modelProfile": "wan22-i2v",
                    "videoMode": "i2v",
                    "aspectRatio": "16:9",
                    "duration": "5",
                    "seed": "100",
                },
            )
            patches = self.run_with_patches(root, commands)
            with patches[0], patches[1], patches[2]:
                result = wan_seed_seeker_action.run_preview(payload, emit_partials=False)

        self.assertEqual(len(result["artifacts"]), 3)
        self.assertEqual([command[1] for command in commands], ["wan22-i2v", "wan22-i2v", "wan22-i2v"])
        self.assertEqual([command[command.index("--seed") + 1] for command in commands], ["100", "101", "102"])
        self.assertEqual([command[command.index("--width") + 1] for command in commands], ["640", "640", "640"])
        self.assertEqual([command[command.index("--height") + 1] for command in commands], ["360", "360", "360"])
        self.assertEqual([command[command.index("--length") + 1] for command in commands], ["81", "81", "81"])
        self.assertEqual([command[command.index("--fps") + 1] for command in commands], ["16", "16", "16"])
        self.assertEqual(commands[0][commands[0].index("--high-steps") + 1], "10")
        self.assertEqual(commands[0][commands[0].index("--low-steps") + 1], "10")
        self.assertTrue(all("--input" in command for command in commands))
        self.assertTrue(commands[0][commands[0].index("--input") + 1].endswith("image-1.png"))
        first_metadata = result["artifacts"][0]["metadata"]
        self.assertEqual(first_metadata["seed"], 100)
        self.assertEqual(first_metadata["resolution"], "360p")
        self.assertEqual(first_metadata["width"], 640)
        self.assertEqual(first_metadata["height"], 360)
        self.assertEqual(first_metadata["requestedWidth"], 640)
        self.assertEqual(first_metadata["requestedHeight"], 360)
        self.assertEqual(first_metadata["cliWidth"], 640)
        self.assertEqual(first_metadata["cliHeight"], 360)
        self.assertEqual(first_metadata["length"], 81)
        self.assertEqual(first_metadata["fps"], 16)
        self.assertEqual(first_metadata["seedSeeker"]["skillId"], "wan-seed-seeker")
        self.assertEqual(first_metadata["seedSeeker"]["previewCount"], 3)

    def test_preview_i2v_resolves_wan_lora_and_stores_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            lora_path = root / "models" / "loras" / "wan22" / "blue-motion.safetensors"
            lora_path.parent.mkdir(parents=True)
            lora_path.write_bytes(b"")
            commands: list[list[str]] = []
            payload = self.payload(
                root,
                params={
                    "runMode": "preview",
                    "modelProfile": "wan22-i2v",
                    "videoMode": "i2v",
                    "aspectRatio": "16:9",
                    "duration": "5",
                    "seed": "100",
                    "extraLora": {"name": "blue motion", "strength": 0.6},
                },
            )
            patches = self.run_with_patches(root, commands)
            with patches[0], patches[1], patches[2]:
                result = wan_seed_seeker_action.run_preview(payload, emit_partials=False)

        self.assertTrue(all("--extra-lora" in command for command in commands))
        self.assertEqual(commands[0][commands[0].index("--extra-lora") + 1], f"{lora_path}:0.6")
        metadata = result["artifacts"][0]["metadata"]
        self.assertEqual(metadata["extraLoras"], [f"{lora_path}:0.6"])
        self.assertEqual(metadata["seedSeeker"]["extraLoras"], [f"{lora_path}:0.6"])
        self.assertIn("lora", metadata["tags"])

    def test_preview_flf2v_uses_first_and_last_image_directly_with_dasiwa_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            commands: list[list[str]] = []
            payload = self.payload(
                root,
                image_count=2,
                params={
                    "runMode": "preview",
                    "modelProfile": "wan22-dasiwa-tastysin-i2v",
                    "videoMode": "flf2v",
                    "aspectRatio": "9:16",
                    "duration": "3",
                    "seed": "7",
                },
            )
            patches = self.run_with_patches(root, commands)
            with patches[0], patches[1], patches[2]:
                result = wan_seed_seeker_action.run_preview(payload, emit_partials=False)

        self.assertEqual(len(result["artifacts"]), 3)
        self.assertEqual([command[1] for command in commands], ["wan22-flf2v", "wan22-flf2v", "wan22-flf2v"])
        self.assertEqual(commands[0][commands[0].index("--width") + 1], "360")
        self.assertEqual(commands[0][commands[0].index("--height") + 1], "640")
        self.assertEqual(commands[0][commands[0].index("--length") + 1], "49")
        self.assertEqual(commands[0][commands[0].index("--high-steps") + 1], "2")
        self.assertEqual(commands[0][commands[0].index("--low-steps") + 1], "2")
        self.assertTrue(commands[0][commands[0].index("--first") + 1].endswith("image-1.png"))
        self.assertTrue(commands[0][commands[0].index("--last") + 1].endswith("image-2.png"))
        self.assertEqual(result["artifacts"][0]["metadata"]["videoMode"], "flf2v")
        self.assertEqual(result["artifacts"][0]["metadata"]["cliMode"], "wan22-flf2v")

    def test_preview_flf2v_duplicates_single_image(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            commands: list[list[str]] = []
            payload = self.payload(
                root,
                image_count=1,
                params={
                    "runMode": "preview",
                    "modelProfile": "wan22-dasiwa-boundbite-i2v",
                    "videoMode": "flf2v",
                    "aspectRatio": "4:3",
                    "duration": "3",
                    "seed": "11",
                },
            )
            patches = self.run_with_patches(root, commands)
            with patches[0], patches[1], patches[2]:
                wan_seed_seeker_action.run_preview(payload, emit_partials=False)

        first = commands[0][commands[0].index("--first") + 1]
        last = commands[0][commands[0].index("--last") + 1]
        self.assertEqual(first, last)

    def test_preview_flf2v_explicit_first_last_paths_take_priority(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            explicit_first = root / "explicit" / "first.png"
            explicit_last = root / "explicit" / "last.png"
            explicit_first.parent.mkdir(parents=True, exist_ok=True)
            explicit_first.write_bytes(b"first")
            explicit_last.write_bytes(b"last")
            commands: list[list[str]] = []
            payload = self.payload(
                root,
                image_count=1,
                params={
                    "runMode": "preview",
                    "modelProfile": "wan22-dasiwa-boundbite-i2v",
                    "videoMode": "flf2v",
                    "aspectRatio": "4:3",
                    "duration": "3",
                    "seed": "11",
                    "firstPath": str(explicit_first),
                    "lastPath": str(explicit_last),
                },
            )
            patches = self.run_with_patches(root, commands)
            with patches[0], patches[1], patches[2]:
                wan_seed_seeker_action.run_preview(payload, emit_partials=False)

        first = commands[0][commands[0].index("--first") + 1]
        last = commands[0][commands[0].index("--last") + 1]
        self.assertTrue(first.endswith("explicit/first.png"))
        self.assertTrue(last.endswith("explicit/last.png"))
        self.assertNotIn("image-1.png", first)
        self.assertNotIn("image-1.png", last)

    def test_rerender_uses_selected_preview_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_1 = root / "inputs" / "first.png"
            source_2 = root / "inputs" / "last.png"
            source_1.parent.mkdir(parents=True)
            source_1.write_bytes(b"first")
            source_2.write_bytes(b"last")
            lora = root / "models" / "loras" / "wan22" / "seed-style.safetensors"
            lora.parent.mkdir(parents=True)
            lora.write_bytes(b"")
            commands: list[list[str]] = []
            payload = {
                "skillId": "wan-seed-seeker",
                "runId": "skill_run_final",
                "prompt": "ignored new prompt",
                "params": {"runMode": "rerender", "targetResolution": "1080p"},
                "selectedCardSnapshots": [
                    {
                        "name": "Seed preview",
                        "mediaAssets": [],
                        "metadata": {
                            "seedSeeker": {"skillId": "wan-seed-seeker", "mode": "preview"},
                            "seed": 4242,
                            "basePrompt": "stored prompt",
                            "modelProfile": "wan22-dasiwa-boundbite-i2v",
                            "videoMode": "flf2v",
                            "aspectRatio": "4:3",
                            "duration": 7,
                            "highNoiseSteps": 2,
                            "lowNoiseSteps": 2,
                            "extraLoras": [f"{lora}:0.5"],
                            "sourceImageArtifactUrls": [
                                "/api/artifacts/inputs/first.png",
                                "/api/artifacts/inputs/last.png",
                            ],
                        },
                    }
                ],
            }
            patches = self.run_with_patches(root, commands)
            with patches[0], patches[1], patches[2]:
                result = wan_seed_seeker_action.run_rerender(payload)

        command = commands[0]
        self.assertEqual(len(result["artifacts"]), 1)
        self.assertEqual(command[1], "wan22-flf2v")
        self.assertEqual(command[command.index("--seed") + 1], "4242")
        self.assertEqual(command[command.index("--prompt") + 1], "stored prompt")
        self.assertEqual(command[command.index("--width") + 1], "1440")
        self.assertEqual(command[command.index("--height") + 1], "1080")
        self.assertEqual(command[command.index("--length") + 1], "113")
        self.assertEqual(command[command.index("--extra-lora") + 1], f"{lora}:0.5")
        self.assertTrue(command[command.index("--first") + 1].endswith("first.png"))
        self.assertTrue(command[command.index("--last") + 1].endswith("last.png"))
        self.assertEqual(result["artifacts"][0]["metadata"]["resolution"], "1080p")
        self.assertEqual(result["artifacts"][0]["metadata"]["width"], 1440)
        self.assertEqual(result["artifacts"][0]["metadata"]["height"], 1080)
        self.assertEqual(result["artifacts"][0]["metadata"]["extraLoras"], [f"{lora}:0.5"])
        self.assertIn("Seed: 4242", result["artifacts"][0]["prompt"])

    def test_rerender_requires_selected_wan_preview(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "requires selecting one WAN Seed Seeker preview card"):
            wan_seed_seeker_action.run_rerender(
                {
                    "skillId": "wan-seed-seeker",
                    "runId": "skill_run_final",
                    "prompt": "prompt",
                    "params": {"runMode": "rerender", "targetResolution": "720p"},
                    "selectedCardSnapshots": [
                        {"metadata": {"seedSeeker": {"skillId": "ltx-seed-seeker", "mode": "preview"}, "seed": 1}}
                    ],
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
                    "modelProfile": "wan22-i2v",
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
                patch("wan_seed_seeker_action.comfy_action.artifacts_root", return_value=root),
                patch("wan_seed_seeker_action.comfy_action.models_dir", return_value=root / "models"),
                patch("wan_seed_seeker_action.comfy_action.run_command", side_effect=run),
            ):
                result = wan_seed_seeker_action.run_preview(payload, emit_partials=False)

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
                    "modelProfile": "wan22-i2v",
                    "videoMode": "i2v",
                    "aspectRatio": "16:9",
                    "duration": "5",
                    "seed": "1",
                },
            )
            with (
                patch("wan_seed_seeker_action.comfy_action.artifacts_root", return_value=root),
                patch("wan_seed_seeker_action.comfy_action.models_dir", return_value=root / "models"),
                patch("wan_seed_seeker_action.comfy_action.run_command", side_effect=RuntimeError("all failed")),
            ):
                with self.assertRaisesRegex(RuntimeError, "failed for all seeds"):
                    wan_seed_seeker_action.run_preview(payload, emit_partials=False)


if __name__ == "__main__":
    unittest.main()
