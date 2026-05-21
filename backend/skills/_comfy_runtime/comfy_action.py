from __future__ import annotations

import base64
import json
import mimetypes
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4


IMAGE_MIME_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/jpg": ".jpg", "image/webp": ".webp"}
AUDIO_MIME_TYPES = {"audio/wav": ".wav", "audio/x-wav": ".wav", "audio/mpeg": ".mp3", "audio/mp3": ".mp3", "audio/flac": ".flac"}
VIDEO_MIME_TYPES = {"video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov"}
ASPECT_DIMENSIONS = {
    "1:1": (1024, 1024),
    "4:3": (1152, 864),
    "16:9": (1344, 768),
    "9:16": (768, 1344),
}


def read_payload() -> dict[str, Any]:
    raw = sys.stdin.read()
    return json.loads(raw) if raw.strip() else {}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def artifacts_root() -> Path:
    return Path(os.environ.get("LOKI_ARTIFACTS_ROOT", repo_root() / ".loki")).resolve()


def first_text(*values: object) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def as_int(value: object) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_data_url(data_url: str) -> tuple[str, bytes]:
    header, separator, encoded = data_url.partition(",")
    if separator != "," or not header.startswith("data:") or ";base64" not in header:
        raise ValueError("invalid base64 data URL")
    return header[5:].split(";", 1)[0] or "application/octet-stream", base64.b64decode(encoded)


def extension_for_mime(mime_type: str) -> str:
    return (
        IMAGE_MIME_TYPES.get(mime_type)
        or AUDIO_MIME_TYPES.get(mime_type)
        or VIDEO_MIME_TYPES.get(mime_type)
        or mimetypes.guess_extension(mime_type)
        or ".bin"
    )


def write_data_url(data_url: str, destination: Path) -> Path | None:
    mime_type, data = parse_data_url(data_url)
    if mime_type not in {*IMAGE_MIME_TYPES, *AUDIO_MIME_TYPES, *VIDEO_MIME_TYPES}:
        return None
    path = destination.with_suffix(extension_for_mime(mime_type))
    path.write_bytes(data)
    return path


def materialize_selected_media(payload: dict[str, Any], inputs_dir: Path) -> dict[str, list[Path]]:
    inputs_dir.mkdir(parents=True, exist_ok=True)
    media: dict[str, list[Path]] = {"image": [], "audio": [], "video": []}
    snapshots = payload.get("selectedCardSnapshots")
    if not isinstance(snapshots, list):
        return media

    for snapshot_index, snapshot in enumerate(snapshots, start=1):
        if not isinstance(snapshot, dict):
            continue

        assets = snapshot.get("mediaAssets")
        if isinstance(assets, list):
            for asset_index, asset in enumerate(assets, start=1):
                if not isinstance(asset, dict):
                    continue
                kind = first_text(asset.get("kind"))
                if kind not in media:
                    continue
                data_url = first_text(asset.get("dataUrl"), asset.get("src"))
                if not data_url.startswith(f"data:{kind}/"):
                    continue
                try:
                    path = write_data_url(data_url, inputs_dir / f"{snapshot_index:02d}-{asset_index:02d}-{kind}")
                except Exception:
                    path = None
                if path is not None:
                    media[kind].append(path)

        if not media["image"]:
            preview = snapshot.get("preview")
            if isinstance(preview, dict) and not preview.get("omitted"):
                data_url = first_text(preview.get("dataUrl"))
                if data_url.startswith("data:image/"):
                    try:
                        path = write_data_url(data_url, inputs_dir / f"{snapshot_index:02d}-preview")
                    except Exception:
                        path = None
                    if path is not None:
                        media["image"].append(path)

    return media


def models_dir() -> Path:
    return Path(os.environ.get("LOKI_COMFY_MODELS_DIR", repo_root() / ".loki" / "models" / "comfyui")).absolute()


def output_dir(payload: dict[str, Any]) -> Path:
    run_id = first_text(payload.get("runId"), f"skill_run_{uuid4().hex}")
    skill_id = first_text(payload.get("skillId"), "comfy")
    path = artifacts_root() / "skills" / skill_id / run_id / "outputs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def base_prompt(payload: dict[str, Any]) -> str:
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    return first_text(params.get("prompt"), params.get("skillPrompt"), params.get("outputText"), payload.get("prompt"))


def command_from_params(params: dict[str, Any], default: str) -> str:
    return first_text(params.get("command"), params.get("mode"), default)


