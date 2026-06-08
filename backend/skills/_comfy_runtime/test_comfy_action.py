from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import comfy_action


class ComfyActionTest(unittest.TestCase):
    def test_ideogram4_builds_structured_generate_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir)):
            command, cwd = comfy_action.build_cli_command(
                {
                    "skillId": "ideogram4-image",
                    "prompt": "Premium cinematic poster for a translucent amber cassette player",
                    "params": {
                        "mode": "t2i",
                        "qualityProfile": "Quality",
                        "aspectRatio": "21:9",
                        "styleAesthetics": "premium cinematic advertising, high detail",
                        "styleLighting": "soft studio key light with warm rim light",
                        "styleMedium": "photograph",
                        "stylePhoto": "commercial product photography",
                        "styleColors": ["#0B0F14", "#F4D06F"],
                        "background": "dark glossy studio surface",
                        "objects": [
                            {
                                "bbox": [180, 300, 850, 760],
                                "description": "translucent amber cassette player, centered hero object",
                            }
                        ],
                        "texts": [
                            {
                                "bbox": [70, 180, 180, 820],
                                "text": "RETRO WAVE",
                                "description": "large readable condensed headline above product",
                            }
                        ],
                        "seed": 123,
                    },
                },
                Path(tmpdir) / "outputs",
                media={"image": [], "audio": [], "video": []},
            )
            config = (cwd / ".comfy-agent-tools.json").read_text(encoding="utf-8")

        self.assertEqual(command[:2], ["comfy-imagegen", "ideogram4-generate"])
        self.assertEqual(command[command.index("--width") + 1], "1344")
        self.assertEqual(command[command.index("--height") + 1], "576")
        self.assertEqual(command[command.index("--steps") + 1], "48")
        self.assertEqual(command[command.index("--mu") + 1], "0.0")
        self.assertEqual(command[command.index("--std") + 1], "1.5")
        self.assertEqual(command[command.index("--style-photo") + 1], "commercial product photography")
        self.assertEqual(command[command.index("--output-json") + 1], str(Path(tmpdir) / "outputs" / "ideogram-prompt.json"))
        self.assertIn("--style-color", command)
        self.assertEqual(command[command.index("--object") + 1], "180,300,850,760|translucent amber cassette player, centered hero object")
        self.assertEqual(command[command.index("--text") + 1], "70,180,180,820|RETRO WAVE|large readable condensed headline above product")
        self.assertEqual(command[command.index("--seed") + 1], "123")
        self.assertIn('"imagegen.ideogram4-generate": "ideogram4-fp8"', config)

    def test_ideogram4_turbo_profile_uses_turbo_params(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir)):
            command, _cwd = comfy_action.build_cli_command(
                {
                    "skillId": "ideogram4-image",
                    "prompt": "Graphic badge logo",
                    "params": {
                        "mode": "t2i",
                        "qualityProfile": "Turbo",
                        "aspectRatio": "1:1",
                        "styleAesthetics": "bold clean graphic design",
                        "styleLighting": "flat even lighting",
                        "styleMedium": "illustration",
                        "styleArtStyle": "vector poster art",
                        "background": "solid red field",
                        "objects": [{"bbox": "180,180,820,820", "description": "centered circular badge emblem"}],
                    },
                },
                Path(tmpdir) / "outputs",
                media={"image": [], "audio": [], "video": []},
            )

        self.assertEqual(command[command.index("--steps") + 1], "12")
        self.assertEqual(command[command.index("--mu") + 1], "0.5")
        self.assertEqual(command[command.index("--std") + 1], "1.75")
        self.assertEqual(command[command.index("--style-art-style") + 1], "vector poster art")

    def test_ideogram4_supports_requested_aspect_ratios(self) -> None:
        expected = {
            "1:1": ("1024", "1024"),
            "3:2": ("1248", "832"),
            "4:3": ("1152", "864"),
            "16:9": ("1360", "768"),
            "21:9": ("1344", "576"),
            "2:3": ("832", "1248"),
            "3:4": ("864", "1152"),
            "9:16": ("768", "1360"),
        }
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir)):
            for ratio, dimensions in expected.items():
                with self.subTest(ratio=ratio):
                    command, _cwd = comfy_action.build_cli_command(
                        {
                            "skillId": "ideogram4-image",
                            "prompt": "Graphic poster",
                            "params": {
                                "mode": "t2i",
                                "qualityProfile": "Default",
                                "aspectRatio": ratio,
                                "styleAesthetics": "bold clean graphic design",
                                "styleLighting": "flat even lighting",
                                "styleMedium": "illustration",
                                "styleArtStyle": "poster art",
                                "background": "plain background",
                                "objects": [{"bbox": [180, 180, 820, 820], "description": "centered poster subject"}],
                            },
                        },
                        Path(tmpdir) / ratio.replace(":", "-"),
                        media={"image": [], "audio": [], "video": []},
                    )
                    self.assertEqual(command[command.index("--width") + 1], dimensions[0])
                    self.assertEqual(command[command.index("--height") + 1], dimensions[1])

    def test_ideogram4_does_not_apply_runtime_nsfw_filter(self) -> None:
        prompt = "Adult erotic editorial portrait in a private studio"
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir)):
            command, _cwd = comfy_action.build_cli_command(
                {
                    "skillId": "ideogram4-image",
                    "prompt": prompt,
                    "params": {
                        "mode": "t2i",
                        "qualityProfile": "Default",
                        "aspectRatio": "1:1",
                        "styleAesthetics": "intimate editorial photography, high detail",
                        "styleLighting": "soft warm studio lighting",
                        "styleMedium": "photograph",
                        "stylePhoto": "editorial portrait photography",
                        "background": "minimal private studio set",
                        "objects": [{"bbox": [120, 180, 940, 820], "description": "adult portrait subject, centered editorial composition"}],
                    },
                },
                Path(tmpdir) / "outputs",
                media={"image": [], "audio": [], "video": []},
            )

        self.assertEqual(command[command.index("--prompt") + 1], prompt)

    def test_ideogram4_r2i_requires_local_image_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir)):
            with self.assertRaisesRegex(RuntimeError, "r2i requires"):
                comfy_action.build_cli_command(
                    {
                        "skillId": "ideogram4-image",
                        "prompt": "Use the selected reference style",
                        "params": {
                            "mode": "r2i",
                            "qualityProfile": "Default",
                            "aspectRatio": "3:2",
                            "styleAesthetics": "reference-informed style",
                            "styleLighting": "soft light",
                            "styleMedium": "photograph",
                            "stylePhoto": "editorial photograph",
                            "background": "studio background",
                            "objects": [{"bbox": [100, 100, 900, 900], "description": "main referenced subject"}],
                        },
                    },
                    Path(tmpdir) / "outputs",
                    media={"image": [], "audio": [], "video": []},
                )

    def test_ideogram4_rejects_invalid_bbox(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir)):
            with self.assertRaisesRegex(RuntimeError, "y_min < y_max"):
                comfy_action.build_cli_command(
                    {
                        "skillId": "ideogram4-image",
                        "prompt": "Broken bbox",
                        "params": {
                            "mode": "t2i",
                            "qualityProfile": "Default",
                            "aspectRatio": "1:1",
                            "styleAesthetics": "clean",
                            "styleLighting": "soft",
                            "styleMedium": "illustration",
                            "styleArtStyle": "poster art",
                            "background": "plain background",
                            "objects": [{"bbox": [900, 100, 100, 900], "description": "invalid object"}],
                        },
                    },
                    Path(tmpdir) / "outputs",
                    media={"image": [], "audio": [], "video": []},
                )

    def test_ideogram4_rejects_reference_language_in_model_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir)):
            with self.assertRaisesRegex(RuntimeError, "standalone visual description"):
                comfy_action.build_cli_command(
                    {
                        "skillId": "ideogram4-image",
                        "prompt": "Crear una recreacion muy fiel de la imagen de referencia interpretada",
                        "params": {
                            "mode": "r2i",
                            "qualityProfile": "Default",
                            "aspectRatio": "3:4",
                            "styleAesthetics": "faithful portrait, high detail",
                            "styleLighting": "warm direct light",
                            "styleMedium": "digital painting",
                            "styleArtStyle": "semi-realistic fashion portrait",
                            "background": "plain warm beige studio background",
                            "objects": [{"bbox": [0, 0, 965, 1000], "description": "adult female fashion portrait face filling the frame"}],
                        },
                    },
                    Path(tmpdir) / "outputs",
                    media={"image": [Path(tmpdir) / "input.png"], "audio": [], "video": []},
                )

    def test_ideogram4_rejects_reference_language_in_object_description(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir)):
            with self.assertRaisesRegex(RuntimeError, "Remove reference-language phrase"):
                comfy_action.build_cli_command(
                    {
                        "skillId": "ideogram4-image",
                        "prompt": "Ultra close cropped warm glamour portrait",
                        "params": {
                            "mode": "r2i",
                            "qualityProfile": "Default",
                            "aspectRatio": "3:4",
                            "styleAesthetics": "faithful portrait, high detail",
                            "styleLighting": "warm direct light",
                            "styleMedium": "digital painting",
                            "styleArtStyle": "semi-realistic fashion portrait",
                            "background": "plain warm beige studio background",
                            "objects": [{"bbox": [0, 0, 965, 1000], "description": "mantener la referencia with adult female fashion portrait face filling the frame"}],
                        },
                    },
                    Path(tmpdir) / "outputs",
                    media={"image": [Path(tmpdir) / "input.png"], "audio": [], "video": []},
                )

    def test_raw_result_uses_ideogram_prompt_json_file_as_card_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "image.png"
            output.write_bytes(b"png")
            prompt_json = Path(tmpdir) / "ideogram-prompt.json"
            structured_prompt = '{"high_level_description":"Structured Ideogram prompt"}'
            prompt_json.write_text(structured_prompt, encoding="utf-8")

            raw = comfy_action.raw_result_from_cli(
                {
                    "kind": "image",
                    "mode": "ideogram4-generate",
                    "artifacts": [str(output)],
                    "prompt_json": str(prompt_json),
                },
                ["comfy-imagegen", "ideogram4-generate"],
                "High level prompt",
            )

        self.assertEqual(raw["artifacts"][0]["prompt"], structured_prompt)

    def test_raw_result_reads_ideogram_prompt_json_from_command_option(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "image.png"
            output.write_bytes(b"png")
            prompt_json = Path(tmpdir) / "ideogram-prompt.json"
            structured_prompt = '{"high_level_description":"Prompt from output json option"}'
            prompt_json.write_text(structured_prompt, encoding="utf-8")

            raw = comfy_action.raw_result_from_cli(
                {
                    "kind": "image",
                    "mode": "ideogram4-generate",
                    "artifacts": [str(output)],
                },
                ["comfy-imagegen", "ideogram4-generate", "--output-json", str(prompt_json)],
                "High level prompt",
            )

        self.assertEqual(raw["artifacts"][0]["prompt"], structured_prompt)

    def test_raw_result_falls_back_to_command_prompt_without_prompt_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "image.png"
            output.write_bytes(b"png")

            raw = comfy_action.raw_result_from_cli(
                {
                    "kind": "image",
                    "mode": "generate",
                    "artifacts": [str(output)],
                },
                ["comfy-imagegen", "generate"],
                "Normal prompt",
            )

        self.assertEqual(raw["artifacts"][0]["prompt"], "Normal prompt")

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

    def test_wan_i2v_resolves_extra_lora_name_from_wan22_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir)):
            lora_path = Path(tmpdir) / "loras" / "wan22" / "blue-motion.safetensors"
            lora_path.parent.mkdir(parents=True)
            lora_path.write_bytes(b"")
            image = Path(tmpdir) / "input.png"

            command, cwd = comfy_action.build_cli_command(
                {
                    "skillId": "comfy-videogen",
                    "prompt": "slow camera drift",
                    "params": {
                        "modelProfile": "wan22-i2v",
                        "videoMode": "i2v",
                        "aspectRatio": "16:9",
                        "resolution": "480p",
                        "duration": "5",
                        "fps": "24",
                        "lora": {"name": "blue motion", "strength": 0.75},
                    },
                },
                Path(tmpdir) / "outputs",
                media={"image": [image], "audio": [], "video": []},
            )
            config = (cwd / ".comfy-agent-tools.json").read_text(encoding="utf-8")

        self.assertEqual(command[:2], ["comfy-videogen", "wan22-i2v"])
        self.assertEqual(command[command.index("--fps") + 1], "24")
        self.assertEqual(command[command.index("--length") + 1], "121")
        self.assertEqual(command[command.index("--extra-lora") + 1], f"{lora_path}:0.75")
        self.assertIn('"videogen.wan22-i2v": "wan22-i2v"', config)

    def test_wan_i2v_defaults_to_16_fps(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir)):
            command, _cwd = comfy_action.build_cli_command(
                {
                    "skillId": "comfy-videogen",
                    "prompt": "slow camera drift",
                    "params": {
                        "modelProfile": "wan22-i2v",
                        "videoMode": "i2v",
                        "aspectRatio": "16:9",
                        "resolution": "480p",
                        "duration": "5",
                    },
                },
                Path(tmpdir) / "outputs",
                media={"image": [Path(tmpdir) / "input.png"], "audio": [], "video": []},
            )

        self.assertEqual(command[command.index("--fps") + 1], "16")
        self.assertEqual(command[command.index("--length") + 1], "81")

    def test_wan_flf2v_preserves_explicit_high_and_low_loras(self) -> None:
        high_lora = "/models/loras/wan22/high.safetensors:0.9"
        low_lora = "/models/loras/wan22/low.safetensors:0.4"

        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir)):
            first = Path(tmpdir) / "first.png"
            last = Path(tmpdir) / "last.png"
            command, _cwd = comfy_action.build_cli_command(
                {
                    "skillId": "comfy-videogen",
                    "prompt": "smooth transition",
                    "params": {
                        "modelProfile": "wan22-dasiwa-tastysin-i2v",
                        "videoMode": "flf2v",
                        "aspectRatio": "9:16",
                        "resolution": "480p",
                        "duration": "3",
                        "fps": "24",
                        "extraLoraHigh": high_lora,
                        "extraLoraLow": low_lora,
                    },
                },
                Path(tmpdir) / "outputs",
                media={"image": [first, last], "audio": [], "video": []},
            )

        self.assertEqual(command[:2], ["comfy-videogen", "wan22-flf2v"])
        self.assertEqual(command[command.index("--fps") + 1], "24")
        self.assertEqual(command[command.index("--length") + 1], "73")
        self.assertEqual(command[command.index("--extra-lora-high") + 1], high_lora)
        self.assertEqual(command[command.index("--extra-lora-low") + 1], low_lora)

    def test_s2vidgen_uses_wan_lora_flag_and_strength(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            patch("comfy_action.models_dir", return_value=Path(tmpdir)),
            patch("comfy_action.audio_duration_seconds", return_value=3.0),
        ):
            lora_path = Path(tmpdir) / "loras" / "wan22" / "singer-style.safetensors"
            lora_path.parent.mkdir(parents=True)
            lora_path.write_bytes(b"")
            command, _cwd = comfy_action.build_cli_command(
                {
                    "skillId": "comfy-s2vidgen",
                    "prompt": "In the video, a singer performs.",
                    "params": {
                        "modelProfile": "wan22-s2v",
                        "aspectRatio": "16:9",
                        "resolution": "480p",
                        "extraLora": "singer style:0.55",
                    },
                },
                Path(tmpdir) / "outputs",
                media={"image": [Path(tmpdir) / "input.png"], "audio": [Path(tmpdir) / "song.wav"], "video": []},
            )

        self.assertNotIn("--extra-lora", command)
        self.assertEqual(command[command.index("--lora") + 1], str(lora_path))
        self.assertEqual(command[command.index("--lora-strength") + 1], "0.55")

    def test_s2vidgen_builds_audio_length_command(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            patch("comfy_action.models_dir", return_value=Path(tmpdir)),
            patch("comfy_action.audio_duration_seconds", return_value=14.0),
        ):
            out_dir = Path(tmpdir) / "outputs"
            image = Path(tmpdir) / "input.png"
            audio = Path(tmpdir) / "song.wav"
            command, cwd = comfy_action.build_cli_command(
                {
                    "skillId": "comfy-s2vidgen",
                    "prompt": "In the video, a singer performs with emotional expression and subtle camera motion.",
                    "params": {
                        "modelProfile": "wan22-s2v",
                        "aspectRatio": "16:9",
                        "resolution": "480p",
                        "duration": "5",
                        "fps": "24",
                        "highNoiseSteps": "10",
                        "lowNoiseSteps": "10",
                    },
                },
                out_dir,
                media={"image": [image], "audio": [audio], "video": []},
            )
            config = (cwd / ".comfy-agent-tools.json").read_text(encoding="utf-8")

        self.assertEqual(command[:2], ["comfy-videogen", "wan22-s2v"])
        self.assertEqual(command[command.index("--input") + 1], str(image))
        self.assertEqual(command[command.index("--audio") + 1], str(audio))
        self.assertEqual(command[command.index("--width") + 1], "848")
        self.assertEqual(command[command.index("--height") + 1], "480")
        self.assertEqual(command[command.index("--length") + 1], "336")
        self.assertEqual(command[command.index("--fps") + 1], "24")
        self.assertEqual(command[command.index("--audio-duration") + 1], "14")
        self.assertEqual(command[command.index("--prompt") + 1], "In the video, a singer performs with emotional expression and subtle camera motion.")
        self.assertNotIn("--duration", command)
        self.assertNotIn("--high-steps", command)
        self.assertNotIn("--low-steps", command)
        self.assertIn('"videogen.wan22-s2v": "wan22-s2v"', config)

    def test_wan_rejects_unsupported_fps(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir)):
            for fps in ("30", "fast"):
                with self.subTest(fps=fps), self.assertRaisesRegex(RuntimeError, "WAN FPS must be 16 or 24"):
                    comfy_action.build_cli_command(
                        {
                            "skillId": "comfy-videogen",
                            "prompt": "slow camera drift",
                            "params": {
                                "modelProfile": "wan22-i2v",
                                "videoMode": "i2v",
                                "aspectRatio": "16:9",
                                "resolution": "480p",
                                "duration": "5",
                                "fps": fps,
                            },
                        },
                        Path(tmpdir) / "outputs",
                        media={"image": [Path(tmpdir) / "input.png"], "audio": [], "video": []},
                    )

    def test_s2vidgen_dasiwa_littledemon_uses_720p_vertical_dimensions(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            patch("comfy_action.models_dir", return_value=Path(tmpdir)),
            patch("comfy_action.audio_duration_seconds", return_value=14.1),
        ):
            out_dir = Path(tmpdir) / "outputs"
            image = Path(tmpdir) / "input.png"
            audio = Path(tmpdir) / "song.wav"
            command, cwd = comfy_action.build_cli_command(
                {
                    "skillId": "comfy-s2vidgen",
                    "prompt": "In the video, a performer sings with expressive face and hand movement.",
                    "params": {
                        "modelProfile": "wan22-dasiwa-littledemon-v2-s2v",
                        "aspectRatio": "9:16",
                        "resolution": "720p",
                        "width": 480,
                        "height": 848,
                    },
                },
                out_dir,
                media={"image": [image], "audio": [audio], "video": []},
            )
            config = (cwd / ".comfy-agent-tools.json").read_text(encoding="utf-8")

        self.assertEqual(command[:2], ["comfy-videogen", "wan22-s2v"])
        self.assertEqual(command[command.index("--input") + 1], str(image))
        self.assertEqual(command[command.index("--audio") + 1], str(audio))
        self.assertEqual(command[command.index("--width") + 1], "720")
        self.assertEqual(command[command.index("--height") + 1], "1280")
        self.assertEqual(command[command.index("--length") + 1], "226")
        self.assertEqual(command[command.index("--fps") + 1], "16")
        self.assertEqual(command[command.index("--audio-duration") + 1], "14.1")
        self.assertIn('"videogen.wan22-s2v": "wan22-dasiwa-littledemon-v2-s2v"', config)

    def test_s2vidgen_rejects_non_s2v_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir)):
            with self.assertRaisesRegex(RuntimeError, "requires an S2V modelProfile"):
                comfy_action.build_cli_command(
                    {
                        "skillId": "comfy-s2vidgen",
                        "prompt": "In the video, a singer performs.",
                        "params": {
                            "modelProfile": "wan22-i2v",
                            "aspectRatio": "16:9",
                            "resolution": "480p",
                        },
                    },
                    Path(tmpdir) / "outputs",
                    media={"image": [Path(tmpdir) / "input.png"], "audio": [Path(tmpdir) / "song.wav"], "video": []},
                )

    def test_s2vidgen_requires_image_and_audio(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir)):
            payload = {
                "skillId": "comfy-s2vidgen",
                "prompt": "In the video, a singer performs.",
                "params": {"modelProfile": "wan22-s2v", "aspectRatio": "16:9", "resolution": "480p"},
            }
            with self.assertRaisesRegex(RuntimeError, "requires one input image"):
                comfy_action.build_cli_command(
                    payload,
                    Path(tmpdir) / "outputs",
                    media={"image": [], "audio": [Path(tmpdir) / "song.wav"], "video": []},
                )
            with self.assertRaisesRegex(RuntimeError, "requires one input audio"):
                comfy_action.build_cli_command(
                    payload,
                    Path(tmpdir) / "outputs",
                    media={"image": [Path(tmpdir) / "input.png"], "audio": [], "video": []},
                )

    def test_videogen_rejects_moved_wan_s2v_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir)):
            with self.assertRaisesRegex(RuntimeError, "moved to comfy-s2vidgen"):
                comfy_action.build_cli_command(
                    {
                        "skillId": "comfy-videogen",
                        "prompt": "In the video, a singer performs.",
                        "params": {
                            "modelProfile": "wan22-s2v",
                            "videoMode": "wan22-s2v",
                            "aspectRatio": "16:9",
                            "resolution": "480p",
                            "duration": "5",
                        },
                    },
                    Path(tmpdir) / "outputs",
                    media={"image": [Path(tmpdir) / "input.png"], "audio": [Path(tmpdir) / "song.wav"], "video": []},
                )

    def test_video_dimensions_supports_seed_seeker_resolutions(self) -> None:
        self.assertEqual(
            comfy_action.video_dimensions({"aspectRatio": "16:9", "resolution": "360p"}),
            (640, 360),
        )
        self.assertEqual(
            comfy_action.video_dimensions({"aspectRatio": "9:16", "resolution": "360p"}),
            (360, 640),
        )
        self.assertEqual(
            comfy_action.video_dimensions({"aspectRatio": "4:3", "resolution": "1080p"}),
            (1440, 1080),
        )
        self.assertEqual(
            comfy_action.video_dimensions({"aspectRatio": "9:16", "resolution": "1080p"}),
            (1080, 1920),
        )

    def test_materialize_selected_media_resolves_metadata_artifact_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.artifacts_root", return_value=Path(tmpdir)):
            root = Path(tmpdir)
            audio = root / "skills" / "ffmpeg-audio-split" / "skill_run_audio" / "outputs" / "clip.m4a"
            audio.parent.mkdir(parents=True)
            audio.write_bytes(b"audio")

            media = comfy_action.materialize_selected_media(
                {
                    "selectedCardSnapshots": [
                        {
                            "name": "Audio clip",
                            "mediaAssets": [],
                            "metadata": {
                                "kind": "audio",
                                "artifactUrl": "/api/artifacts/skills/ffmpeg-audio-split/skill_run_audio/outputs/clip.m4a",
                            },
                        }
                    ]
                },
                root / "inputs",
            )

        self.assertEqual(media["audio"], [audio])

    def test_materialize_selected_media_prefers_asset_src_over_data_url_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.artifacts_root", return_value=Path(tmpdir)):
            root = Path(tmpdir)
            image = root / "skills" / "comfy-image-generate" / "skill_run_image" / "outputs" / "image.png"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"image")

            media = comfy_action.materialize_selected_media(
                {
                    "selectedCardSnapshots": [
                        {
                            "name": "Image",
                            "mediaAssets": [
                                {
                                    "kind": "image",
                                    "src": "/api/artifacts/skills/comfy-image-generate/skill_run_image/outputs/image.png",
                                    "dataUrl": "data:image/png;base64,aW1hZ2UtY29weQ==",
                                }
                            ],
                            "metadata": {},
                        }
                    ]
                },
                root / "inputs",
            )

        self.assertEqual(media["image"], [image])


if __name__ == "__main__":
    unittest.main()
