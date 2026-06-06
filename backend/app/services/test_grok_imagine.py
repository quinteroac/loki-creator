from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.models import GrokImageGenerationRequest, GrokVideoGenerationRequest
from app.services import card_packager
from app.services.grok_imagine import GrokImagineGenerationError, GrokImagineGenerationService


class GrokImagineGenerationServiceTest(unittest.TestCase):
    def image_request(self, **overrides: object) -> GrokImageGenerationRequest:
        data = {
            "prompt": "turn the sweater black and red",
            "aspectRatio": "9:16",
            "resolution": "1k",
            "selectedCardSnapshots": [],
            "attachments": [],
        }
        data.update(overrides)
        return GrokImageGenerationRequest.model_validate(data)

    def video_request(self, **overrides: object) -> GrokVideoGenerationRequest:
        data = {
            "prompt": "animate the selected image",
            "aspectRatio": "16:9",
            "resolution": "720p",
            "duration": 5,
            "selectedCardSnapshots": [],
            "attachments": [],
        }
        data.update(overrides)
        return GrokVideoGenerationRequest.model_validate(data)

    def test_image_generation_packages_valid_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            card_packager,
            "ARTIFACTS_ROOT",
            Path(tmpdir),
        ):
            output = Path(tmpdir) / "generations" / "grok" / "image.png"
            output.parent.mkdir(parents=True)
            output.write_bytes(b"png")
            service = GrokImagineGenerationService(Path(tmpdir))

            with patch.object(
                service,
                "invoke_runtime",
                return_value={
                    "artifacts": [
                        {
                            "path": str(output),
                            "kind": "image",
                            "mimeType": "image/png",
                            "title": "Grok image",
                            "prompt": "turn the sweater black and red",
                        }
                    ]
                },
            ) as invoke_runtime:
                response = service.generate_image(self.image_request())

        invoke_runtime.assert_called_once()
        self.assertEqual(len(response.cards), 1)
        self.assertEqual(response.cards[0].source_skill_id, "grok-imagine-image-direct")
        self.assertEqual(response.cards[0].metadata.kind, "image")

    def test_video_generation_packages_valid_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            card_packager,
            "ARTIFACTS_ROOT",
            Path(tmpdir),
        ):
            output = Path(tmpdir) / "generations" / "grok" / "video.mp4"
            output.parent.mkdir(parents=True)
            output.write_bytes(b"mp4")
            service = GrokImagineGenerationService(Path(tmpdir))

            with patch.object(
                service,
                "invoke_runtime",
                return_value={
                    "artifacts": [
                        {
                            "path": str(output),
                            "kind": "video",
                            "mimeType": "video/mp4",
                            "title": "Grok video",
                            "prompt": "animate the selected image",
                        }
                    ]
                },
            ):
                response = service.generate_video(self.video_request())

        self.assertEqual(len(response.cards), 1)
        self.assertEqual(response.cards[0].source_skill_id, "grok-imagine-video-direct")
        self.assertEqual(response.cards[0].metadata.kind, "video")

    def test_rejects_missing_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = GrokImagineGenerationService(Path(tmpdir))
            with self.assertRaisesRegex(GrokImagineGenerationError, "does not exist"):
                service.validated_raw_result(
                    {
                        "artifacts": [
                            {
                                "path": str(Path(tmpdir) / "missing.png"),
                                "kind": "image",
                                "mimeType": "image/png",
                            }
                        ]
                    },
                    expected_kind="image",
                )

    def test_rejects_artifact_outside_loki_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as outside:
            external = Path(outside) / "image.png"
            external.write_bytes(b"png")
            service = GrokImagineGenerationService(Path(tmpdir))
            with self.assertRaisesRegex(GrokImagineGenerationError, "inside Loki artifacts root"):
                service.validated_raw_result(
                    {
                        "artifacts": [
                            {
                                "path": str(external),
                                "kind": "image",
                                "mimeType": "image/png",
                            }
                        ]
                    },
                    expected_kind="image",
                )

    def test_rejects_wrong_artifact_kind(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "image.png"
            output.write_bytes(b"png")
            service = GrokImagineGenerationService(Path(tmpdir))
            with self.assertRaisesRegex(GrokImagineGenerationError, "kind must be video"):
                service.validated_raw_result(
                    {
                        "artifacts": [
                            {
                                "path": str(output),
                                "kind": "image",
                                "mimeType": "image/png",
                            }
                        ]
                    },
                    expected_kind="video",
                )

    def test_rejects_blank_prompt_before_runtime_call(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = GrokImagineGenerationService(Path(tmpdir))
            with patch.object(service, "invoke_runtime", side_effect=AssertionError("runtime should not run")):
                with self.assertRaisesRegex(GrokImagineGenerationError, "requires a prompt"):
                    service.generate_image(self.image_request(prompt=" "))

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
            service = GrokImagineGenerationService(Path(tmpdir))
            with patch.object(service, "invoke_runtime", side_effect=AssertionError("runtime should not run")):
                with self.assertRaisesRegex(GrokImagineGenerationError, "preview-only media is not executable"):
                    service.generate_image(payload)


if __name__ == "__main__":
    unittest.main()