def dimensions(params: dict[str, Any]) -> tuple[int | None, int | None]:
    width = as_int(params.get("width"))
    height = as_int(params.get("height"))
    if width and height:
        return width, height
    aspect_ratio = first_text(params.get("aspectRatio"))
    return ASPECT_DIMENSIONS.get(aspect_ratio, (width, height))


def selected_input(media: dict[str, list[Path]], kind: str) -> Path | None:
    return media.get(kind, [None])[0] if media.get(kind) else None


def imagegen_capability(mode: str) -> str:
    return {
        "generate": "imagegen.generate",
        "edit": "imagegen.edit",
        "upscale": "imagegen.upscale",
        "grok-generate": "imagegen.grok-generate",
        "grok-edit": "imagegen.grok-edit",
    }.get(mode, f"imagegen.{mode}")


def local_comfy_config() -> dict[str, Any]:
    config_path = repo_root() / ".comfy-agent-tools.json"
    if not config_path.is_file():
        return {}
    try:
        parsed = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def write_run_comfy_config(run_dir: Path, *, capability: str, model_profile: str) -> Path:
    base_config = local_comfy_config()
    config = {
        **base_config,
        "models_dir": str(models_dir()),
        "defaults": {
            **dict(base_config.get("defaults", {})),
            capability: model_profile,
        },
        "profiles": dict(base_config.get("profiles", {})),
    }
    config_dir = run_dir / "comfy-config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / ".comfy-agent-tools.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return config_dir


def maybe_adjust_imagegen_mode_for_profile(mode: str, model_profile: str) -> str:
    if model_profile == "grok-imagine-api" and mode == "generate":
        return "grok-generate"
    if model_profile == "grok-imagine-api" and mode == "edit":
        return "grok-edit"
    return mode


def is_anima_profile(model_profile: str) -> bool:
    return model_profile in {"anima-base", "anima-preview3-turbo"}


def looks_like_tag_prompt(prompt: str) -> bool:
    stripped = prompt.strip()
    if not stripped:
        return False

    tags = [tag.strip() for tag in stripped.split(",") if tag.strip()]
    if len(tags) < 5:
        return False

    sentence_markers = {".", "?", "!", ";", ":"}
    if any(marker in stripped for marker in sentence_markers):
        return False

    long_phrases = [tag for tag in tags if len(tag.split()) > 4]
    if long_phrases:
        return False

    natural_language_starters = {
        "a ",
        "an ",
        "the ",
        "una ",
        "un ",
        "el ",
        "la ",
        "los ",
        "las ",
        "retrato ",
        "portrait ",
        "imagen ",
        "image ",
        "genera ",
        "generate ",
    }
    lowered_first_tag = tags[0].lower()
    return not any(lowered_first_tag.startswith(marker) for marker in natural_language_starters)


def validate_imagegen_prompt(mode: str, model_profile: str, prompt: str, skill_label: str) -> None:
    if mode != "generate" or not is_anima_profile(model_profile):
        return
    if looks_like_tag_prompt(prompt):
        return

    raise RuntimeError(
        f"{skill_label} with {model_profile} requires Danbooru-style tags, not natural language. "
        "Rewrite the user's request into a comma-separated tag prompt before invoking the skill. "
        "Use compact tags like: masterpiece, best quality, score_7, safe, 1girl, samurai, katana, "
        "forest, rain, cinematic lighting, detailed background, anime style."
    )


