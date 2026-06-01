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


class ImagegenCardActionTest(unittest.TestCase):
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
        self.assertIn("accept the generated image and report its real dimensions", calls[0]["input"])

    def test_main_accepts_generated_image_with_different_dimensions(self) -> None:
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

        printed = "".join(call.args[0] for call in stdout.write.call_args_list if call.args)
        result = json.loads(printed)
        metadata = result["artifacts"][0]["metadata"]
        self.assertEqual(metadata["requestedResolution"], "2048x1152")
        self.assertEqual(metadata["width"], 1672)
        self.assertEqual(metadata["height"], 941)


if __name__ == "__main__":
    unittest.main()
