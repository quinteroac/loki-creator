#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="comfy-videoedit",
        description="Edit MP4 videos through the video-edit capabilities currently exposed by comfy-videogen.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    video_audio = subparsers.add_parser("video-audio", help="Run WAN 2.2 video+audio edit presets.")
    add_passthrough_options(
        video_audio,
        required=("--mode", "--input-video", "--audio"),
        choices={"--mode": ("audio-driven", "lipsync")},
        options=(
            "--models-dir",
            "--out",
            "--mode",
            "--input-video",
            "--audio",
            "--mask-video",
            "--mask-image",
            "--prompt",
            "--unet",
            "--text-encoder",
            "--audio-encoder",
            "--vae",
            "--chunk-length",
            "--chunk-overlap",
            "--steps",
            "--denoise",
            "--cfg",
            "--sampler",
            "--scheduler",
            "--shift",
            "--seed",
            "--negative-prompt",
            "--audio-start-time",
        ),
    )
    video_audio.add_argument("--no-manifest", action="store_true")
    video_audio.add_argument("--verbose", action="store_true")

    bernini = subparsers.add_parser("bernini", help="Run WAN 2.2 Bernini reference-guided video editing.")
    add_passthrough_options(
        bernini,
        required=("--prompt",),
        append=("--reference-image",),
        options=(
            "--models-dir",
            "--out",
            "--input-video",
            "--reference-image",
            "--prompt",
            "--unet-high",
            "--unet-low",
            "--lora",
            "--text-encoder",
            "--vae",
            "--width",
            "--height",
            "--length",
            "--fps",
            "--steps",
            "--split-step",
            "--cfg",
            "--seed",
            "--negative-prompt",
            "--high-lora-strength",
            "--low-lora-strength",
            "--sampler",
            "--scheduler",
            "--ref-max-size",
        ),
    )
    bernini.add_argument("--no-manifest", action="store_true")
    bernini.add_argument("--verbose", action="store_true")
    return parser


def add_passthrough_options(
    parser: argparse.ArgumentParser,
    *,
    options: tuple[str, ...],
    required: tuple[str, ...] = (),
    append: tuple[str, ...] = (),
    choices: dict[str, tuple[str, ...]] | None = None,
) -> None:
    choices = choices or {}
    for option in options:
        kwargs = {
            "required": option in required,
            "choices": choices.get(option),
            "action": "append" if option in append else "store",
        }
        parser.add_argument(option, **{key: value for key, value in kwargs.items() if value})


def command_for_args(args: argparse.Namespace) -> list[str]:
    mode = "wan22-video-audio" if args.command == "video-audio" else "wan22-bernini"
    command = ["comfy-videogen", mode]
    for key, value in vars(args).items():
        if key == "command" or value in (None, False):
            continue
        option = f"--{key.replace('_', '-')}"
        if value is True:
            command.append(option)
        elif isinstance(value, list):
            for item in value:
                command.extend([option, str(item)])
        else:
            command.extend([option, str(value)])
    return command


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    command = command_for_args(args)
    if shutil.which("comfy-videogen") is None:
        parser.error("comfy-videogen is required. Install/update comfy-agent-tools first.")

    process = subprocess.run(command, text=True, check=False)
    return process.returncode


if __name__ == "__main__":
    raise SystemExit(main())