def build_imagegen_command(
    *,
    mode: str,
    params: dict[str, Any],
    prompt: str,
    out_dir: Path,
    media: dict[str, list[Path]],
    require_model_profile: bool,
    require_aspect_ratio: bool,
    require_input_image: bool,
    skill_label: str,
) -> tuple[list[str], Path]:
    model_dir = models_dir()
    model_profile = first_text(params.get("modelProfile"), params.get("profile"))
    aspect_ratio = first_text(params.get("aspectRatio"))

    if require_model_profile and not model_profile:
        raise RuntimeError(f"{skill_label} requires params.modelProfile. The agent must ask the user which model to use.")
    if require_aspect_ratio and not aspect_ratio:
        raise RuntimeError(f"{skill_label} requires params.aspectRatio. The agent must ask the user which aspect ratio to use.")

    if model_profile:
        mode = maybe_adjust_imagegen_mode_for_profile(mode, model_profile)
    validate_imagegen_prompt(mode, model_profile, prompt, skill_label)

    command = ["comfy-imagegen", mode, "--out", str(out_dir)]
    if mode in {"generate", "edit", "upscale"}:
        command.extend(["--models-dir", str(model_dir)])
    if mode in {"generate", "edit", "grok-generate", "grok-edit"}:
        command.extend(["--prompt", prompt])
    if mode in {"edit", "upscale", "grok-edit"}:
        image_input = first_text(params.get("inputPath")) or str(selected_input(media, "image") or "")
        if not image_input and require_input_image:
            raise RuntimeError(f"{skill_label} requires an input image from params.inputPath or a selected card snapshot.")
        if image_input:
            command.extend(["--input", image_input])

    width, height = dimensions(params)
    if width and height and mode == "generate":
        command.extend(["--width", str(width), "--height", str(height)])
    if width and height and mode == "edit" and model_profile == "flux-klein-9b-snofs":
        command.extend(["--width", str(width), "--height", str(height)])
    if aspect_ratio and mode in {"grok-generate", "grok-edit"}:
        command.extend(["--aspect-ratio", aspect_ratio])
    if as_int(params.get("seed")) is not None:
        command.extend(["--seed", str(as_int(params.get("seed")))])

    cwd = write_run_comfy_config(out_dir.parent, capability=imagegen_capability(mode), model_profile=model_profile) if model_profile else repo_root()
    return command, cwd


def build_cli_command(payload: dict[str, Any], out_dir: Path, media: dict[str, list[Path]]) -> tuple[list[str], Path]:
    skill_id = first_text(payload.get("skillId"))
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    prompt = base_prompt(payload)
    model_dir = models_dir()

    if skill_id == "comfy-image-generate":
        return build_imagegen_command(
            mode="generate",
            params=params,
            prompt=prompt,
            out_dir=out_dir,
            media=media,
            require_model_profile=True,
            require_aspect_ratio=True,
            require_input_image=False,
            skill_label="comfy-image-generate",
        )

    if skill_id == "comfy-image-edit":
        return build_imagegen_command(
            mode="edit",
            params=params,
            prompt=prompt,
            out_dir=out_dir,
            media=media,
            require_model_profile=True,
            require_aspect_ratio=False,
            require_input_image=True,
            skill_label="comfy-image-edit",
        )

    if skill_id == "comfy-image-upscale":
        return build_imagegen_command(
            mode="upscale",
            params=params,
            prompt=prompt,
            out_dir=out_dir,
            media=media,
            require_model_profile=False,
            require_aspect_ratio=False,
            require_input_image=True,
            skill_label="comfy-image-upscale",
        )

    if skill_id in {"comfy-videogen", "comfy-motion-track-control"}:
        default_mode = "i2v" if selected_input(media, "image") else "t2v"
        if skill_id == "comfy-motion-track-control":
            default_mode = "motion-track"
        mode = command_from_params(params, default_mode)
        command = ["comfy-videogen", mode, "--out", str(out_dir)]
        if not mode.startswith("seedance2-"):
            command.extend(["--models-dir", str(model_dir)])
        command.extend(["--prompt", prompt])
        image_input = first_text(params.get("inputPath")) or str(selected_input(media, "image") or "")
        if mode in {"i2v", "ia2av", "motion-track", "seedance2-r2v"} and image_input:
            command.extend(["--input", image_input])
        if mode in {"flf2v", "seedance2-flf2v"}:
            image_inputs = media.get("image", [])
            first = first_text(params.get("firstPath")) or str(image_inputs[0] if image_inputs else "")
            last = first_text(params.get("lastPath")) or str(image_inputs[-1] if image_inputs else "")
            if first:
                command.extend(["--first", first])
            if last:
                command.extend(["--last", last])
        audio_input = first_text(params.get("audioPath")) or str(selected_input(media, "audio") or "")
        if mode == "ia2av" and audio_input:
            command.extend(["--audio", audio_input])
        control_video = first_text(params.get("controlVideoPath")) or str(selected_input(media, "video") or "")
        if mode == "motion-track" and control_video:
            command.extend(["--control-video", control_video])
        width, height = dimensions(params)
        if width and height and not mode.startswith("seedance2-"):
            command.extend(["--width", str(width), "--height", str(height)])
        if first_text(params.get("aspectRatio")) and mode.startswith("seedance2-"):
            command.extend(["--ratio", first_text(params.get("aspectRatio"))])
        for key in ("length", "fps", "duration", "seed"):
            value = as_int(params.get(key))
            if value is not None:
                command.extend([f"--{key}", str(value)])
        return command, repo_root()

    if skill_id == "comfy-musicgen":
        command = [
            "comfy-musicgen",
            "generate",
            "--models-dir",
            str(model_dir),
            "--out",
            str(out_dir),
            "--prompt",
            prompt,
        ]
        lyrics = first_text(params.get("lyrics"))
        if lyrics:
            command.extend(["--lyrics", lyrics])
        for key in ("duration", "bpm", "steps", "cfg", "language", "keyscale"):
            value = first_text(params.get(key))
            if value:
                command.extend([f"--{key}", value])
        return command, repo_root()

    if skill_id == "comfy-media":
        mode = command_from_params(params, "index")
        command = ["comfy-media", mode, "--out", first_text(params.get("out"), str(out_dir))]
        if mode == "gallery":
            command.append("--dry-run")
        return command, repo_root()

    if skill_id in {"comfy-tools-setup", "comfy-model-onboarding", "comfy-model-downloader", "comfy-lora-onboarding"}:
        if skill_id == "comfy-tools-setup":
            mode = command_from_params(params, "show")
        elif skill_id == "comfy-model-downloader":
            mode = command_from_params(params, "download" if first_text(params.get("capability")) else "show")
        else:
            mode = command_from_params(params, "show")
        command = ["comfy-models", mode]
        capability = first_text(params.get("capability"))
        profile = first_text(params.get("profile"))
        if mode == "download" and capability:
            command.append(capability)
            command.append("--dry-run" if not params.get("yes") else "--yes")
        elif mode == "download-profile" and profile:
            command.append(profile)
            command.append("--dry-run" if not params.get("yes") else "--yes")
        elif mode == "set-models-dir":
            command.append(first_text(params.get("modelsDir"), str(model_dir)))
        return command, repo_root()

    raise RuntimeError(f"Unsupported Comfy skill: {skill_id}")


