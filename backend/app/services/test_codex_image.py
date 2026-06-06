from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app.models import CodexImageGenerationRequest
from app.services import card_packager
from app.services.codex_image import CodexImageGenerationError, CodexImageGenerationService


class CodexImageGenerationServiceTest(unittest.TestCase):
    def image_request(self, **overrides: object) -> CodexImageGenerationRequest:
        data = {
            "prompt": "turn the sweater black and red",
            "resolution": "1024x1536",
            "selectedCardSnapshots": [],
            "attachments": [],
        }
        data.update(overrides)
        return CodexImageGenerationRequest.model_validate(data)

    def completed_process(self, stdout: str, *, returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=["python"], returncode=returncode, stdout=stdout, stderr=stderr)

    def test_image_generation_packages_valid_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            card_packager,
            "ARTIFACTS_ROOT",
            Path(tmpdir),
        ):
            output = Path(tmpdir) / "skills" / "imagegen" / "generation" / "outputs" / "image.png"
            output.parent.mkdir(parents=True)
            Image.new("RGB", (1024, 1536), "black").save(output)
            service = CodexImageGenerationService(Path(tmpdir))

            with patch.object(
                service,
                "invoke_action",
                return_value={
                    "artifacts": [
                        {
                            "path": str(output),
                            "kind": "image",
                            "mimeType": "image/png",
                            "title": "Codex image",
                            "prompt": "turn the sweater black and red",
                        }
                    ],
                    "diagnostics": [],
                },
            ) as invoke_action:
                response = service.generate(self.image_request())

        invoke_action.assert_called_once()
        self.assertEqual(len(response.cards), 1)
        self.assertEqual(response.cards[0].source_skill_id, "codex-image-direct")
        self.assertEqual(response.cards[0].metadata.kind, "image")

    def test_invoke_action_passes_selected_snapshots_to_imagegen_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "skills" / "imagegen" / "generation" / "outputs" / "image.png"
            output.parent.mkdir(parents=True)
            output.write_bytes(b"png")
            captured_payload: dict = {}

            def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
                captured_payload.update(json.loads(str(kwargs["input"])))
                return self.completed_process(
                    json.dumps(
                        {
                            "artifacts": [
                                {
                                    "path": str(output),
                                    "kind": "image",
                                    "mimeType": "image/png",
                                    "title": "Codex image",
                                    "prompt": "edit",
                                }
                            ],
                            "diagnostics": [],
                        }
                    )
                )

            service = CodexImageGenerationService(Path(tmpdir))
            snapshot = {"mediaAssets": [{"kind": "image", "src": "/api/artifacts/imports/source.png"}]}
            with patch("app.services.codex_image.subprocess.run", side_effect=fake_run):
                result = service.invoke_action("edit", {"resolution": "1024x1024"}, [snapshot], [], {})

        self.assertEqual(result["artifacts"][0]["kind"], "image")
        self.assertEqual(captured_payload["skillId"], "imagegen")
        self.assertEqual(captured_payload["selectedCardSnapshots"], [snapshot])
        self.assertEqual(captured_payload["context"]["selectedCardSnapshots"], [snapshot])

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
            service = CodexImageGenerationService(Path(tmpdir))
            with patch.object(service, "invoke_action", side_effect=AssertionError("action should not run")):
                with self.assertRaisesRegex(CodexImageGenerationError, "preview-only media is not executable"):
                    service.generate(payload)

    def test_rejects_invalid_action_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = CodexImageGenerationService(Path(tmpdir))
            with patch(
                "app.services.codex_image.subprocess.run",
                return_value=self.completed_process("not json"),
            ):
                with self.assertRaisesRegex(CodexImageGenerationError, "valid JSON"):
                    service.invoke_action("prompt", {"resolution": "1024x1024"}, [], [], {})

    def test_rejects_missing_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = CodexImageGenerationService(Path(tmpdir))
            with self.assertRaisesRegex(CodexImageGenerationError, "does not exist"):
                service.validated_raw_result(
                    {
                        "artifacts": [
                            {
                                "path": str(Path(tmpdir) / "missing.png"),
                                "kind": "image",
                                "mimeType": "image/png",
                            }
                        ]
                    }
                )

    def test_rejects_artifact_outside_loki_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as outside:
            external = Path(outside) / "image.png"
            external.write_bytes(b"png")
            service = CodexImageGenerationService(Path(tmpdir))
            with self.assertRaisesRegex(CodexImageGenerationError, "inside Loki artifacts root"):
                service.validated_raw_result(
                    {
                        "artifacts": [
                            {
                                "path": str(external),
                                "kind": "image",
                                "mimeType": "image/png",
                            }
                        ]
                    }
                )


if __name__ == "__main__":
    unittest.main()
