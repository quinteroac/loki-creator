from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app.models import ComfyGenerationRequest
from app.services import card_packager
from app.services.comfy_generation import ComfyGenerationError, ComfyGenerationService


class ComfyGenerationServiceTest(unittest.TestCase):
    def request(self, **overrides: object) -> ComfyGenerationRequest:
        data = {
            "prompt": "cinematic concept art",
            "tool": "image",
            "imageMode": "generate",
            "videoMode": "t2v",
            "modelProfile": "anima-base",
            "aspectRatio": "16:9",
            "resolution": "480p",
            "duration": 5,
            "selectedCardSnapshots": [],
            "attachments": [],
        }
        data.update(overrides)
        return ComfyGenerationRequest.model_validate(data)

    def service(self, root: str) -> ComfyGenerationService:
        return ComfyGenerationService(Path(root))

    def media_file(self, root: str, name: str = "input.png") -> Path:
        path = Path(root) / "imports" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (64, 64), "black").save(path)
        return path

    def completed_process(self, stdout: str, *, returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=["comfy"], returncode=returncode, stdout=stdout, stderr=stderr)

    def test_builds_image_generate_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict("os.environ", {"LOKI_COMFY_MODELS_DIR": str(Path(tmpdir) / "models")}):
            service = self.service(tmpdir)
            out_dir = service.output_dir("run")
            with patch.object(service, "executable", return_value="comfy-imagegen"):
                command, cwd, kind, params = service.build_command(self.request(), "cinematic concept art", out_dir, {"image": [], "video": [], "audio": []})
            self.assertTrue((cwd / ".comfy-agent-tools.json").is_file())

        self.assertEqual(command[:2], ["comfy-imagegen", "generate"])
        self.assertIn("--prompt", command)
        self.assertIn("--width", command)
        self.assertEqual(command[command.index("--width") + 1], "1344")
        self.assertEqual(command[command.index("--height") + 1], "768")
        self.assertEqual(kind, "image")
        self.assertEqual(params["modelProfile"], "anima-base")

    def test_builds_image_edit_command_with_selected_image(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = self.service(tmpdir)
            image = self.media_file(tmpdir)
            out_dir = service.output_dir("run")
            with patch.object(service, "executable", return_value="comfy-imagegen"):
                command, _cwd, kind, _params = service.build_command(
                    self.request(imageMode="edit", modelProfile="qwen-edit2511"),
                    "change it",
                    out_dir,
                    {"image": [image], "video": [], "audio": []},
                )

        self.assertEqual(command[:2], ["comfy-imagegen", "edit"])
        self.assertEqual(command[command.index("--input") + 1], str(image))
        self.assertEqual(kind, "image")

    def test_builds_image_upscale_command_without_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = self.service(tmpdir)
            image = self.media_file(tmpdir)
            out_dir = service.output_dir("run")
            with patch.object(service, "executable", return_value="comfy-imagegen"):
                command, _cwd, kind, _params = service.build_command(
                    self.request(imageMode="upscale", modelProfile=""),
                    "upscale",
                    out_dir,
                    {"image": [image], "video": [], "audio": []},
                )

        self.assertEqual(command[:2], ["comfy-imagegen", "upscale"])
        self.assertNotIn("--prompt", command)
        self.assertEqual(command[command.index("--input") + 1], str(image))
        self.assertEqual(kind, "image")

    def test_builds_video_i2v_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = self.service(tmpdir)
            image = self.media_file(tmpdir)
            out_dir = service.output_dir("run")
            with patch.object(service, "executable", return_value="comfy-videogen"):
                command, _cwd, kind, params = service.build_command(
                    self.request(tool="video", videoMode="i2v", modelProfile="ltx23-10eros", aspectRatio="16:9", resolution="480p", duration=5),
                    "animate",
                    out_dir,
                    {"image": [image], "video": [], "audio": []},
                )

        self.assertEqual(command[:2], ["comfy-videogen", "i2v"])
        self.assertEqual(command[command.index("--input") + 1], str(image))
        self.assertEqual(command[command.index("--width") + 1], "848")
        self.assertEqual(command[command.index("--height") + 1], "480")
        self.assertEqual(command[command.index("--length") + 1], "120")
        self.assertEqual(kind, "video")
        self.assertEqual(params["modelProfile"], "ltx23-10eros")

    def test_builds_wan_flf_command_with_one_image_as_first_and_last(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = self.service(tmpdir)
            image = self.media_file(tmpdir)
            out_dir = service.output_dir("run")
            with patch.object(service, "executable", return_value="comfy-videogen"):
                command, _cwd, kind, _params = service.build_command(
                    self.request(tool="video", videoMode="wan22-flf2v", modelProfile="wan22-i2v", aspectRatio="9:16", resolution="360p", duration=4),
                    "animate",
                    out_dir,
                    {"image": [image], "video": [], "audio": []},
                )

        self.assertEqual(command[:2], ["comfy-videogen", "wan22-flf2v"])
        self.assertEqual(command[command.index("--first") + 1], str(image))
        self.assertEqual(command[command.index("--last") + 1], str(image))
        self.assertEqual(command[command.index("--fps") + 1], "16")
        self.assertEqual(command[command.index("--length") + 1], "65")
        self.assertEqual(kind, "video")

    def test_rejects_preview_only_media(self) -> None:
        payload = self.request(
            imageMode="edit",
            selectedCardSnapshots=[{"mediaAssets": [{"kind": "image", "dataUrl": "data:image/png;base64,aGVsbG8="}]}],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            service = self.service(tmpdir)
            with self.assertRaisesRegex(ComfyGenerationError, "preview-only media"):
                service.selected_media(payload)

    def test_rejects_missing_required_image_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = self.service(tmpdir)
            with self.assertRaisesRegex(ComfyGenerationError, "requires one selected"):
                service.build_command(
                    self.request(imageMode="edit", modelProfile="qwen-edit2511"),
                    "edit",
                    service.output_dir("run"),
                    {"image": [], "video": [], "audio": []},
                )

    def test_validates_cli_json_and_packages_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.object(card_packager, "ARTIFACTS_ROOT", Path(tmpdir)):
            service = self.service(tmpdir)
            output = Path(tmpdir) / "generations" / "comfy" / "run" / "outputs" / "image.png"
            output.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (256, 256), "black").save(output)
            payload = self.request()

            with patch.object(service, "executable", return_value="comfy-imagegen"), patch(
                "app.services.comfy_generation.subprocess.run",
                return_value=self.completed_process(json.dumps({"ok": True, "kind": "image", "artifacts": [str(output)]})),
            ):
                response = service.generate(payload)

        self.assertEqual(len(response.cards), 1)
        self.assertEqual(response.cards[0].source_skill_id, "comfy-direct")
        self.assertEqual(response.cards[0].metadata.kind, "image")

    def test_rejects_invalid_cli_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = self.service(tmpdir)
            with patch(
                "app.services.comfy_generation.subprocess.run",
                return_value=self.completed_process("not-json"),
            ):
                with self.assertRaisesRegex(ComfyGenerationError, "valid JSON"):
                    service.run_command(["comfy-imagegen"], Path(tmpdir))

    def test_rejects_artifact_outside_loki_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as outside:
            external = Path(outside) / "image.png"
            external.write_bytes(b"png")
            service = self.service(tmpdir)
            with self.assertRaisesRegex(ComfyGenerationError, "inside Loki artifacts root"):
                service.validated_raw_result({"artifacts": [str(external)]}, expected_kind="image", prompt="prompt")


if __name__ == "__main__":
    unittest.main()
