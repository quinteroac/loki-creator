from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import comfy_action


class ComfyActionTest(unittest.TestCase):
    def test_anima_generation_preserves_natural_language_prompt(self) -> None:
        original_prompt = "Una chica samurai en un bosque lluvioso con luz cinematica"

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

    def test_anima_generation_resolves_extra_lora_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir)):
            lora_path = Path(tmpdir) / "loras" / "anima" / "blue-dawn-style.safetensors"
            lora_path.parent.mkdir(parents=True)
            lora_path.write_bytes(b"")

            command, _cwd = comfy_action.build_imagegen_command(
                mode="generate",
                params={
                    "modelProfile": "anima-base",
                    "aspectRatio": "1:1",
                    "lora": {"name": "blue dawn style", "strength": 0.8, "clipStrength": 0.0},
                },
                prompt="masterpiece, best quality, score_7, safe, 1girl, anime style",
                out_dir=Path(tmpdir) / "outputs",
                media={"image": [], "audio": [], "video": []},
                require_model_profile=True,
                require_aspect_ratio=True,
                require_input_image=False,
                skill_label="comfy-image-generate",
            )

        lora = command[command.index("--extra-lora") + 1]
        self.assertEqual(lora, f"{lora_path}:0.8:0.0")

    def test_anima_generation_preserves_explicit_extra_lora_path(self) -> None:
        lora = "/models/loras/anima/custom.safetensors:0.7:0.0"

        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir)):
            command, _cwd = comfy_action.build_imagegen_command(
                mode="generate",
                params={"modelProfile": "anima-base", "aspectRatio": "1:1", "extraLora": lora},
                prompt="masterpiece, best quality, score_7, safe, 1girl, anime style",
                out_dir=Path(tmpdir) / "outputs",
                media={"image": [], "audio": [], "video": []},
                require_model_profile=True,
                require_aspect_ratio=True,
                require_input_image=False,
                skill_label="comfy-image-generate",
            )

        self.assertEqual(command[command.index("--extra-lora") + 1], lora)

    def test_anima_generation_resolves_relative_loras_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir)):
            lora_path = Path(tmpdir) / "loras" / "anima" / "ink-line.safetensors"
            lora_path.parent.mkdir(parents=True)
            lora_path.write_bytes(b"")

            command, _cwd = comfy_action.build_imagegen_command(
                mode="generate",
                params={"modelProfile": "anima-base", "aspectRatio": "1:1", "extraLora": "loras/anima/ink-line.safetensors:0.6"},
                prompt="masterpiece, best quality, score_7, safe, 1girl, anime style",
                out_dir=Path(tmpdir) / "outputs",
                media={"image": [], "audio": [], "video": []},
                require_model_profile=True,
                require_aspect_ratio=True,
                require_input_image=False,
                skill_label="comfy-image-generate",
            )

        self.assertEqual(command[command.index("--extra-lora") + 1], f"{lora_path}:0.6")


if __name__ == "__main__":
    unittest.main()
