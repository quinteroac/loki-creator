from __future__ import annotations

import base64
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parent))

import split_audio


HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def run(command: list[str]) -> None:
    process = subprocess.run(command, text=True, capture_output=True, check=False)
    if process.returncode != 0:
        raise AssertionError(process.stderr or process.stdout)


def create_audio(path: Path, *, duration: float = 8.2, frequency: int = 440) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={frequency}:sample_rate=48000:d={duration}",
            "-ac",
            "2",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            str(path),
        ]
    )


class SplitAudioSelectionTest(unittest.TestCase):
    def test_materialize_selected_audio_preserves_order_and_uses_metadata_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifact_a = root / "imports" / "a.m4a"
            artifact_b = root / "imports" / "b.m4a"
            artifact_a.parent.mkdir(parents=True)
            artifact_a.write_bytes(b"a")
            artifact_b.write_bytes(b"b")

            payload = {
                "selectedCardSnapshots": [
                    {
                        "name": "image",
                        "mediaAssets": [{"kind": "image", "src": "/api/artifacts/imports/ignored.png"}],
                    },
                    {
                        "name": "metadata audio",
                        "mediaAssets": [{"kind": "source", "mimeType": "video/mp4", "src": "/api/artifacts/imports/ignored.mp4"}],
                        "metadata": {"kind": "audio", "artifactUrl": "/api/artifacts/imports/b.m4a"},
                    },
                    {
                        "name": "later audio",
                        "mediaAssets": [{"kind": "audio", "src": "/api/artifacts/imports/a.m4a"}],
                    },
                ]
            }

            with patch.dict(os.environ, {"LOKI_ARTIFACTS_ROOT": str(root)}):
                audio = split_audio.materialize_selected_audio(payload, root / "inputs")

        self.assertEqual(audio, artifact_b)

    def test_materialize_selected_audio_accepts_data_url_audio(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_url = f"data:audio/wav;base64,{base64.b64encode(b'audio').decode('ascii')}"
            payload = {
                "selectedCardSnapshots": [
                    {
                        "name": "inline audio",
                        "mediaAssets": [{"kind": "audio", "dataUrl": data_url}],
                    },
                ]
            }

            with patch.dict(os.environ, {"LOKI_ARTIFACTS_ROOT": str(root)}):
                audio = split_audio.materialize_selected_audio(payload, root / "inputs")
                audio_bytes = audio.read_bytes() if audio is not None else b""

        self.assertIsNotNone(audio)
        self.assertEqual(audio_bytes, b"audio")

    def test_split_selected_audio_requires_audio(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(os.environ, {"LOKI_ARTIFACTS_ROOT": tmpdir}):
            with self.assertRaisesRegex(RuntimeError, "requires one selected audio card"):
                split_audio.split_selected_audio(
                    {
                        "runId": "skill_run_test",
                        "skillId": "ffmpeg-audio-split",
                        "params": {"clipDurationSeconds": "5"},
                        "selectedCardSnapshots": [],
                    }
                )

    def test_parse_clip_duration_requires_video_duration_presets(self) -> None:
        self.assertEqual(split_audio.parse_clip_duration({"clipDurationSeconds": "10"}), 10)
        with self.assertRaisesRegex(RuntimeError, "3, 5, 7, 10, 15"):
            split_audio.parse_clip_duration({"clipDurationSeconds": "4"})


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg and ffprobe are required")
class SplitAudioFfmpegTest(unittest.TestCase):
    def payload_for(self, root: Path, run_id: str, audio: Path, duration: str = "3") -> dict:
        return {
            "runId": run_id,
            "skillId": "ffmpeg-audio-split",
            "prompt": f"split into {duration}s clips",
            "params": {"clipDurationSeconds": duration, "title": "Segment"},
            "selectedCardSnapshots": [
                {
                    "name": audio.stem,
                    "mediaAssets": [{"kind": "audio", "src": f"/api/artifacts/{audio.relative_to(root).as_posix()}"}],
                }
            ],
        }

    def test_split_produces_multiple_audio_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(os.environ, {"LOKI_ARTIFACTS_ROOT": tmpdir}):
            root = Path(tmpdir)
            source = root / "imports" / "tone.m4a"
            create_audio(source, duration=8.2)

            result = split_audio.split_selected_audio(self.payload_for(root, "skill_run_split", source, "3"))
            artifacts = result["artifacts"]

            self.assertEqual(len(artifacts), 3)
            for index, artifact in enumerate(artifacts, start=1):
                output = Path(artifact["path"])
                self.assertTrue(output.is_file())
                self.assertEqual(artifact["kind"], "audio")
                self.assertEqual(artifact["mimeType"], "audio/mp4")
                self.assertEqual(artifact["metadata"]["clipIndex"], index)
                info = split_audio.audio_info(output)
                self.assertGreater(info["duration"], 0.5)
                self.assertEqual(info["channels"], 2)

    def test_short_audio_produces_one_partial_clip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(os.environ, {"LOKI_ARTIFACTS_ROOT": tmpdir}):
            root = Path(tmpdir)
            source = root / "imports" / "short.m4a"
            create_audio(source, duration=1.4)

            result = split_audio.split_selected_audio(self.payload_for(root, "skill_run_short", source, "5"))

            self.assertEqual(len(result["artifacts"]), 1)
            metadata = result["artifacts"][0]["metadata"]
            self.assertLess(metadata["endSeconds"], 5)


if __name__ == "__main__":
    unittest.main()
