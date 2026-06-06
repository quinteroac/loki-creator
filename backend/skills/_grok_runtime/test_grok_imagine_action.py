from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import grok_imagine_action as action


IMAGE_DATA_URL = "data:image/png;base64,aGVsbG8="


class GrokImagineActionTest(unittest.TestCase):
    def test_imagine_image_uses_edit_endpoint_for_attached_local_image(self) -> None:
        calls: list[tuple[str, str, dict]] = []

        def fake_request_json(method: str, path: str, body: dict | None = None) -> dict:
            calls.append((method, path, body or {}))
            return {"data": [{"b64_json": "aGVsbG8="}]}

        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "imports" / "input.png"
            image_path.parent.mkdir(parents=True)
            image_path.write_bytes(b"hello")
            payload = {
                "skillId": "grok-imagine-image",
                "runId": "test-image-edit",
                "prompt": "turn this into a watercolor",
                "attachments": [
                    {
                        "kind": "image",
                        "artifactUrl": "/api/artifacts/imports/input.png",
                        "omitted": False,
                    }
                ],
            }

            with patch.dict(os.environ, {"LOKI_ARTIFACTS_ROOT": tmpdir}), patch(
            "grok_imagine_action.request_json",
            side_effect=fake_request_json,
            ):
                result = action.imagine_image(payload)

        self.assertEqual(calls[0][1], "/v1/images/edits")
        self.assertEqual(calls[0][2]["image"], {"url": IMAGE_DATA_URL, "type": "image_url"})
        self.assertEqual(result["artifacts"][0]["metadata"]["source"], "image-edit")

    def test_imagine_image_uses_multiple_selected_card_images(self) -> None:
        calls: list[tuple[str, str, dict]] = []

        def fake_request_json(method: str, path: str, body: dict | None = None) -> dict:
            calls.append((method, path, body or {}))
            return {"data": [{"b64_json": "aGVsbG8="}]}

        with tempfile.TemporaryDirectory() as tmpdir:
            first = Path(tmpdir) / "imports" / "first.png"
            second = Path(tmpdir) / "imports" / "second.png"
            first.parent.mkdir(parents=True)
            first.write_bytes(b"hello")
            second.write_bytes(b"world")
            payload = {
                "skillId": "grok-imagine-image",
                "runId": "test-multi-image-edit",
                "prompt": "combine these references",
                "selectedCardSnapshots": [
                    {"mediaAssets": [{"kind": "image", "src": "/api/artifacts/imports/first.png"}]},
                    {"metadata": {"kind": "image", "artifactUrl": "/api/artifacts/imports/second.png"}},
                ],
            }

            with patch.dict(os.environ, {"LOKI_ARTIFACTS_ROOT": tmpdir}), patch(
            "grok_imagine_action.request_json",
            side_effect=fake_request_json,
            ):
                action.imagine_image(payload)

        self.assertEqual(calls[0][1], "/v1/images/edits")
        self.assertEqual(
            calls[0][2]["images"],
            [
                {"url": IMAGE_DATA_URL, "type": "image_url"},
                {"url": "data:image/png;base64,d29ybGQ=", "type": "image_url"},
            ],
        )

    def test_imagine_video_uses_selected_image_input(self) -> None:
        calls: list[tuple[str, str, dict]] = []

        def fake_request_json(method: str, path: str, body: dict | None = None) -> dict:
            calls.append((method, path, body or {}))
            return {"request_id": "video-request-1"}

        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "imports" / "input.png"
            image_path.parent.mkdir(parents=True)
            image_path.write_bytes(b"hello")
            payload = {
                "skillId": "grok-imagine-video",
                "prompt": "animate the scene",
                "params": {"poll": False},
                "selectedCardSnapshots": [
                    {"mediaAssets": [{"kind": "image", "src": "/api/artifacts/imports/input.png"}]},
                ],
            }

            with patch.dict(os.environ, {"LOKI_ARTIFACTS_ROOT": tmpdir}), patch("grok_imagine_action.request_json", side_effect=fake_request_json):
                result = action.imagine_video(payload)

        self.assertEqual(calls[0][1], "/v1/videos/generations")
        self.assertEqual(calls[0][2]["image"], {"url": IMAGE_DATA_URL})
        self.assertEqual(result["metadata"]["status"], "pending")


if __name__ == "__main__":
    unittest.main()
