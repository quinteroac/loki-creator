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

import join_videos


HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def run(command: list[str]) -> None:
    process = subprocess.run(command, text=True, capture_output=True, check=False)
    if process.returncode != 0:
        raise AssertionError(process.stderr or process.stdout)


def create_clip(path: Path, *, audio: bool = True, color: str = "red", duration: float = 0.8) -> None:
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
                f"sine=frequency=440:sample_rate=48000:d={duration}",
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


class JoinVideosSelectionTest(unittest.TestCase):
    def test_materialize_selected_videos_preserves_order_fallback_and_dedupes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifact_a = root / "imports" / "a.mp4"
            artifact_b = root / "imports" / "b.mp4"
            artifact_a.parent.mkdir(parents=True)
            artifact_a.write_bytes(b"a")
            artifact_b.write_bytes(b"b")

            payload = {
                "selectedCardSnapshots": [
                    {
                        "name": "first",
                        "mediaAssets": [{"kind": "source", "mimeType": "video/mp4", "src": "/api/artifacts/imports/a.mp4"}],
                    },
                    {
                        "name": "second",
                        "mediaAssets": [{"kind": "image", "src": "/api/artifacts/imports/ignored.png"}],
                        "metadata": {"kind": "video", "artifactUrl": "/api/artifacts/imports/b.mp4"},
                    },
                    {
                        "name": "duplicate",
                        "mediaAssets": [{"kind": "video", "src": "/api/artifacts/imports/a.mp4"}],
                    },
                ]
            }

            with patch.dict(os.environ, {"LOKI_ARTIFACTS_ROOT": str(root)}):
                videos = join_videos.materialize_selected_videos(payload, root / "inputs")

        self.assertEqual(videos, [artifact_a, artifact_b])

    def test_join_selected_videos_requires_two_videos(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(os.environ, {"LOKI_ARTIFACTS_ROOT": tmpdir}):
            with self.assertRaisesRegex(RuntimeError, "at least two selected video cards"):
                join_videos.join_selected_videos(
                    {
                        "runId": "skill_run_test",
                        "skillId": "ffmpeg-video-join",
                        "params": {"joinMode": "direct"},
                        "selectedCardSnapshots": [],
                    }
                )


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg and ffprobe are required")
class JoinVideosFfmpegTest(unittest.TestCase):
    def payload_for(self, root: Path, run_id: str, mode: str, clips: list[Path], **params: object) -> dict:
        return {
            "runId": run_id,
            "skillId": "ffmpeg-video-join",
            "prompt": f"join with {mode}",
            "params": {"joinMode": mode, **params},
            "selectedCardSnapshots": [
                {
                    "name": clip.stem,
                    "mediaAssets": [{"kind": "video", "src": f"/api/artifacts/{clip.relative_to(root).as_posix()}"}],
                }
                for clip in clips
            ],
        }

    def test_direct_produces_valid_mp4(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(os.environ, {"LOKI_ARTIFACTS_ROOT": tmpdir}):
            root = Path(tmpdir)
            clip_a = root / "imports" / "a.mp4"
            clip_b = root / "imports" / "b.mp4"
            clip_a.parent.mkdir(parents=True)
            create_clip(clip_a, color="red")
            create_clip(clip_b, color="blue")

            result = join_videos.join_selected_videos(self.payload_for(root, "skill_run_direct", "direct", [clip_a, clip_b]))
            output = Path(result["artifacts"][0]["path"])

            self.assertTrue(output.is_file())
            info = join_videos.video_info(output)
            self.assertTrue(info["has_audio"])
            self.assertGreater(info["duration"], 1.0)

    def test_trim_last_frame_reduces_duration(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(os.environ, {"LOKI_ARTIFACTS_ROOT": tmpdir}):
            root = Path(tmpdir)
            clip_a = root / "imports" / "a.mp4"
            clip_b = root / "imports" / "b.mp4"
            clip_a.parent.mkdir(parents=True)
            create_clip(clip_a, color="red", duration=1.0)
            create_clip(clip_b, color="blue", duration=1.0)

            direct = join_videos.join_selected_videos(self.payload_for(root, "skill_run_direct", "direct", [clip_a, clip_b]))
            trimmed = join_videos.join_selected_videos(
                self.payload_for(root, "skill_run_trim", "trim-last-frame", [clip_a, clip_b])
            )

            direct_duration = join_videos.video_info(Path(direct["artifacts"][0]["path"]))["duration"]
            trimmed_duration = join_videos.video_info(Path(trimmed["artifacts"][0]["path"]))["duration"]
            self.assertLess(trimmed_duration, direct_duration - 0.04)

    def test_crossfade_produces_valid_video_with_audio(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(os.environ, {"LOKI_ARTIFACTS_ROOT": tmpdir}):
            root = Path(tmpdir)
            clip_a = root / "imports" / "a.mp4"
            clip_b = root / "imports" / "b.mp4"
            clip_a.parent.mkdir(parents=True)
            create_clip(clip_a, color="red", duration=1.0)
            create_clip(clip_b, color="blue", duration=1.0)

            result = join_videos.join_selected_videos(
                self.payload_for(root, "skill_run_crossfade", "crossfade", [clip_a, clip_b], fadeDurationSeconds=0.2)
            )
            info = join_videos.video_info(Path(result["artifacts"][0]["path"]))

            self.assertTrue(info["has_audio"])
            self.assertGreater(info["duration"], 1.0)

    def test_clip_without_audio_receives_silence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(os.environ, {"LOKI_ARTIFACTS_ROOT": tmpdir}):
            root = Path(tmpdir)
            clip_a = root / "imports" / "a.mp4"
            clip_b = root / "imports" / "b.mp4"
            clip_a.parent.mkdir(parents=True)
            create_clip(clip_a, audio=False, color="red")
            create_clip(clip_b, audio=True, color="blue")

            result = join_videos.join_selected_videos(self.payload_for(root, "skill_run_silence", "direct", [clip_a, clip_b]))
            info = join_videos.video_info(Path(result["artifacts"][0]["path"]))

            self.assertTrue(info["has_audio"])


if __name__ == "__main__":
    unittest.main()
