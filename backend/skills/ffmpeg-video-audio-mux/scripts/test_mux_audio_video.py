from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parent))

import mux_audio_video


HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def run(command: list[str]) -> None:
    process = subprocess.run(command, text=True, capture_output=True, check=False)
    if process.returncode != 0:
        raise AssertionError(process.stderr or process.stdout)


def create_video(path: Path, *, audio: bool = True, color: str = "red", duration: float = 1.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c={color}:s=64x48:r=10:d={duration}",
    ]
    if audio:
        command.extend(
            [
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency=220:sample_rate=48000:d={duration}",
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
            ]
        )
    else:
        command.extend(["-map", "0:v:0"])
    command.extend(
        [
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(path),
        ]
    )
    run(command)


def create_audio(path: Path, *, duration: float = 1.0, frequency: int = 440) -> None:
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


class MuxAudioVideoSelectionTest(unittest.TestCase):
    def test_materialize_selected_media_uses_local_artifact_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            video = root / "imports" / "video.mp4"
            audio = root / "imports" / "audio.m4a"
            video.parent.mkdir(parents=True)
            video.write_bytes(b"video")
            audio.write_bytes(b"audio")
            payload = {
                "selectedCardSnapshots": [
                    {
                        "name": "video",
                        "metadata": {"kind": "video", "artifactUrl": "/api/artifacts/imports/video.mp4"},
                    },
                    {
                        "name": "audio",
                        "mediaAssets": [{"kind": "audio", "src": "/api/artifacts/imports/audio.m4a"}],
                    },
                ]
            }

            with patch.dict(os.environ, {"LOKI_ARTIFACTS_ROOT": str(root)}):
                resolved_video = mux_audio_video.materialize_selected_media(payload, root / "inputs", "video")
                resolved_audio = mux_audio_video.materialize_selected_media(payload, root / "inputs", "audio")

        self.assertEqual(resolved_video, video)
        self.assertEqual(resolved_audio, audio)

    def test_mux_requires_video_and_audio(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(os.environ, {"LOKI_ARTIFACTS_ROOT": tmpdir}):
            with self.assertRaisesRegex(RuntimeError, "requires one selected video card"):
                mux_audio_video.mux_selected_audio_video(
                    {
                        "runId": "skill_run_missing_video",
                        "skillId": "ffmpeg-video-audio-mux",
                        "selectedCardSnapshots": [],
                    }
                )

            video = Path(tmpdir) / "imports" / "video.mp4"
            video.parent.mkdir(parents=True)
            video.write_bytes(b"video")
            with self.assertRaisesRegex(RuntimeError, "requires one selected audio card"):
                mux_audio_video.mux_selected_audio_video(
                    {
                        "runId": "skill_run_missing_audio",
                        "skillId": "ffmpeg-video-audio-mux",
                        "selectedCardSnapshots": [
                            {
                                "name": "video",
                                "mediaAssets": [{"kind": "video", "src": "/api/artifacts/imports/video.mp4"}],
                            }
                        ],
                    }
                )


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg and ffprobe are required")
class MuxAudioVideoFfmpegTest(unittest.TestCase):
    def payload_for(self, root: Path, run_id: str, video: Path, audio: Path) -> dict:
        return {
            "runId": run_id,
            "skillId": "ffmpeg-video-audio-mux",
            "prompt": "put audio on video",
            "params": {"title": "Muxed"},
            "selectedCardSnapshots": [
                {
                    "name": video.stem,
                    "mediaAssets": [{"kind": "video", "src": f"/api/artifacts/{video.relative_to(root).as_posix()}"}],
                },
                {
                    "name": audio.stem,
                    "mediaAssets": [{"kind": "audio", "src": f"/api/artifacts/{audio.relative_to(root).as_posix()}"}],
                },
            ],
        }

    def test_short_audio_is_padded_with_silence_to_video_duration(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(os.environ, {"LOKI_ARTIFACTS_ROOT": tmpdir}):
            root = Path(tmpdir)
            video = root / "imports" / "video.mp4"
            audio = root / "imports" / "audio.m4a"
            create_video(video, duration=1.8)
            create_audio(audio, duration=0.6)

            result = mux_audio_video.mux_selected_audio_video(self.payload_for(root, "skill_run_pad", video, audio))
            artifact = result["artifacts"][0]
            output = Path(artifact["path"])
            info = mux_audio_video.video_info(output)
            output_audio = mux_audio_video.audio_info(output)

            self.assertTrue(output.is_file())
            self.assertEqual(artifact["kind"], "video")
            self.assertEqual(artifact["mimeType"], "video/mp4")
            self.assertEqual(artifact["metadata"]["audioFitMode"], "padded-with-silence")
            self.assertTrue(info["has_audio"])
            self.assertGreater(output_audio["duration"], 1.3)

    def test_long_audio_is_trimmed_to_video_duration(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(os.environ, {"LOKI_ARTIFACTS_ROOT": tmpdir}):
            root = Path(tmpdir)
            video = root / "imports" / "video.mp4"
            audio = root / "imports" / "audio.m4a"
            create_video(video, audio=False, duration=0.9)
            create_audio(audio, duration=2.2)

            result = mux_audio_video.mux_selected_audio_video(self.payload_for(root, "skill_run_trim", video, audio))
            output = Path(result["artifacts"][0]["path"])
            info = mux_audio_video.video_info(output)
            output_audio = mux_audio_video.audio_info(output)

            self.assertTrue(info["has_audio"])
            self.assertEqual(result["artifacts"][0]["metadata"]["audioFitMode"], "trimmed-to-video")
            self.assertLess(info["duration"], 1.3)
            self.assertLess(output_audio["duration"], 1.3)


if __name__ == "__main__":
    unittest.main()