def run_command(command: list[str], cwd: Path) -> dict[str, Any]:
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    process = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        timeout=int(os.environ.get("LOKI_COMFY_TIMEOUT_SECONDS", "900")),
        check=False,
    )
    if process.returncode != 0:
        message = process.stderr.strip() or process.stdout.strip() or "Comfy command failed"
        raise RuntimeError(message)
    try:
        parsed = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Comfy command did not return JSON: {process.stdout[:500]}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("Comfy command returned non-object JSON")
    return parsed


def artifact_kind(payload: dict[str, Any]) -> str:
    kind = first_text(payload.get("kind"))
    if kind == "music":
        return "audio"
    if kind in {"image", "video", "audio"}:
        return kind
    return "artifact"


def raw_result_from_cli(payload: dict[str, Any], command: list[str], prompt: str) -> dict[str, Any]:
    if payload.get("ok") is False:
        return {
            "diagnostics": [
                {
                    "level": "error",
                    "title": "Comfy command failed",
                    "message": json.dumps(payload, indent=2),
                    "metadata": {"command": command},
                }
            ]
        }

    artifacts = payload.get("artifacts")
    if isinstance(artifacts, list) and artifacts:
        return {
            "artifacts": [
                {
                    "path": str(path),
                    "kind": artifact_kind(payload),
                    "title": first_text(payload.get("title"), payload.get("mode"), "Comfy artifact"),
                    "prompt": prompt,
                    "metadata": payload,
                }
                for path in artifacts
                if isinstance(path, str)
            ]
        }

    return {
        "diagnostics": [
            {
                "level": "info",
                "title": "Comfy result",
                "message": json.dumps(payload, indent=2),
                "metadata": {"command": command},
            }
        ]
    }


def main() -> None:
    payload = read_payload()
    run_dir = output_dir(payload)
    input_media = materialize_selected_media(payload, run_dir.parent / "inputs")
    command, cwd = build_cli_command(payload, run_dir, input_media)
    if shutil.which(command[0]) is None:
        raise RuntimeError(
            f"Comfy CLI not found: {command[0]}. Install with `uv tool install git+https://github.com/quinteroac/comfy-agent-tools`."
        )
    result = run_command(command, cwd)
    print(json.dumps(raw_result_from_cli(result, command, base_prompt(payload))))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"comfy action failed: {exc}", file=sys.stderr)
        sys.exit(1)
