from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import comfy_action


class ComfyActionTest(unittest.TestCase):
    def test_sage_attention_patch_targets_wan_video_commands(self) -> None:
        with patch.dict(comfy_action.os.environ, {}, clear=True):
            self.assertTrue(comfy_action.should_enable_loki_sage_attention(["comfy-videogen", "wan22-i2v"]))
            self.assertTrue(
                comfy_action.should_enable_loki_sage_attention(
                    [sys.executable, str(Path(comfy_action.__file__).with_name("comfy_videoedit.py")), "bernini"]
                )
            )
            self.assertFalse(comfy_action.should_enable_loki_sage_attention(["comfy-videogen", "t2v"]))
            self.assertFalse(comfy_action.should_enable_loki_sage_attention(["comfy-imagegen", "generate"]))

    def test_sage_attention_patch_can_be_disabled_by_env(self) -> None:
        with patch.dict(comfy_action.os.environ, {"LOKI_COMFY_USE_SAGE_ATTENTION": "0"}, clear=True):
            self.assertFalse(comfy_action.should_enable_loki_sage_attention(["comfy-videogen", "wan22-i2v"]))

    def test_run_command_injects_sage_attention_sitecustomize_for_wan(self) -> None:
        seen: dict[str, object] = {}

        class Result:
            returncode = 0
            stdout = '{"ok": true}'
            stderr = ""

        def fake_run(*args: object, **kwargs: object) -> Result:
            seen["args"] = args
            seen["kwargs"] = kwargs
            return Result()

        with (
            tempfile.TemporaryDirectory() as tmpdir,
            patch.dict(comfy_action.os.environ, {}, clear=True),
            patch("comfy_action.subprocess.run", fake_run),
        ):
            result = comfy_action.run_command(["comfy-videogen", "wan22-i2v"], Path(tmpdir))

        env = seen["kwargs"]["env"]  # type: ignore[index]
        self.assertEqual(result, {"ok": True})
        self.assertEqual(env["LOKI_COMFY_USE_SAGE_ATTENTION"], "1")
        self.assertIn(str(Path(comfy_action.__file__).resolve().parent), env["PYTHONPATH"])

    def test_run_command_repairs_missing_sage_attention_and_retries(self) -> None:
        calls: list[list[str]] = []

        class Result:
            def __init__(self, stdout: str = "", stderr: str = "", returncode: int = 0) -> None:
                self.stdout = stdout
                self.stderr = stderr
                self.returncode = returncode

        def fake_run(command: list[str], *args: object, **kwargs: object) -> Result:
            calls.append(command)
            if command[:2] == ["comfy-videogen", "wan22-i2v"] and len(calls) == 1:
                return Result(
                    stdout=(
                        '{"ok": false, "error": "LOKI_COMFY_USE_SAGE_ATTENTION=1 requires '
                        'the sageattention package inside the comfy-agent-tools uv tool environment."}'
                    ),
                    returncode=1,
                )
            if "tool" in command and "sageattention" in command:
                return Result()
            return Result(stdout='{"ok": true}')

        with (
            tempfile.TemporaryDirectory() as tmpdir,
            patch.dict(comfy_action.os.environ, {}, clear=True),
            patch("comfy_action.subprocess.run", fake_run),
            patch("comfy_action.shutil.which", return_value="/usr/bin/uv"),
        ):
            result = comfy_action.run_command(["comfy-videogen", "wan22-i2v"], Path(tmpdir))

        self.assertEqual(result, {"ok": True})
        self.assertEqual(calls[0][:2], ["comfy-videogen", "wan22-i2v"])
        self.assertIn("sageattention", calls[1])
        self.assertEqual(calls[2][:2], ["comfy-videogen", "wan22-i2v"])

    def test_ensure_comfy_cli_repairs_missing_imagedescribe(self) -> None:
        which_calls = 0
        repairs: list[list[str]] = []

        def fake_which(command: str) -> str | None:
            nonlocal which_calls
            if command == "uv":
                return "/usr/bin/uv"
            which_calls += 1
            return None if which_calls == 1 else f"/usr/bin/{command}"

        def fake_run(command: list[str], *args: object, **kwargs: object) -> object:
            repairs.append(command)

            class Result:
                returncode = 0
                stdout = ""
                stderr = ""

            return Result()

        with (
            tempfile.TemporaryDirectory() as tmpdir,
            patch("comfy_action.shutil.which", fake_which),
            patch("comfy_action.subprocess.run", fake_run),
        ):
            comfy_action.ensure_comfy_cli(["comfy-imagedescribe", "describe"], Path(tmpdir))

        self.assertEqual(repairs[0][:4], ["/usr/bin/uv", "tool", "install", "--force"])
        self.assertIn("git+https://github.com/quinteroac/comfy-agent-tools", repairs[0])

    def test_comfy_image_edit_bernini_builds_single_frame_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir) / "models"):
            image = Path(tmpdir) / "input.png"
            image.write_bytes(b"not inspected when aspect ratio is provided")
            command, cwd = comfy_action.build_cli_command(
                {
                    "skillId": "comfy-image-edit",
                    "prompt": "Only change the jacket to red. Preserve everything else.",
                    "params": {
                        "modelProfile": "wan22-bernini-image",
                        "aspectRatio": "1:1",
                        "seed": 123,
                    },
                },
                Path(tmpdir) / "outputs",
                media={"image": [image], "audio": [], "video": []},
            )
            config = (cwd / ".comfy-agent-tools.json").read_text(encoding="utf-8")

        self.assertEqual(Path(command[1]).name, "comfy_videoedit.py")
        self.assertEqual(command[2], "bernini")
        self.assertEqual(command[command.index("--reference-image") + 1], str(image))
        self.assertEqual(command[command.index("--length") + 1], "1")
        self.assertEqual(command[command.index("--width") + 1], "1024")
        self.assertEqual(command[command.index("--height") + 1], "1024")
        self.assertIn('"videogen.wan22-bernini": "wan22-bernini"', config)

    def test_comfy_image_edit_bernini_extracts_png_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "outputs"
            out_dir.mkdir()
            source_video = out_dir / "result.mp4"
            source_video.write_bytes(b"video")

            class Result:
                returncode = 0
                stdout = ""
                stderr = ""

            def fake_run(command: list[str], **_kwargs: object) -> Result:
                Path(command[-1]).write_bytes(b"png")
                return Result()

            command = [sys.executable, str(Path(comfy_action.__file__).with_name("comfy_videoedit.py")), "bernini", "--out", str(out_dir), "--length", "1"]
            with patch("comfy_action.shutil.which", return_value="/usr/bin/ffmpeg"), patch("comfy_action.subprocess.run", fake_run):
                result = comfy_action.extract_bernini_image_artifact({"kind": "video", "artifacts": [str(source_video)]}, command)

        self.assertEqual(result["kind"], "image")
        self.assertEqual(result["mode"], "wan22-bernini-image")
        self.assertEqual(Path(result["artifacts"][0]).name, "bernini-image-edit.png")
        self.assertEqual(result["sourceVideoArtifact"], str(source_video))

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

    def test_ideogram4_applies_single_default_lora_at_half_strength(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir)):
            lora_path = Path(tmpdir) / "loras" / "ideogram4" / "Realism_Engine_Ideogram4_beta.safetensors"
            lora_path.parent.mkdir(parents=True)
            lora_path.write_bytes(b"")
            command, _cwd = comfy_action.build_cli_command(
                {
                    "skillId": "ideogram4-image",
                    "prompt": "Premium cinematic portrait",
                    "params": {
                        "mode": "t2i",
                        "qualityProfile": "Default",
                        "aspectRatio": "1:1",
                        "styleAesthetics": "premium realism, high detail",
                        "styleLighting": "soft studio lighting",
                        "styleMedium": "photograph",
                        "stylePhoto": "editorial portrait photography",
                        "background": "neutral studio backdrop",
                        "objects": [{"bbox": "120,160,920,860", "description": "centered portrait subject"}],
                    },
                },
                Path(tmpdir) / "outputs",
                media={"image": [], "audio": [], "video": []},
            )

        self.assertEqual(command[command.index("--extra-lora") + 1], f"{lora_path}:0.5")

    def test_ideogram4_uses_realism_default_lora_when_other_loras_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir)):
            lora_dir = Path(tmpdir) / "loras" / "ideogram4"
            lora_dir.mkdir(parents=True)
            default_lora = lora_dir / "Realism_Engine_Ideogram4_beta.safetensors"
            default_lora.write_bytes(b"")
            (lora_dir / "another-style.safetensors").write_bytes(b"")

            command, _cwd = comfy_action.build_cli_command(
                {
                    "skillId": "ideogram4-image",
                    "prompt": "Premium cinematic portrait",
                    "params": {
                        "mode": "t2i",
                        "qualityProfile": "Default",
                        "aspectRatio": "1:1",
                        "styleAesthetics": "premium realism, high detail",
                        "styleLighting": "soft studio lighting",
                        "styleMedium": "photograph",
                        "stylePhoto": "editorial portrait photography",
                        "background": "neutral studio backdrop",
                        "objects": [{"bbox": "120,160,920,860", "description": "centered portrait subject"}],
                    },
                },
                Path(tmpdir) / "outputs",
                media={"image": [], "audio": [], "video": []},
            )

        self.assertEqual(command[command.index("--extra-lora") + 1], f"{default_lora}:0.5")

    def test_ideogram4_normalizes_style_colors_to_rrggbb(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir)):
            command, _cwd = comfy_action.build_cli_command(
                {
                    "skillId": "ideogram4-image",
                    "prompt": "Graphic badge logo",
                    "params": {
                        "mode": "t2i",
                        "qualityProfile": "Default",
                        "aspectRatio": "1:1",
                        "styleAesthetics": "bold clean graphic design",
                        "styleLighting": "flat even lighting",
                        "styleMedium": "illustration",
                        "styleArtStyle": "vector poster art",
                        "styleColors": ["#abc", "0b0f14", "#F4D06F"],
                        "background": "solid color field",
                        "objects": [{"bbox": "180,180,820,820", "description": "centered circular badge emblem"}],
                    },
                },
                Path(tmpdir) / "outputs",
                media={"image": [], "audio": [], "video": []},
            )

        colors = [
            command[index + 1]
            for index, value in enumerate(command)
            if value == "--style-color"
        ]
        self.assertEqual(colors, ["#AABBCC", "#0B0F14", "#F4D06F"])

    def test_ideogram4_rejects_non_hex_style_colors_before_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir)):
            with self.assertRaisesRegex(RuntimeError, "#RRGGBB"):
                comfy_action.build_cli_command(
                    {
                        "skillId": "ideogram4-image",
                        "prompt": "Graphic badge logo",
                        "params": {
                            "mode": "t2i",
                            "qualityProfile": "Default",
                            "aspectRatio": "1:1",
                            "styleAesthetics": "bold clean graphic design",
                            "styleLighting": "flat even lighting",
                            "styleMedium": "illustration",
                            "styleArtStyle": "vector poster art",
                            "styleColors": ["white"],
                            "background": "solid color field",
                            "objects": [{"bbox": "180,180,820,820", "description": "centered circular badge emblem"}],
                        },
                    },
                    Path(tmpdir) / "outputs",
                    media={"image": [], "audio": [], "video": []},
                )

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

    def test_comfy_imagedescribe_builds_describe_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir) / "models"):
            image = Path(tmpdir) / "input.png"
            image.write_bytes(b"image")
            command, cwd = comfy_action.build_cli_command(
                {
                    "skillId": "comfy-imagedescribe",
                    "prompt": "Describe the character, wardrobe, lighting, and composition.",
                    "params": {"maxLength": 256, "seed": 7, "greedy": True},
                },
                Path(tmpdir) / "outputs",
                media={"image": [image], "audio": [], "video": []},
            )
            config = (cwd / ".comfy-agent-tools.json").read_text(encoding="utf-8")

        self.assertEqual(command[:2], ["comfy-imagedescribe", "describe"])
        self.assertEqual(command[command.index("--models-dir") + 1], str(Path(tmpdir) / "models"))
        self.assertEqual(command[command.index("--input") + 1], str(image))
        self.assertEqual(command[command.index("--prompt") + 1], "Describe the character, wardrobe, lighting, and composition.")
        self.assertEqual(command[command.index("--out") + 1], str(Path(tmpdir) / "outputs"))
        self.assertIn("--no-manifest", command)
        self.assertEqual(command[command.index("--max-length") + 1], "256")
        self.assertEqual(command[command.index("--seed") + 1], "7")
        self.assertIn("--greedy", command)
        self.assertIn('"imagedescribe.describe": "qwen3vl-2b-instruct"', config)

    def test_comfy_imagedescribe_requires_image(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir) / "models"):
            with self.assertRaisesRegex(RuntimeError, "requires one selected or attached local image artifact"):
                comfy_action.build_cli_command(
                    {"skillId": "comfy-imagedescribe", "prompt": "Describe this image.", "params": {}},
                    Path(tmpdir) / "outputs",
                    media={"image": [], "audio": [], "video": []},
                )

    def test_raw_result_converts_imagedescribe_description_to_text_metadata(self) -> None:
        raw = comfy_action.raw_result_from_cli(
            {
                "ok": True,
                "kind": "text",
                "mode": "describe",
                "input": "/tmp/input.png",
                "description": "A portrait with warm studio lighting.",
            },
            ["comfy-imagedescribe", "describe"],
            "Describe this image.",
        )

        self.assertEqual(raw["text"], "A portrait with warm studio lighting.")
        self.assertEqual(raw["metadata"]["imageDescription"], "A portrait with warm studio lighting.")
        self.assertEqual(raw["metadata"]["tool"], "comfy-imagedescribe")

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

    def test_comfy_image_generate_does_not_apply_runtime_nsfw_filter(self) -> None:
        original_prompt = "adult erotic editorial portrait, private studio lighting, explicit boudoir styling"

        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir)):
            command, _cwd = comfy_action.build_imagegen_command(
                mode="generate",
                params={"modelProfile": "flux-klein-9b-snofs", "aspectRatio": "1:1"},
                prompt=original_prompt,
                out_dir=Path(tmpdir) / "outputs",
                media={"image": [], "audio": [], "video": []},
                require_model_profile=True,
                require_aspect_ratio=True,
                require_input_image=False,
                skill_label="comfy-image-generate",
            )

        self.assertEqual(command[command.index("--prompt") + 1], original_prompt)

    def test_comfy_image_generate_r2i_requires_local_image_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir)):
            with self.assertRaisesRegex(RuntimeError, "r2i requires"):
                comfy_action.build_cli_command(
                    {
                        "skillId": "comfy-image-generate",
                        "prompt": "masterpiece, best quality, anime illustration, 1girl, solo",
                        "params": {
                            "mode": "r2i",
                            "modelProfile": "anima-base",
                            "aspectRatio": "1:1",
                        },
                    },
                    Path(tmpdir) / "outputs",
                    media={"image": [], "audio": [], "video": []},
                )

    def test_comfy_image_generate_r2i_maps_to_generate_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir)):
            image = Path(tmpdir) / "input.png"
            image.write_bytes(b"png")
            command, cwd = comfy_action.build_cli_command(
                {
                    "skillId": "comfy-image-generate",
                    "prompt": "masterpiece, best quality, anime illustration, 1girl, solo, black hair, red jacket",
                    "params": {
                        "mode": "r2i",
                        "modelProfile": "anima-base",
                        "aspectRatio": "1:1",
                    },
                },
                Path(tmpdir) / "outputs",
                media={"image": [image], "audio": [], "video": []},
            )
            config = (cwd / ".comfy-agent-tools.json").read_text(encoding="utf-8")

        self.assertEqual(command[:2], ["comfy-imagegen", "generate"])
        self.assertNotIn("--input", command)
        self.assertEqual(command[command.index("--prompt") + 1], "masterpiece, best quality, anime illustration, 1girl, solo, black hair, red jacket")
        self.assertIn('"imagegen.generate": "anima-base"', config)

    def test_comfy_image_generate_r2i_rejects_reference_language(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir)):
            with self.assertRaisesRegex(RuntimeError, "standalone visual description"):
                comfy_action.build_cli_command(
                    {
                        "skillId": "comfy-image-generate",
                        "prompt": "usar la imagen de referencia para crear una version nueva",
                        "params": {
                            "mode": "r2i",
                            "modelProfile": "flux-klein-9b-snofs",
                            "aspectRatio": "1:1",
                        },
                    },
                    Path(tmpdir) / "outputs",
                    media={"image": [Path(tmpdir) / "input.png"], "audio": [], "video": []},
                )

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
                        "modelProfile": "wan22-dasiwa-boundbite-i2v",
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
        self.assertIn('"videogen.wan22-i2v": "wan22-dasiwa-boundbite-i2v"', config)

    def test_ltx_r2v_maps_to_t2v_without_input_image(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir)):
            image = Path(tmpdir) / "reference.png"
            command, cwd = comfy_action.build_cli_command(
                {
                    "skillId": "comfy-videogen",
                    "prompt": "A red-haired woman in a lace dress stands in a candlelit room while the camera slowly drifts forward.",
                    "params": {
                        "modelProfile": "ltx23-10eros",
                        "videoMode": "r2v",
                        "aspectRatio": "16:9",
                        "resolution": "480p",
                        "duration": "5",
                    },
                },
                Path(tmpdir) / "outputs",
                media={"image": [image], "audio": [], "video": []},
            )
            config = (cwd / ".comfy-agent-tools.json").read_text(encoding="utf-8")

        self.assertEqual(command[:2], ["comfy-videogen", "t2v"])
        self.assertNotIn("--input", command)
        self.assertEqual(command[command.index("--length") + 1], "120")
        self.assertIn('"videogen.t2v": "ltx23-10eros"', config)

    def test_wan_r2v_maps_to_wan_t2v_without_input_image(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir)):
            image = Path(tmpdir) / "reference.png"
            command, cwd = comfy_action.build_cli_command(
                {
                    "skillId": "comfy-videogen",
                    "prompt": "A moonlit armored figure crosses a shallow reflective pool while mist curls around the scene.",
                    "params": {
                        "modelProfile": "wan22-dasiwa-boundbite-i2v",
                        "videoMode": "r2v",
                        "aspectRatio": "16:9",
                        "resolution": "480p",
                        "duration": "5",
                        "fps": "24",
                    },
                },
                Path(tmpdir) / "outputs",
                media={"image": [image], "audio": [], "video": []},
            )
            config = (cwd / ".comfy-agent-tools.json").read_text(encoding="utf-8")

        self.assertEqual(command[:2], ["comfy-videogen", "wan22-t2v"])
        self.assertNotIn("--input", command)
        self.assertEqual(command[command.index("--fps") + 1], "24")
        self.assertEqual(command[command.index("--length") + 1], "121")
        self.assertIn('"videogen.wan22-t2v": "wan22-dasiwa-boundbite-t2v"', config)

    def test_r2v_requires_input_image(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir)):
            with self.assertRaisesRegex(RuntimeError, "r2v requires one input image"):
                comfy_action.build_cli_command(
                    {
                        "skillId": "comfy-videogen",
                        "prompt": "slow motion",
                        "params": {
                            "modelProfile": "ltx23-10eros",
                            "videoMode": "r2v",
                            "aspectRatio": "16:9",
                            "resolution": "480p",
                            "duration": "5",
                        },
                    },
                    Path(tmpdir) / "outputs",
                    media={"image": [], "audio": [], "video": []},
                )

    def test_seedance_r2v_is_not_supported_by_comfy_videogen_skill_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir)):
            with self.assertRaisesRegex(RuntimeError, "r2v supports only LTX 2.3 and WAN 2.2"):
                comfy_action.build_cli_command(
                    {
                        "skillId": "comfy-videogen",
                        "prompt": "slow motion",
                        "params": {
                            "modelProfile": "seedance2-api",
                            "videoMode": "r2v",
                            "aspectRatio": "16:9",
                            "resolution": "480p",
                            "duration": "5",
                        },
                    },
                    Path(tmpdir) / "outputs",
                    media={"image": [Path(tmpdir) / "reference.png"], "audio": [], "video": []},
                )

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

    def test_comfy_videogen_does_not_apply_runtime_nsfw_filter(self) -> None:
        original_prompt = "adult erotic scene in a private room, slow intimate camera drift, explicit mature styling"

        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir)):
            command, _cwd = comfy_action.build_cli_command(
                {
                    "skillId": "comfy-videogen",
                    "prompt": original_prompt,
                    "params": {
                        "modelProfile": "ltx23-10eros",
                        "videoMode": "t2v",
                        "aspectRatio": "16:9",
                        "resolution": "480p",
                        "duration": "5",
                    },
                },
                Path(tmpdir) / "outputs",
                media={"image": [], "audio": [], "video": []},
            )

        self.assertEqual(command[command.index("--prompt") + 1], original_prompt)

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

    def test_videoedit_audio_driven_builds_wrapper_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir)):
            video = Path(tmpdir) / "input.mp4"
            audio = Path(tmpdir) / "voice.wav"
            command, cwd = comfy_action.build_cli_command(
                {
                    "skillId": "comfy-videoedit",
                    "prompt": "Preserve the original framing while syncing the performance to the new vocal.",
                    "params": {
                        "editMode": "audio-driven",
                        "modelProfile": "wan22-dasiwa-littledemon-v2-video-audio",
                        "steps": "12",
                        "denoise": "0.45",
                        "seed": "123",
                    },
                },
                Path(tmpdir) / "outputs",
                media={"image": [], "audio": [audio], "video": [video]},
            )
            config = (cwd / ".comfy-agent-tools.json").read_text(encoding="utf-8")

        self.assertEqual(Path(command[1]).name, "comfy_videoedit.py")
        self.assertEqual(command[2], "video-audio")
        self.assertEqual(command[command.index("--mode") + 1], "audio-driven")
        self.assertEqual(command[command.index("--input-video") + 1], str(video))
        self.assertEqual(command[command.index("--audio") + 1], str(audio))
        self.assertEqual(command[command.index("--prompt") + 1], "Preserve the original framing while syncing the performance to the new vocal.")
        self.assertEqual(command[command.index("--steps") + 1], "12")
        self.assertEqual(command[command.index("--denoise") + 1], "0.45")
        self.assertEqual(command[command.index("--seed") + 1], "123")
        self.assertIn('"videogen.wan22-video-audio": "wan22-dasiwa-littledemon-v2-video-audio"', config)

    def test_videoedit_lipsync_requires_video_and_audio(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir)):
            payload = {
                "skillId": "comfy-videoedit",
                "prompt": "Lip sync the subject.",
                "params": {"editMode": "lipsync"},
            }
            with self.assertRaisesRegex(RuntimeError, "requires one input video"):
                comfy_action.build_cli_command(
                    payload,
                    Path(tmpdir) / "outputs",
                    media={"image": [], "audio": [Path(tmpdir) / "voice.wav"], "video": []},
                )
            with self.assertRaisesRegex(RuntimeError, "requires one input audio"):
                comfy_action.build_cli_command(
                    payload,
                    Path(tmpdir) / "outputs",
                    media={"image": [], "audio": [], "video": [Path(tmpdir) / "input.mp4"]},
                )

    def test_comfy_upscale_video_builds_rtx_vsr_command_from_selected_video(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir) / "models"):
            video = Path(tmpdir) / "input.mp4"
            command, cwd = comfy_action.build_cli_command(
                {
                    "skillId": "comfy-upscale-video",
                    "params": {
                        "resolution": "4k",
                        "quality": "HIGH",
                    },
                },
                Path(tmpdir) / "outputs",
                media={"image": [], "audio": [], "video": [video]},
            )
            config = (cwd / ".comfy-agent-tools.json").read_text(encoding="utf-8")

        self.assertEqual(command[:2], ["comfy-videogen", "rtx-upscale"])
        self.assertNotIn("--models-dir", command)
        self.assertEqual(command[command.index("--input-video") + 1], str(video))
        self.assertEqual(command[command.index("--resolution") + 1], "4k")
        self.assertEqual(command[command.index("--quality") + 1], "HIGH")
        self.assertEqual(command[command.index("--out") + 1], str(Path(tmpdir) / "outputs"))
        self.assertIn('"videogen.rtx-upscale": "rtx-vsr"', config)

    def test_comfy_upscale_video_accepts_input_video_path_param(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir) / "models"):
            video = Path(tmpdir) / "explicit.mp4"
            command, _cwd = comfy_action.build_cli_command(
                {
                    "skillId": "comfy-upscale-video",
                    "params": {
                        "inputVideoPath": str(video),
                        "resolution": "1080p",
                        "quality": "ultra",
                    },
                },
                Path(tmpdir) / "outputs",
                media={"image": [], "audio": [], "video": []},
            )

        self.assertEqual(command[:2], ["comfy-videogen", "rtx-upscale"])
        self.assertEqual(command[command.index("--input-video") + 1], str(video))
        self.assertEqual(command[command.index("--quality") + 1], "ULTRA")

    def test_comfy_upscale_video_builds_seedvr2_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.repo_root", return_value=Path(tmpdir)):
            video = Path(tmpdir) / "input.mp4"
            command, cwd = comfy_action.build_cli_command(
                {
                    "skillId": "comfy-upscale-video",
                    "params": {
                        "engine": "seedvr2",
                        "inputVideoPath": str(video),
                        "resolution": "1440p",
                        "processingMode": "single",
                    },
                },
                Path(tmpdir) / "outputs",
                media={"image": [], "audio": [], "video": []},
            )
            config = (cwd / ".comfy-agent-tools.json").read_text(encoding="utf-8")

        self.assertEqual(command[:2], ["comfy-videogen", "seedvr2-upscale"])
        self.assertNotIn("--quality", command)
        self.assertEqual(command[command.index("--input-video") + 1], str(video))
        self.assertEqual(command[command.index("--resolution") + 1], "1440p")
        self.assertEqual(command[command.index("--models-dir") + 1], str(Path(tmpdir) / ".loki" / "models" / "comfyui" / "seedvr2"))
        self.assertEqual(command[command.index("--out") + 1], str(Path(tmpdir) / "outputs"))
        self.assertIn('"videogen.seedvr2-upscale": "seedvr2"', config)

    def test_comfy_upscale_video_long_mode_splits_upscales_and_concats_segments(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_video = Path(tmpdir) / "input.mp4"
            input_video.write_bytes(b"video")
            out_dir = Path(tmpdir) / "outputs"
            out_dir.mkdir()
            command = [
                "comfy-videogen",
                "rtx-upscale",
                "--input-video",
                str(input_video),
                "--resolution",
                "4k",
                "--quality",
                "HIGH",
                "--out",
                str(out_dir),
            ]
            ffmpeg_commands: list[list[str]] = []
            upscale_commands: list[list[str]] = []

            class Result:
                def __init__(self, stdout: str = "", stderr: str = "", returncode: int = 0) -> None:
                    self.stdout = stdout
                    self.stderr = stderr
                    self.returncode = returncode

            def fake_subprocess_run(command: list[str], **_kwargs: object) -> Result:
                if command[0] == "ffprobe":
                    return Result(stdout="65.2\n")
                self.assertEqual(command[0], "ffmpeg")
                ffmpeg_commands.append(command)
                Path(command[-1]).parent.mkdir(parents=True, exist_ok=True)
                Path(command[-1]).write_bytes(b"mp4")
                return Result()

            def fake_run_command(segment_command: list[str], _cwd: Path) -> dict[str, object]:
                upscale_commands.append(segment_command)
                segment_out = Path(segment_command[segment_command.index("--out") + 1])
                segment_out.mkdir(parents=True, exist_ok=True)
                artifact = segment_out / "upscaled.mp4"
                artifact.write_bytes(b"upscaled")
                return {"kind": "video", "artifacts": [str(artifact)]}

            with (
                patch("comfy_action.shutil.which", return_value="/usr/bin/tool"),
                patch("comfy_action.subprocess.run", fake_subprocess_run),
                patch("comfy_action.run_command", fake_run_command),
            ):
                raw = comfy_action.run_chunked_video_upscale(command, Path(tmpdir), out_dir, "Upscale this video")

        self.assertEqual(len(upscale_commands), 3)
        split_commands = [cmd for cmd in ffmpeg_commands if "-ss" in cmd]
        self.assertEqual(len(split_commands), 3)
        self.assertEqual([cmd[cmd.index("-ss") + 1] for cmd in split_commands], ["0", "30", "60"])
        self.assertEqual([cmd[cmd.index("-t") + 1] for cmd in split_commands], ["30", "30", "5.201"])
        for split_command in split_commands:
            self.assertLess(split_command.index("-i"), split_command.index("-ss"))
            self.assertNotIn("copy", split_command)
            self.assertEqual(split_command[split_command.index("-c:v") + 1], "libx264")
            self.assertEqual(split_command[split_command.index("-map") + 1], "0:v:0")
            self.assertIn("0:a?", split_command)
        self.assertEqual(len([cmd for cmd in ffmpeg_commands if "-f" in cmd and "concat" in cmd]), 1)
        self.assertEqual(raw["artifacts"][0]["kind"], "video")
        self.assertEqual(Path(raw["artifacts"][0]["path"]).name, "rtx-upscaled-long.mp4")
        self.assertEqual(raw["artifacts"][0]["metadata"]["segmentCount"], 3)
        for segment_command in upscale_commands:
            self.assertEqual(segment_command[:2], ["comfy-videogen", "rtx-upscale"])
            self.assertNotIn("--models-dir", segment_command)
            self.assertEqual(segment_command[segment_command.index("--resolution") + 1], "4k")
            self.assertEqual(segment_command[segment_command.index("--quality") + 1], "HIGH")

    def test_comfy_upscale_video_seedvr2_long_mode_uses_same_chunk_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_video = Path(tmpdir) / "input.mp4"
            input_video.write_bytes(b"video")
            out_dir = Path(tmpdir) / "outputs"
            out_dir.mkdir()
            command = [
                "comfy-videogen",
                "seedvr2-upscale",
                "--input-video",
                str(input_video),
                "--resolution",
                "1080p",
                "--models-dir",
                str(Path(tmpdir) / "models" / "seedvr2"),
                "--out",
                str(out_dir),
            ]
            ffmpeg_commands: list[list[str]] = []
            upscale_commands: list[list[str]] = []

            class Result:
                def __init__(self, stdout: str = "", stderr: str = "", returncode: int = 0) -> None:
                    self.stdout = stdout
                    self.stderr = stderr
                    self.returncode = returncode

            def fake_subprocess_run(command: list[str], **_kwargs: object) -> Result:
                if command[0] == "ffprobe":
                    return Result(stdout="61\n")
                self.assertEqual(command[0], "ffmpeg")
                ffmpeg_commands.append(command)
                Path(command[-1]).parent.mkdir(parents=True, exist_ok=True)
                Path(command[-1]).write_bytes(b"mp4")
                return Result()

            def fake_run_command(segment_command: list[str], _cwd: Path) -> dict[str, object]:
                upscale_commands.append(segment_command)
                segment_out = Path(segment_command[segment_command.index("--out") + 1])
                segment_out.mkdir(parents=True, exist_ok=True)
                artifact = segment_out / "seedvr2.mp4"
                artifact.write_bytes(b"seedvr2")
                return {"kind": "video", "artifacts": [str(artifact)]}

            with (
                patch("comfy_action.shutil.which", return_value="/usr/bin/tool"),
                patch("comfy_action.subprocess.run", fake_subprocess_run),
                patch("comfy_action.run_command", fake_run_command),
            ):
                raw = comfy_action.run_chunked_video_upscale(command, Path(tmpdir), out_dir, "Upscale with SeedVR2")

        self.assertEqual(len(upscale_commands), 3)
        self.assertEqual(len([cmd for cmd in ffmpeg_commands if "-ss" in cmd]), 3)
        self.assertEqual(raw["artifacts"][0]["kind"], "video")
        self.assertEqual(Path(raw["artifacts"][0]["path"]).name, "seedvr2-upscaled-long.mp4")
        self.assertEqual(raw["artifacts"][0]["metadata"]["mode"], "seedvr2-upscale-long")
        self.assertEqual(raw["artifacts"][0]["metadata"]["engine"], "seedvr2")
        self.assertEqual(raw["artifacts"][0]["metadata"]["segmentCount"], 3)
        self.assertEqual(raw["artifacts"][0]["metadata"]["resolution"], "1080p")
        self.assertNotIn("quality", raw["artifacts"][0]["metadata"])
        for segment_command in upscale_commands:
            self.assertEqual(segment_command[:2], ["comfy-videogen", "seedvr2-upscale"])
            self.assertIn("--models-dir", segment_command)

    def test_comfy_upscale_video_repairs_missing_dependency_and_retries(self) -> None:
        calls: list[list[str]] = []

        class Result:
            def __init__(self, stdout: str = "", stderr: str = "", returncode: int = 0) -> None:
                self.stdout = stdout
                self.stderr = stderr
                self.returncode = returncode

        def fake_subprocess_run(command: list[str], **_kwargs: object) -> Result:
            calls.append(command)
            if command[:2] == ["comfy-videogen", "rtx-upscale"] and len(calls) == 1:
                return Result(stdout='{"ok": false, "error_type": "missing_dependency", "error": "nvidia-vfx missing"}', returncode=1)
            if command[:3] == ["/usr/bin/uv", "tool", "upgrade"]:
                return Result(stdout="upgraded")
            return Result(stdout='{"ok": true, "kind": "video", "artifacts": ["/tmp/upscaled.mp4"]}')

        with (
            tempfile.TemporaryDirectory() as tmpdir,
            patch("comfy_action.shutil.which", side_effect=lambda name: f"/usr/bin/{name}"),
            patch("comfy_action.subprocess.run", fake_subprocess_run),
        ):
            result = comfy_action.run_command(["comfy-videogen", "rtx-upscale"], Path(tmpdir))

        self.assertTrue(result["ok"])
        self.assertEqual(
            calls[1],
            [
                "/usr/bin/uv",
                "tool",
                "install",
                "--force",
                "--with",
                "sageattention",
                "--with",
                "nvidia-vfx",
                "git+https://github.com/quinteroac/comfy-agent-tools",
            ],
        )
        self.assertEqual(calls[2][:2], ["comfy-videogen", "rtx-upscale"])

    def test_comfy_upscale_video_repairs_missing_seedvr2_subcommand_and_retries(self) -> None:
        calls: list[list[str]] = []

        class Result:
            def __init__(self, stdout: str = "", stderr: str = "", returncode: int = 0) -> None:
                self.stdout = stdout
                self.stderr = stderr
                self.returncode = returncode

        def fake_subprocess_run(command: list[str], **_kwargs: object) -> Result:
            calls.append(command)
            if command[:2] == ["comfy-videogen", "seedvr2-upscale"] and len(calls) == 1:
                return Result(stderr="argument command: invalid choice: 'seedvr2-upscale'", returncode=2)
            if command[:3] == ["/usr/bin/uv", "tool", "upgrade"]:
                return Result(stdout="upgraded")
            return Result(stdout='{"ok": true, "kind": "video", "artifacts": ["/tmp/seedvr2.mp4"]}')

        with (
            tempfile.TemporaryDirectory() as tmpdir,
            patch("comfy_action.shutil.which", side_effect=lambda name: f"/usr/bin/{name}"),
            patch("comfy_action.subprocess.run", fake_subprocess_run),
        ):
            result = comfy_action.run_command(["comfy-videogen", "seedvr2-upscale"], Path(tmpdir))

        self.assertTrue(result["ok"])
        self.assertEqual(
            calls[1],
            [
                "/usr/bin/uv",
                "tool",
                "install",
                "--force",
                "--with",
                "sageattention",
                "--with",
                "nvidia-vfx",
                "git+https://github.com/quinteroac/comfy-agent-tools",
            ],
        )
        self.assertEqual(calls[2][:2], ["comfy-videogen", "seedvr2-upscale"])

    def test_comfy_upscale_video_does_not_repair_hardware_required(self) -> None:
        calls: list[list[str]] = []

        class Result:
            stdout = '{"ok": false, "error_type": "hardware_required", "error": "RTX GPU required"}'
            stderr = ""
            returncode = 1

        def fake_subprocess_run(command: list[str], **_kwargs: object) -> Result:
            calls.append(command)
            return Result()

        with (
            tempfile.TemporaryDirectory() as tmpdir,
            patch("comfy_action.shutil.which", side_effect=lambda name: f"/usr/bin/{name}"),
            patch("comfy_action.subprocess.run", fake_subprocess_run),
        ):
            with self.assertRaisesRegex(RuntimeError, "hardware_required"):
                comfy_action.run_command(["comfy-videogen", "rtx-upscale"], Path(tmpdir))

        self.assertEqual(calls, [["comfy-videogen", "rtx-upscale"]])

    def test_comfy_upscale_video_requires_video_resolution_and_quality(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir) / "models"):
            payload = {
                "skillId": "comfy-upscale-video",
                "params": {"resolution": "1080p", "quality": "ULTRA"},
            }
            with self.assertRaisesRegex(RuntimeError, "requires one input video"):
                comfy_action.build_cli_command(payload, Path(tmpdir) / "outputs", media={"image": [], "audio": [], "video": []})

            payload["params"] = {"quality": "ULTRA", "inputVideoPath": str(Path(tmpdir) / "input.mp4")}
            with self.assertRaisesRegex(RuntimeError, "requires params.resolution"):
                comfy_action.build_cli_command(payload, Path(tmpdir) / "outputs", media={"image": [], "audio": [], "video": []})

            payload["params"] = {"resolution": "1080p", "inputVideoPath": str(Path(tmpdir) / "input.mp4")}
            with self.assertRaisesRegex(RuntimeError, "requires params.quality"):
                comfy_action.build_cli_command(payload, Path(tmpdir) / "outputs", media={"image": [], "audio": [], "video": []})

            payload["params"] = {"resolution": "2160p", "quality": "ULTRA", "inputVideoPath": str(Path(tmpdir) / "input.mp4")}
            with self.assertRaisesRegex(RuntimeError, "params.resolution"):
                comfy_action.build_cli_command(payload, Path(tmpdir) / "outputs", media={"image": [], "audio": [], "video": []})

            payload["params"] = {"resolution": "1080p", "quality": "BEST", "inputVideoPath": str(Path(tmpdir) / "input.mp4")}
            with self.assertRaisesRegex(RuntimeError, "params.quality"):
                comfy_action.build_cli_command(payload, Path(tmpdir) / "outputs", media={"image": [], "audio": [], "video": []})

            payload["params"] = {"engine": "seedvr2", "resolution": "8k", "inputVideoPath": str(Path(tmpdir) / "input.mp4")}
            with self.assertRaisesRegex(RuntimeError, "SeedVR2 params.resolution"):
                comfy_action.build_cli_command(payload, Path(tmpdir) / "outputs", media={"image": [], "audio": [], "video": []})

            payload["params"] = {"engine": "seedvr2", "resolution": "480p", "inputVideoPath": str(Path(tmpdir) / "input.mp4")}
            with self.assertRaisesRegex(RuntimeError, "SeedVR2 params.resolution"):
                comfy_action.build_cli_command(payload, Path(tmpdir) / "outputs", media={"image": [], "audio": [], "video": []})

            payload["params"] = {
                "resolution": "1080p",
                "quality": "ULTRA",
                "processingMode": "automatic",
                "inputVideoPath": str(Path(tmpdir) / "input.mp4"),
            }
            with self.assertRaisesRegex(RuntimeError, "params.processingMode"):
                comfy_action.build_cli_command(payload, Path(tmpdir) / "outputs", media={"image": [], "audio": [], "video": []})

    def test_videoedit_bernini_builds_reference_guided_command(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            patch("comfy_action.models_dir", return_value=Path(tmpdir)),
            patch("comfy_action.video_file_dimensions", return_value=(1280, 720)),
        ):
            video = Path(tmpdir) / "input.mp4"
            reference = Path(tmpdir) / "reference.png"
            command, cwd = comfy_action.build_cli_command(
                {
                    "skillId": "comfy-videoedit",
                    "prompt": "A cinematic reference-guided edit preserves the actor identity while changing the scene to a rainy neon street.",
                    "params": {
                        "editMode": "bernini",
                        "berniniMode": "rv2v",
                        "aspectRatio": "16:9",
                        "resolution": "480p",
                        "duration": "5",
                        "fps": "16",
                        "highLoraStrength": "0.7",
                        "lowLoraStrength": "0.5",
                    },
                },
                Path(tmpdir) / "outputs",
                media={"image": [reference], "audio": [], "video": [video]},
            )
            config = (cwd / ".comfy-agent-tools.json").read_text(encoding="utf-8")

        self.assertEqual(Path(command[1]).name, "comfy_videoedit.py")
        self.assertEqual(command[2], "bernini")
        self.assertEqual(command[command.index("--input-video") + 1], str(video))
        self.assertEqual(command[command.index("--reference-image") + 1], str(reference))
        self.assertEqual(command[command.index("--width") + 1], "1280")
        self.assertEqual(command[command.index("--height") + 1], "720")
        self.assertEqual(command[command.index("--length") + 1], "81")
        self.assertEqual(command[command.index("--fps") + 1], "16")
        self.assertEqual(command[command.index("--unet-high") + 1], str(Path(tmpdir) / "diffusion_models" / "Wan22_Bernini_HIGH_mxfp8.safetensors"))
        self.assertEqual(command[command.index("--unet-low") + 1], str(Path(tmpdir) / "diffusion_models" / "Wan22_Bernini_LOW_mxfp8.safetensors"))
        self.assertEqual(command[command.index("--lora") + 1], str(Path(tmpdir) / "loras" / "wan22" / "lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16_.safetensors"))
        self.assertEqual(command[command.index("--text-encoder") + 1], str(Path(tmpdir) / "clip" / "nsfw_wan_umt5-xxl_fp8_scaled.safetensors"))
        self.assertEqual(command[command.index("--vae") + 1], str(Path(tmpdir) / "vae" / "wan_2.1_vae.safetensors"))
        self.assertEqual(command[command.index("--high-lora-strength") + 1], "0.7")
        self.assertEqual(command[command.index("--low-lora-strength") + 1], "0.5")
        self.assertIn('"videogen.wan22-bernini": "wan22-bernini"', config)

    def test_videoedit_bernini_r2v_uses_loki_resolution_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir)):
            reference = Path(tmpdir) / "reference.png"
            command, _cwd = comfy_action.build_cli_command(
                {
                    "skillId": "comfy-videoedit",
                    "prompt": "A reference-guided Bernini video shows the character walking through a neon hallway.",
                    "params": {
                        "editMode": "bernini",
                        "berniniMode": "r2v",
                        "aspectRatio": "9:16",
                        "resolution": "720p",
                        "duration": "10",
                        "fps": "24",
                    },
                },
                Path(tmpdir) / "outputs",
                media={"image": [reference], "audio": [], "video": []},
            )

        self.assertEqual(command[:3], [sys.executable, str(Path(comfy_action.__file__).with_name("comfy_videoedit.py")), "bernini"])
        self.assertNotIn("--input-video", command)
        self.assertEqual(command[command.index("--reference-image") + 1], str(reference))
        self.assertEqual(command[command.index("--width") + 1], "720")
        self.assertEqual(command[command.index("--height") + 1], "1280")
        self.assertEqual(command[command.index("--fps") + 1], "24")
        self.assertEqual(command[command.index("--length") + 1], "241")

    def test_videoedit_bernini_r2v_requires_frame_fps_and_duration(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("comfy_action.models_dir", return_value=Path(tmpdir)):
            payload = {
                "skillId": "comfy-videoedit",
                "prompt": "A reference-guided Bernini video.",
                "params": {"editMode": "bernini", "berniniMode": "r2v", "duration": "5"},
            }
            with self.assertRaisesRegex(RuntimeError, "requires params.aspectRatio and params.resolution"):
                comfy_action.build_cli_command(
                    payload,
                    Path(tmpdir) / "outputs",
                    media={"image": [Path(tmpdir) / "reference.png"], "audio": [], "video": []},
                )

            payload["params"] = {
                "editMode": "bernini",
                "berniniMode": "r2v",
                "aspectRatio": "16:9",
                "resolution": "480p",
                "duration": "5",
            }
            with self.assertRaisesRegex(RuntimeError, "requires params.fps"):
                comfy_action.build_cli_command(
                    payload,
                    Path(tmpdir) / "outputs",
                    media={"image": [Path(tmpdir) / "reference.png"], "audio": [], "video": []},
                )

            payload["params"] = {
                "editMode": "bernini",
                "berniniMode": "r2v",
                "aspectRatio": "16:9",
                "resolution": "480p",
                "fps": "24",
            }
            with self.assertRaisesRegex(RuntimeError, "requires params.duration"):
                comfy_action.build_cli_command(
                    payload,
                    Path(tmpdir) / "outputs",
                    media={"image": [Path(tmpdir) / "reference.png"], "audio": [], "video": []},
                )

            payload["params"] = {
                "editMode": "bernini",
                "berniniMode": "r2v",
                "aspectRatio": "16:9",
                "resolution": "480p",
                "duration": "5",
                "fps": "30",
            }
            with self.assertRaisesRegex(RuntimeError, "WAN FPS must be 16 or 24"):
                comfy_action.build_cli_command(
                    payload,
                    Path(tmpdir) / "outputs",
                    media={"image": [Path(tmpdir) / "reference.png"], "audio": [], "video": []},
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
