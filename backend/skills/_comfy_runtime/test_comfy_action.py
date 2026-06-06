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
                        "lora": {"name": "blue motion", "strength": 0.75},
                    },
                },
                Path(tmpdir) / "outputs",
                media={"image": [image], "audio": [], "video": []},
            )
            config = (cwd / ".comfy-agent-tools.json").read_text(encoding="utf-8")

        self.assertEqual(command[:2], ["comfy-videogen", "wan22-i2v"])
        self.assertEqual(command[command.index("--extra-lora") + 1], f"{lora_path}:0.75")
        self.assertIn('"videogen.wan22-i2v": "wan22-i2v"', config)

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
                        "extraLoraHigh": high_lora,
                        "extraLoraLow": low_lora,
                    },
                },
                Path(tmpdir) / "outputs",
                media={"image": [first, last], "audio": [], "video": []},
            )

        self.assertEqual(command[:2], ["comfy-videogen", "wan22-flf2v"])
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
        self.assertEqual(command[command.index("--length") + 1], "224")
        self.assertEqual(command[command.index("--fps") + 1], "16")
        self.assertEqual(command[command.index("--audio-duration") + 1], "14")
        self.assertEqual(command[command.index("--prompt") + 1], "In the video, a singer performs with emotional expression and subtle camera motion.")
        self.assertNotIn("--duration", command)
        self.assertNotIn("--high-steps", command)
        self.assertNotIn("--low-steps", command)
        self.assertIn('"videogen.wan22-s2v": "wan22-s2v"', config)

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
