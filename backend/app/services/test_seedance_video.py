from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.models import SeedanceVideoGenerationRequest
from app.services import card_packager
from app.services.seedance_video import SeedanceVideoGenerationError, SeedanceVideoGenerationService


IMAGE_DATA_URL = "data:image/png;base64,aGVsbG8="
AUDIO_DATA_URL = "data:audio/mpeg;base64,YXVkaW8="


class SeedanceVideoGenerationServiceTest(unittest.TestCase):
    def service(self, root: Path) -> SeedanceVideoGenerationService:
        return SeedanceVideoGenerationService(root, poll_interval_seconds=0.01, poll_timeout_seconds=1)

    def request(self, **overrides: object) -> SeedanceVideoGenerationRequest:
        data = {
            "prompt": "A dancer spins through neon rain",
            "aspectRatio": "16:9",
            "duration": 5,
            "selectedCardSnapshots": [],
            "attachments": [],
        }
        data.update(overrides)
        return SeedanceVideoGenerationRequest.model_validate(data)

    def test_build_request_uses_exact_prompt_and_seedance_constraints(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            image = Path(tmpdir) / "imports" / "image.png"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"hello")
            payload = self.request(
                prompt="exact raw prompt",
                selectedCardSnapshots=[{"mediaAssets": [{"kind": "image", "src": "/api/artifacts/imports/image.png"}]}],
            )
            body = self.service(Path(tmpdir)).build_request_body(payload, payload.prompt)

        self.assertEqual(body["model"], "bytedance/seedance-2.0-fast")
        self.assertEqual(body["prompt"], "exact raw prompt")
        self.assertEqual(body["resolution"], "480p")
        self.assertEqual(body["aspect_ratio"], "16:9")
        self.assertEqual(body["duration"], 5)
        self.assertEqual(body["input_references"][0], {"type": "image_url", "image_url": {"url": IMAGE_DATA_URL}})

    def test_build_request_includes_optional_audio_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            image = Path(tmpdir) / "imports" / "image.png"
            audio = Path(tmpdir) / "imports" / "audio.mp3"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"hello")
            audio.write_bytes(b"audio")
            payload = self.request(
                selectedCardSnapshots=[
                    {"mediaAssets": [{"kind": "image", "src": "/api/artifacts/imports/image.png"}]},
                    {"mediaAssets": [{"kind": "audio", "src": "/api/artifacts/imports/audio.mp3"}]},
                ],
            )
            body = self.service(Path(tmpdir)).build_request_body(payload, payload.prompt)

        self.assertEqual(body["input_references"][1], {"type": "audio_url", "audio_url": {"url": AUDIO_DATA_URL}})

    def test_build_request_requires_image_reference(self) -> None:
        payload = self.request(selectedCardSnapshots=[], attachments=[])
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaisesRegex(SeedanceVideoGenerationError, "requires one selected or attached image"):
                self.service(Path(tmpdir)).build_request_body(payload, payload.prompt)

    def test_generate_rejects_blank_prompt_before_api_call(self) -> None:
        payload = self.request(prompt=" ")
        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            SeedanceVideoGenerationService,
            "request_json",
            side_effect=AssertionError("API should not be called"),
        ):
            with self.assertRaisesRegex(SeedanceVideoGenerationError, "requires a prompt"):
                self.service(Path(tmpdir)).generate(payload)

    def test_generate_polls_downloads_and_packages_video_card(self) -> None:
        calls: list[tuple[str, str, dict | None]] = []

        def fake_request_json(self: SeedanceVideoGenerationService, method: str, path_or_url: str, body: dict | None = None) -> dict:
            calls.append((method, path_or_url, body))
            if method == "POST":
                return {"id": "job-1", "polling_url": "/api/v1/videos/job-1", "status": "pending"}
            return {
                "id": "job-1",
                "generation_id": "gen-1",
                "status": "completed",
                "unsigned_urls": ["https://example.test/video.mp4"],
                "usage": {"cost": 0.12},
            }

        def fake_download(self: SeedanceVideoGenerationService, url: str, destination: Path) -> tuple[Path, str]:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"mp4")
            return destination, "video/mp4"

        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}), patch.object(
            card_packager,
            "ARTIFACTS_ROOT",
            Path(tmpdir),
        ), patch.object(
            SeedanceVideoGenerationService,
            "request_json",
            fake_request_json,
        ), patch.object(
            SeedanceVideoGenerationService,
            "download_video",
            fake_download,
        ):
            image = Path(tmpdir) / "imports" / "image.png"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"hello")
            response = self.service(Path(tmpdir)).generate(
                self.request(selectedCardSnapshots=[{"mediaAssets": [{"kind": "image", "src": "/api/artifacts/imports/image.png"}]}])
            )

        self.assertEqual(calls[0][0], "POST")
        self.assertEqual(calls[0][1], "/api/v1/videos")
        self.assertEqual(calls[0][2]["prompt"], "A dancer spins through neon rain")
        self.assertEqual(calls[1][0], "GET")
        self.assertEqual(len(response.cards), 1)
        card = response.cards[0]
        self.assertEqual(card.prompt, "A dancer spins through neon rain")
        self.assertEqual(card.source_skill_id, "openrouter-seedance-direct")
        self.assertEqual(card.metadata.kind, "video")
        self.assertEqual(card.metadata.artifact_url.startswith("/api/artifacts/generations/seedance-video/"), True)

    def test_poll_surfaces_terminal_failure(self) -> None:
        def fake_request_json(self: SeedanceVideoGenerationService, method: str, path_or_url: str, body: dict | None = None) -> dict:
            return {"id": "job-1", "status": "failed", "error": "Content policy violation"}

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            SeedanceVideoGenerationService,
            "request_json",
            fake_request_json,
        ):
            with self.assertRaisesRegex(SeedanceVideoGenerationError, "Content policy violation"):
                self.service(Path(tmpdir)).poll_video("job-1", "/api/v1/videos/job-1")


if __name__ == "__main__":
    unittest.main()
