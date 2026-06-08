from __future__ import annotations

from dataclasses import dataclass
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app.models import CodexImageGenerationRequest
from app.services import card_packager
from app.services.codex_image import CodexImageGenerationError, CodexImageGenerationService


@dataclass
class FakeCodexPayload:
    message: str
    delta: str | None = None
    result: str = ""
    encrypted_content: str = ""
    item: dict[str, object] | None = None


@dataclass
class FakeCodexEvent:
    payload: FakeCodexPayload
    method: str | None = None


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

    def test_invoke_action_uses_sdk_response_and_passes_selected_snapshots_to_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "skills" / "imagegen" / "generation" / "outputs" / "image.png"
            output.parent.mkdir(parents=True)
            Image.new("RGB", (1024, 1024), "black").save(output)
            captured_prompt = ""
            captured_images: list[Path] = []

            def fake_sdk(prompt: str, _run_dir: Path, selected_images: list[Path]) -> str:
                nonlocal captured_prompt, captured_images
                captured_prompt = prompt
                captured_images = selected_images
                return json.dumps(
                    {
                        "images": [
                            {
                                "imagePath": str(output),
                                "mimeType": "image/png",
                                "title": "Codex image",
                                "prompt": "edit",
                                "width": 1024,
                                "height": 1024,
                            }
                        ],
                        "diagnostics": [],
                    }
                )

            service = CodexImageGenerationService(Path(tmpdir))
            source = Path(tmpdir) / "imports" / "source.png"
            source.parent.mkdir(parents=True)
            Image.new("RGB", (512, 512), "white").save(source)
            snapshot = {
                "displayTitle": "Layout",
                "mediaAssets": [{"kind": "image", "src": "/api/artifacts/imports/source.png"}],
                "structuredData": {
                    "compositionGuide": {
                        "version": 1,
                        "boxes": [{"id": "box1", "ideogramBbox": [0, 0, 1000, 1000]}],
                    }
                },
            }
            with patch.object(service, "run_codex_sdk", side_effect=fake_sdk):
                result = service.invoke_action("edit", {"resolution": "1024x1024"}, [snapshot], [], {})

        self.assertEqual(result["artifacts"][0]["kind"], "image")
        self.assertIn("Selected composition guides from bbox cards", captured_prompt)
        self.assertIn('"ideogramBbox": [', captured_prompt)
        self.assertEqual(captured_images, [source.resolve()])

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
            with patch.object(service, "run_codex_sdk", return_value="not json"):
                with self.assertRaisesRegex(CodexImageGenerationError, "valid JSON"):
                    service.invoke_action("prompt", {"resolution": "1024x1024"}, [], [], {})

    def test_codex_sdk_model_uses_account_default_when_env_is_unset(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LOKI_CODEX_SDK_MODEL", None)
            service = CodexImageGenerationService(Path(tmpdir))
            self.assertIsNone(service.codex_sdk_model())

    def test_codex_sdk_model_uses_explicit_env_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(os.environ, {"LOKI_CODEX_SDK_MODEL": " gpt-test "}, clear=False):
            service = CodexImageGenerationService(Path(tmpdir))
            self.assertEqual(service.codex_sdk_model(), "gpt-test")

    def test_codex_reasoning_summary_defaults_to_auto(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LOKI_CODEX_REASONING_SUMMARY", None)
            service = CodexImageGenerationService(Path(tmpdir))
            self.assertEqual(service.codex_reasoning_summary(), "auto")

    def test_codex_reasoning_summary_rejects_invalid_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(os.environ, {"LOKI_CODEX_REASONING_SUMMARY": "verbose"}):
            service = CodexImageGenerationService(Path(tmpdir))
            with self.assertRaisesRegex(CodexImageGenerationError, "LOKI_CODEX_REASONING_SUMMARY"):
                service.codex_reasoning_summary()

    def test_logged_codex_sdk_stream_writes_events_and_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = CodexImageGenerationService(Path(tmpdir))
            stream_path = Path(tmpdir) / "codex-sdk-events.jsonl"
            status_path = Path(tmpdir) / "codex-sdk-status.json"
            events = [FakeCodexEvent(FakeCodexPayload("started")), FakeCodexEvent(FakeCodexPayload("done"))]

            collected = list(service.logged_codex_sdk_stream(iter(events), stream_path, status_path, "turn_123"))

            self.assertEqual(collected, events)
            lines = stream_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 2)
            first = json.loads(lines[0])
            self.assertEqual(first["eventType"], "FakeCodexPayload")
            self.assertEqual(first["event"]["payload"]["message"], "started")
            status = json.loads(status_path.read_text(encoding="utf-8"))
            self.assertEqual(status["status"], "running")
            self.assertEqual(status["turnId"], "turn_123")
            self.assertEqual(status["eventCount"], 2)

    def test_logged_codex_sdk_stream_redacts_large_payloads_and_tracks_generated_images(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = CodexImageGenerationService(Path(tmpdir))
            stream_path = Path(tmpdir) / "codex-sdk-events.jsonl"
            status_path = Path(tmpdir) / "codex-sdk-status.json"
            generated_path = str(Path.home() / ".codex" / "generated_images" / "thread" / "image.png")
            events = [
                FakeCodexEvent(
                    FakeCodexPayload(
                        "image",
                        result="a" * 5000,
                        encrypted_content="b" * 5000,
                        item={
                            "id": "ig_1",
                            "type": "imageGeneration",
                            "status": "completed",
                            "saved_path": generated_path,
                            "revised_prompt": "final prompt",
                        },
                    )
                )
            ]

            list(service.logged_codex_sdk_stream(iter(events), stream_path, status_path, "turn_123"))

            record = json.loads(stream_path.read_text(encoding="utf-8").strip())
            payload = record["event"]["payload"]
            self.assertEqual(payload["result"]["redacted"], True)
            self.assertEqual(payload["encrypted_content"]["redacted"], True)
            self.assertEqual(record["sdkImageGeneration"]["savedPath"], generated_path)
            status = json.loads(status_path.read_text(encoding="utf-8"))
            self.assertEqual(status["statusDetail"], "image_generation_completed")

    def test_materializes_sdk_generated_image_reported_by_stream(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as codex_home:
            service = CodexImageGenerationService(Path(tmpdir))
            run_dir = Path(tmpdir) / "skills" / "imagegen" / "generation_sdk"
            source = Path(codex_home) / "generated_images" / "thread" / "image.png"
            source.parent.mkdir(parents=True)
            Image.new("RGB", (256, 256), "blue").save(source)
            run_dir.mkdir(parents=True)
            stream_record = {
                "sdkImageGeneration": {
                    "id": "ig_1",
                    "status": "completed",
                    "savedPath": str(source),
                    "revisedPrompt": "prompt",
                }
            }
            (run_dir / "codex-sdk-events.jsonl").write_text(json.dumps(stream_record) + "\n", encoding="utf-8")
            result = {
                "images": [
                    {
                        "imagePath": str(source),
                        "mimeType": "image/png",
                        "title": "Generated",
                        "prompt": "prompt",
                        "width": 256,
                        "height": 256,
                    }
                ],
                "diagnostics": [],
            }

            with patch.dict(os.environ, {"CODEX_HOME": codex_home}):
                materialized = service.materialize_sdk_generated_images(result, run_dir)

            output_path = Path(materialized["images"][0]["imagePath"])
            self.assertTrue(output_path.is_file())
            self.assertEqual(output_path.parent, run_dir / "outputs")
            self.assertEqual(service.verified_image_dimensions(output_path), (256, 256))

    def test_materializes_missing_loki_output_path_from_sdk_stream(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as codex_home:
            service = CodexImageGenerationService(Path(tmpdir))
            run_dir = Path(tmpdir) / "skills" / "imagegen" / "generation_sdk"
            source = Path(codex_home) / "generated_images" / "thread" / "image.png"
            source.parent.mkdir(parents=True)
            Image.new("RGB", (1024, 1536), "blue").save(source)
            declared_output = run_dir / "outputs" / "generated-image-cat-on-rooftop.png"
            run_dir.mkdir(parents=True)
            stream_record = {
                "sdkImageGeneration": {
                    "id": "ig_1",
                    "status": "generating",
                    "savedPath": str(source),
                    "revisedPrompt": "prompt",
                }
            }
            (run_dir / "codex-sdk-events.jsonl").write_text(json.dumps(stream_record) + "\n", encoding="utf-8")
            result = {
                "images": [
                    {
                        "imagePath": str(declared_output),
                        "mimeType": "image/png",
                        "title": "Generated image",
                        "prompt": "prompt",
                        "width": 1024,
                        "height": 1536,
                    }
                ],
                "diagnostics": [],
            }

            with patch.dict(os.environ, {"CODEX_HOME": codex_home}):
                materialized = service.materialize_sdk_generated_images(result, run_dir)

            output_path = Path(materialized["images"][0]["imagePath"])
            self.assertEqual(output_path, declared_output)
            self.assertTrue(output_path.is_file())
            self.assertEqual(service.verified_image_dimensions(output_path), (1024, 1536))

    def test_does_not_materialize_external_image_not_reported_by_stream(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as outside:
            service = CodexImageGenerationService(Path(tmpdir))
            run_dir = Path(tmpdir) / "skills" / "imagegen" / "generation_sdk"
            run_dir.mkdir(parents=True)
            external = Path(outside) / "image.png"
            Image.new("RGB", (128, 128), "black").save(external)
            result = {
                "images": [
                    {
                        "imagePath": str(external),
                        "mimeType": "image/png",
                        "title": "External",
                        "prompt": "prompt",
                        "width": 128,
                        "height": 128,
                    }
                ],
                "diagnostics": [],
            }

            materialized = service.materialize_sdk_generated_images(result, run_dir)

            self.assertEqual(materialized["images"][0]["imagePath"], str(external))

    def test_rejects_sdk_image_path_without_written_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = CodexImageGenerationService(Path(tmpdir))
            missing = Path(tmpdir) / "skills" / "imagegen" / "generation" / "outputs" / "missing.png"
            with patch.object(
                service,
                "run_codex_sdk",
                return_value=json.dumps(
                    {
                        "images": [
                            {
                                "imagePath": str(missing),
                                "mimeType": "image/png",
                                "title": "Missing",
                                "prompt": "prompt",
                                "width": 1024,
                                "height": 1024,
                            }
                        ],
                        "diagnostics": [],
                    }
                ),
            ):
                with self.assertRaisesRegex(CodexImageGenerationError, "no artifact was written"):
                    service.invoke_action("prompt", {"resolution": "1024x1024"}, [], [], {})

    def test_rejects_sdk_image_path_outside_loki_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as outside:
            service = CodexImageGenerationService(Path(tmpdir))
            external = Path(outside) / "image.png"
            Image.new("RGB", (128, 128), "black").save(external)
            with patch.object(
                service,
                "run_codex_sdk",
                return_value=json.dumps(
                    {
                        "images": [
                            {
                                "imagePath": str(external),
                                "mimeType": "image/png",
                                "title": "External",
                                "prompt": "prompt",
                                "width": 128,
                                "height": 128,
                            }
                        ],
                        "diagnostics": [],
                    }
                ),
            ):
                with self.assertRaisesRegex(CodexImageGenerationError, "inside the Loki artifacts directory"):
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
