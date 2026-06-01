from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import comfy_action


class ComfyActionTest(unittest.TestCase):
    def test_anima_generation_adapts_natural_language_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir)):
            command, _cwd = comfy_action.build_imagegen_command(
                mode="generate",
                params={"modelProfile": "anima-base", "aspectRatio": "1:1"},
                prompt="Una chica samurai en un bosque lluvioso con luz cinematica",
                out_dir=Path(tmpdir) / "outputs",
                media={"image": [], "audio": [], "video": []},
                require_model_profile=True,
                require_aspect_ratio=True,
                require_input_image=False,
                skill_label="comfy-image-generate",
            )

        prompt = command[command.index("--prompt") + 1]
        self.assertIn("masterpiece", prompt)
        self.assertIn("1girl", prompt)
        self.assertIn("samurai", prompt)
        self.assertIn("forest", prompt)
        self.assertIn("rain", prompt)
        self.assertIn("cinematic lighting", prompt)

    def test_anima_generation_preserves_existing_tag_prompt(self) -> None:
        original_prompt = "masterpiece, best quality, score_7, safe, 1girl, anime style"

        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir)):
            command, _cwd = comfy_action.build_imagegen_command(
                mode="generate",
                params={"modelProfile": "anima-base", "aspectRatio": "1:1"},
                prompt=original_prompt,
                out_dir=Path(tmpdir) / "outputs",
                media={"image": [], "audio": [], "video": []},
                require_model_profile=True,
                require_aspect_ratio=True,
                require_input_image=False,
                skill_label="comfy-image-generate",
            )

        self.assertEqual(command[command.index("--prompt") + 1], original_prompt)


if __name__ == "__main__":
    unittest.main()
