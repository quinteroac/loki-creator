from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app.models import GeminiImageGenerationRequest
from app.services import card_packager
from app.services.gemini_image import GeminiImageGenerationError, GeminiImageGenerationService


class GeminiImageGenerationServiceTest(unittest.TestCase):
    def image_request(self, **overrides: object) -> GeminiImageGenerationRequest:
        data = {
            "prompt": "make a cinematic cat portrait",
            "resolution": "1024x1024",
            "model": "Gemini 3.5 Flash (Medium)",
            "selectedCardSnapshots": [],
            "attachments": [],
        }
        data.update(overrides)
        return GeminiImageGenerationRequest.model_validate(data)

    def completed_process(self, stdout: str, *, returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=["agy"], returncode=returncode, stdout=stdout, stderr=stderr)

    def test_image_generation_packages_valid_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            card_packager,
            "ARTIFACTS_ROOT",
            Path(tmpdir),
        ):
            output = Path(tmpdir) / "generations" / "gemini-image" / "generation" / "image.png"
            output.parent.mkdir(parents=True)
            Image.new("RGB", (1024, 1024), "red").save(output)
            service = GeminiImageGenerationService(Path(tmpdir))

            with patch.object(
                service,
                "invoke_agy",
                return_value={
                    "images": [
                        {
                            "title": "Gemini image",
                            "prompt": "make a cinematic cat portrait",
                            "imagePath": str(output),
                            "mimeType": "image/png",
                        }
                    ],
                    "diagnostics": [],
                },
            ) as invoke_agy:
                response = service.generate(self.image_request())

        invoke_agy.assert_called_once()
        self.assertEqual(len(response.cards), 1)
        self.assertEqual(response.cards[0].source_skill_id, "gemini-image-direct")
        self.assertEqual(response.cards[0].metadata.kind, "image")

    def test_invoke_agy_command_contains_model_add_dir_timeout_and_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "generations" / "gemini-image" / "generation" / "image.png"
            output.parent.mkdir(parents=True)
            output.write_bytes(b"png")
            service = GeminiImageGenerationService(Path(tmpdir))
            calls: list[dict[str, object]] = []

            def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                calls.append({"command": command, **kwargs})
                return self.completed_process(
                    json.dumps(
                        {
                            "images": [
                                {
                                    "title": "Gemini image",
                                    "prompt": "prompt",
                                    "imagePath": str(output),
                                    "mimeType": "image/png",
                                }
                            ],
                            "diagnostics": [],
                        }
                    )
                )

            with patch.object(service, "resolve_agy_bin", return_value="agy"), patch(
                "app.services.gemini_image.subprocess.run",
                side_effect=fake_run,
            ):
                result = service.invoke_agy(
                    "prompt",
                    {"resolution": "1024x1024", "model": "Gemini 3.5 Flash (Medium)"},
                    output.parent,
                    [],
                )

        command = calls[0]["command"]
        self.assertEqual(result["images"][0]["title"], "Gemini image")
        self.assertIn("--model", command)
        self.assertIn("Gemini 3.5 Flash (Medium)", command)
        self.assertIn("--add-dir", command)
        self.assertIn("--print-timeout", command)
        self.assertIn("-p", command)
        self.assertIn("final response must end with exactly one valid JSON object", command[command.index("-p") + 1])

    def test_rejects_preview_only_image_media(self) -> None:
        payload = self.image_request(
            selectedCardSnapshots=[
                {
                    "mediaAssets": [
                        {
                            "kind": "image",
                            "dataUrl": "data:image/png;base64,aGVsbG8=",
                        }
                    ]
                }
            ]
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            service = GeminiImageGenerationService(Path(tmpdir))
            with patch.object(service, "invoke_agy", side_effect=AssertionError("agy should not run")):
                with self.assertRaisesRegex(GeminiImageGenerationError, "preview-only media is not executable"):
                    service.generate(payload)

    def test_rejects_invalid_json_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = GeminiImageGenerationService(Path(tmpdir))
            with patch.object(service, "resolve_agy_bin", return_value="agy"), patch(
                "app.services.gemini_image.subprocess.run",
                return_value=self.completed_process("not json"),
            ):
                with self.assertRaisesRegex(GeminiImageGenerationError, "final valid JSON object"):
                    service.invoke_agy("prompt", {"resolution": "1024x1024", "model": "Gemini 3.5 Flash (Medium)"}, Path(tmpdir), [])

    def test_parse_agy_stdout_accepts_progress_before_final_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = GeminiImageGenerationService(Path(tmpdir))
            parsed = service.parse_agy_stdout(
                'I am waiting for the image task to finish.\n{"images":[{"title":"Image","imagePath":"/tmp/image.png","mimeType":"image/png"}],"diagnostics":[]}\n'
            )

        self.assertEqual(parsed["images"][0]["title"], "Image")

    def test_parse_agy_stdout_rejects_trailing_text_after_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = GeminiImageGenerationService(Path(tmpdir))
            with self.assertRaisesRegex(GeminiImageGenerationError, "final valid JSON object"):
                service.parse_agy_stdout(
                    '{"images":[{"title":"Image","imagePath":"/tmp/image.png","mimeType":"image/png"}],"diagnostics":[]}\nDone.'
                )

    def test_parse_agy_stdout_rejects_multiple_final_json_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = GeminiImageGenerationService(Path(tmpdir))
            with self.assertRaisesRegex(GeminiImageGenerationError, "multiple possible"):
                service.parse_agy_stdout(
                    'Progress {"ignored": true} {"images":[{"title":"Image","imagePath":"/tmp/image.png","mimeType":"image/png"}],"diagnostics":[]}'
                )

    def test_rejects_missing_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = GeminiImageGenerationService(Path(tmpdir))
            with self.assertRaisesRegex(GeminiImageGenerationError, "does not exist"):
                service.validated_raw_result(
                    {
                        "images": [
                            {
                                "imagePath": str(Path(tmpdir) / "missing.png"),
                                "mimeType": "image/png",
                            }
                        ]
                    }
                )

    def test_rejects_artifact_outside_loki_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as outside:
            external = Path(outside) / "image.png"
            external.write_bytes(b"png")
            service = GeminiImageGenerationService(Path(tmpdir))
            with self.assertRaisesRegex(GeminiImageGenerationError, "inside Loki artifacts root"):
                service.validated_raw_result(
                    {
                        "images": [
                            {
                                "imagePath": str(external),
                                "mimeType": "image/png",
                            }
                        ]
                    }
                )


if __name__ == "__main__":
    unittest.main()
