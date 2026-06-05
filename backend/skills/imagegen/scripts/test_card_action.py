from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

import card_action


def printed_json(stdout: object) -> dict:
    printed = "".join(call.args[0] for call in stdout.write.call_args_list if call.args)
    return json.loads(printed)


class ImagegenCardActionTest(unittest.TestCase):
    def test_output_schema_requires_all_declared_diagnostic_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_path = card_action.write_output_schema(Path(tmpdir))
            schema = json.loads(schema_path.read_text(encoding="utf-8"))

        self.assertEqual(schema["required"], ["images", "diagnostics"])
        diagnostic_items = schema["properties"]["diagnostics"]["items"]
        self.assertEqual(diagnostic_items["required"], ["level", "title", "message"])
        self.assertEqual(
            set(diagnostic_items["required"]),
            set(diagnostic_items["properties"].keys()),
        )

    def test_run_codex_sends_prompt_through_stdin(self) -> None:
        calls: list[dict] = []

        def fake_run(command: list[str], **kwargs: object) -> object:
            calls.append({"command": command, **kwargs})
            response_path = Path(command[command.index("--output-last-message") + 1])
            response_path.write_text(
                json.dumps(
                    {
                        "title": "Generated image",
                        "prompt": "make a test image",
                        "imagePath": str(response_path.parent / "outputs" / "image.png"),
                        "mimeType": "image/png",
                        "width": 1024,
                        "height": 1024,
                    }
                ),
                encoding="utf-8",
            )
            return type("CompletedProcess", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        with tempfile.TemporaryDirectory() as tmpdir, patch("card_action.resolve_codex_bin", return_value="codex"), patch(
            "card_action.subprocess.run",
            side_effect=fake_run,
        ):
            run_dir = Path(tmpdir)
            (run_dir / "outputs").mkdir()
            result = card_action.run_codex(
                {"prompt": "make a test image", "params": {"resolution": "1024x1024"}},
                run_dir,
                [],
            )

        self.assertEqual(result["title"], "Generated image")
        self.assertEqual(calls[0]["command"][-1], "-")
        self.assertIn("make a test image", calls[0]["input"])
        self.assertIn('"images"', calls[0]["input"])
        self.assertIn("accept the generated image and report its real dimensions", calls[0]["input"])

    def test_build_codex_prompt_defaults_ambiguous_multi_image_request_to_four(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            prompt = card_action.build_codex_prompt(
                {"prompt": "create storyboard options for the scene", "params": {"resolution": "1024x1024"}},
                Path(tmpdir),
                Path(tmpdir) / "outputs",
                [],
            )

        self.assertIn("Create exactly 4 separate final image files", prompt)

    def test_main_accepts_legacy_generated_image_with_different_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("card_action.artifacts_root", return_value=Path(tmpdir)):
            output_path = Path(tmpdir) / "skills" / "imagegen" / "skill-run" / "outputs" / "image.png"

            def fake_run_codex(payload: dict, run_dir: Path, selected_images: list[Path]) -> dict:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                Image.new("RGB", (1672, 941), "blue").save(output_path)
                return {
                    "title": "Generated image",
                    "prompt": "mall scene",
                    "imagePath": str(output_path),
                    "mimeType": "image/png",
                    "width": 1672,
                    "height": 941,
                }

            payload = {
                "runId": "skill-run",
                "prompt": "mall scene",
                "params": {"resolution": "2048x1152"},
            }

            with patch("card_action.run_codex", side_effect=fake_run_codex), patch(
                "card_action.read_payload",
                return_value=payload,
            ), patch("sys.stdout") as stdout:
                card_action.main()

        result = printed_json(stdout)
        metadata = result["artifacts"][0]["metadata"]
        self.assertEqual(metadata["requestedResolution"], "2048x1152")
        self.assertEqual(metadata["width"], 1672)
        self.assertEqual(metadata["height"], 941)
        self.assertEqual(metadata["imageIndex"], 1)
        self.assertEqual(metadata["imageCount"], 1)

    def test_main_produces_multiple_image_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("card_action.artifacts_root", return_value=Path(tmpdir)):
            run_root = Path(tmpdir) / "skills" / "imagegen" / "skill-run" / "outputs"
            first_path = run_root / "storyboard-01.png"
            second_path = run_root / "storyboard-02.png"

            def fake_run_codex(payload: dict, run_dir: Path, selected_images: list[Path]) -> dict:
                run_root.mkdir(parents=True, exist_ok=True)
                Image.new("RGB", (1024, 1024), "blue").save(first_path)
                Image.new("RGB", (1024, 1024), "red").save(second_path)
                return {
                    "images": [
                        {
                            "title": "Storyboard frame 1",
                            "prompt": "wide establishing shot",
                            "imagePath": str(first_path),
                            "mimeType": "image/png",
                            "width": 1024,
                            "height": 1024,
                        },
                        {
                            "title": "Storyboard frame 2",
                            "prompt": "close-up reaction shot",
                            "imagePath": str(second_path),
                            "mimeType": "image/png",
                            "width": 1024,
                            "height": 1024,
                        },
                    ]
                }

            payload = {
                "runId": "skill-run",
                "prompt": "create a two frame storyboard",
                "params": {"resolution": "1024x1024", "imageCount": 2},
            }

            with patch("card_action.run_codex", side_effect=fake_run_codex), patch(
                "card_action.read_payload",
                return_value=payload,
            ), patch("sys.stdout") as stdout:
                card_action.main()

        result = printed_json(stdout)
        artifacts = result["artifacts"]
        self.assertEqual(len(artifacts), 2)
        self.assertEqual(artifacts[0]["title"], "Storyboard frame 1")
        self.assertEqual(artifacts[1]["title"], "Storyboard frame 2")
        self.assertEqual(artifacts[0]["metadata"]["imageIndex"], 1)
        self.assertEqual(artifacts[1]["metadata"]["imageIndex"], 2)
        self.assertEqual(artifacts[0]["metadata"]["imageCount"], 2)
        self.assertEqual(artifacts[1]["metadata"]["imageCount"], 2)
        self.assertEqual(artifacts[0]["metadata"]["requestedResolution"], "1024x1024")

    def test_main_keeps_valid_artifacts_when_one_image_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("card_action.artifacts_root", return_value=Path(tmpdir)):
            run_root = Path(tmpdir) / "skills" / "imagegen" / "skill-run" / "outputs"
            valid_path = run_root / "valid.png"
            missing_path = run_root / "missing.png"

            def fake_run_codex(payload: dict, run_dir: Path, selected_images: list[Path]) -> dict:
                run_root.mkdir(parents=True, exist_ok=True)
                Image.new("RGB", (1536, 1024), "green").save(valid_path)
                return {
                    "images": [
                        {
                            "title": "Valid option",
                            "prompt": "valid image prompt",
                            "imagePath": str(valid_path),
                            "mimeType": "image/png",
                            "width": 1536,
                            "height": 1024,
                        },
                        {
                            "title": "Missing option",
                            "prompt": "missing image prompt",
                            "imagePath": str(missing_path),
                            "mimeType": "image/png",
                            "width": 1536,
                            "height": 1024,
                        },
                    ]
                }

            payload = {
                "runId": "skill-run",
                "prompt": "create two options",
                "params": {"resolution": "1536x1024", "imageCount": 2},
            }

            with patch("card_action.run_codex", side_effect=fake_run_codex), patch(
                "card_action.read_payload",
                return_value=payload,
            ), patch("sys.stdout") as stdout:
                card_action.main()

        result = printed_json(stdout)
        self.assertEqual(len(result["artifacts"]), 1)
        self.assertEqual(result["artifacts"][0]["title"], "Valid option")
        self.assertEqual(result["artifacts"][0]["metadata"]["imageCount"], 2)
        self.assertEqual(len(result["diagnostics"]), 1)
        self.assertEqual(result["diagnostics"][0]["level"], "warning")
        self.assertIn("does not exist", result["diagnostics"][0]["message"])


if __name__ == "__main__":
    unittest.main()
