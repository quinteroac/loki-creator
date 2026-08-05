from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.models import HailuoVideoGenerationRequest
from app.services import card_packager
from app.services.hailuo_video import HailuoVideoGenerationError, HailuoVideoGenerationService


FIRST_IMAGE_DATA_URL = "data:image/png;base64,Zmlyc3Q="
LAST_IMAGE_DATA_URL = "data:image/png;base64,bGFzdA=="


class HailuoVideoGenerationServiceTest(unittest.TestCase):
    def service(self, root: Path) -> HailuoVideoGenerationService:
        return HailuoVideoGenerationService(root, poll_interval_seconds=0.01, poll_timeout_seconds=1)

    def request(self, **overrides: object) -> HailuoVideoGenerationRequest:
        data = {
            "prompt": "A paper bird takes flight over a miniature city",
            "aspectRatio": "16:9",
            "duration": 5,
            "selectedCardSnapshots": [],
            "attachments": [],
            "context": {},
        }
        data.update(overrides)
        return HailuoVideoGenerationRequest.model_validate(data)

    def test_build_request_supports_text_to_video(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            body = self.service(Path(tmpdir)).build_request_body(self.request(), "exact prompt")

        self.assertEqual(body, {
            "model": "minimax/hailuo-3",
            "prompt": "exact prompt",
            "resolution": "2K",
            "aspect_ratio": "16:9",
            "duration": 5,
            "generate_audio": True,
        })

    def test_build_request_maps_two_selected_images_to_first_and_last_frames(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            imports = root / "imports"
            imports.mkdir()
            (imports / "first.png").write_bytes(b"first")
            (imports / "last.png").write_bytes(b"last")
            payload = self.request(selectedCardSnapshots=[
                {"mediaAssets": [{"kind": "image", "src": "/api/artifacts/imports/first.png"}]},
                {"mediaAssets": [{"kind": "image", "src": "/api/artifacts/imports/last.png"}]},
            ])
            body = self.service(root).build_request_body(payload, payload.prompt)

        self.assertEqual(body["frame_images"], [
            {"type": "image_url", "image_url": {"url": FIRST_IMAGE_DATA_URL}, "frame_type": "first_frame"},
            {"type": "image_url", "image_url": {"url": LAST_IMAGE_DATA_URL}, "frame_type": "last_frame"},
        ])

    def test_local_media_references_do_not_duplicate_snapshot_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            image = root / "imports" / "first.png"
            image.parent.mkdir()
            image.write_bytes(b"first")
            payload = self.request(
                context={"localMediaReferences": [{"kind": "image", "path": str(image)}]},
                selectedCardSnapshots=[{"mediaAssets": [{"kind": "image", "src": "/api/artifacts/imports/first.png"}]}],
            )
            body = self.service(root).build_request_body(payload, payload.prompt)

        self.assertEqual(len(body["frame_images"]), 1)
        self.assertEqual(body["frame_images"][0]["frame_type"], "first_frame")

    def test_generate_polls_downloads_and_packages_hailuo_card(self) -> None:
        calls: list[tuple[str, str, dict | None]] = []

        def fake_request_json(self: HailuoVideoGenerationService, method: str, path_or_url: str, body: dict | None = None) -> dict:
            calls.append((method, path_or_url, body))
            if method == "POST":
                return {"id": "job-h3", "polling_url": "/api/v1/videos/job-h3", "status": "pending"}
            return {
                "id": "job-h3",
                "generation_id": "gen-h3",
                "status": "completed",
                "unsigned_urls": ["https://example.test/h3.mp4"],
                "usage": {"cost": 0.65},
            }

        def fake_download(self: HailuoVideoGenerationService, url: str, destination: Path) -> tuple[Path, str]:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"mp4")
            return destination, "video/mp4"

        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}), patch.object(
            card_packager,
            "ARTIFACTS_ROOT",
            Path(tmpdir),
        ), patch.object(
            HailuoVideoGenerationService,
            "request_json",
            fake_request_json,
        ), patch.object(
            HailuoVideoGenerationService,
            "download_video",
            fake_download,
        ):
            response = self.service(Path(tmpdir)).generate(self.request())

        self.assertEqual(calls[0][2]["model"], "minimax/hailuo-3")
        self.assertEqual(len(response.cards), 1)
        card = response.cards[0]
        self.assertEqual(card.source_skill_id, "openrouter-hailuo-direct")
        self.assertEqual(card.metadata.resolution, "2K")
        self.assertEqual(card.metadata.artifact_url.startswith("/api/artifacts/generations/hailuo-video/"), True)

    def test_generate_rejects_blank_prompt_before_api_call(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            HailuoVideoGenerationService,
            "request_json",
            side_effect=AssertionError("API should not be called"),
        ):
            with self.assertRaisesRegex(HailuoVideoGenerationError, "requires a prompt"):
                self.service(Path(tmpdir)).generate(self.request(prompt=" "))


if __name__ == "__main__":
    unittest.main()
