from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

from PIL import Image


IMAGE_MIME_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/jpg": ".jpg", "image/webp": ".webp"}
AUDIO_MIME_TYPES = {"audio/wav": ".wav", "audio/x-wav": ".wav", "audio/mpeg": ".mp3", "audio/mp3": ".mp3", "audio/flac": ".flac"}
VIDEO_MIME_TYPES = {"video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov"}
ASPECT_DIMENSIONS = {
    "1:1": (1024, 1024),
    "4:3": (1152, 864),
    "16:9": (1344, 768),
    "9:16": (768, 1344),
}
VIDEO_BASE_DIMENSIONS = {
    "1:1": (512, 512),
    "4:3": (512, 384),
    "16:9": (512, 288),
    "9:16": (288, 512),
}
MUSIC_QUALITY_DEFAULTS = {
    "steps": "64",
    "cfg": "7.0",
}
CHANGE_ASPECT_RATIOS = set(ASPECT_DIMENSIONS)


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


def resolve_artifact_src(src: str) -> Path | None:
    if not src.startswith("/api/artifacts/"):
        return None

    artifact_path = (artifacts_root() / src.removeprefix("/api/artifacts/")).resolve()
    try:
        artifact_path.relative_to(artifacts_root())
    except ValueError:
        return None

    return artifact_path if artifact_path.is_file() else None


def materialize_selected_media(payload: dict[str, Any], inputs_dir: Path) -> dict[str, list[Path]]:
    inputs_dir.mkdir(parents=True, exist_ok=True)
    media: dict[str, list[Path]] = {"image": [], "audio": [], "video": []}
    attachments = payload.get("attachments")
    if isinstance(attachments, list):
        for attachment_index, attachment in enumerate(attachments, start=1):
            if not isinstance(attachment, dict) or attachment.get("omitted"):
                continue
            kind = first_text(attachment.get("kind"))
            if kind not in media:
                continue
            data_url = first_text(attachment.get("dataUrl"))
            if not data_url.startswith(f"data:{kind}/"):
                continue
            try:
                path = write_data_url(data_url, inputs_dir / f"attachment-{attachment_index:02d}-{kind}")
            except Exception:
                path = None
            if path is not None:
                media[kind].append(path)

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
                path = resolve_artifact_src(data_url)
                if path is None:
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


def unique_items(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = value.strip()
        key = normalized.lower()
        if normalized and key not in seen:
            seen.add(key)
            result.append(normalized)
    return result


def normalize_video_mode(value: str) -> str:
    normalized = value.strip().lower().replace("_", "-")
    aliases = {
        "text-to-video": "t2v",
        "txt2vid": "t2v",
        "image-to-video": "i2v",
        "img2vid": "i2v",
        "reference-to-video": "i2v",
        "reference-image-to-video": "i2v",
        "image-audio-to-video": "ia2av",
        "image-plus-audio-to-video": "ia2av",
        "image-and-audio-to-video": "ia2av",
        "first-last-frame": "flf2v",
        "first-last-frame-to-video": "flf2v",
        "first-and-last-frame-to-video": "flf2v",
        "motion-track-control": "motion-track",
        "seedance2-text-to-video": "seedance2-t2v",
        "seedance2-image-to-video": "seedance2-r2v",
        "seedance2-reference-to-video": "seedance2-r2v",
        "seedance2-reference-image-to-video": "seedance2-r2v",
        "seedance2-first-last-frame": "seedance2-flf2v",
        "seedance2-first-last-frame-to-video": "seedance2-flf2v",
    }
    return aliases.get(normalized, normalized)


def dimensions(params: dict[str, Any]) -> tuple[int | None, int | None]:
    width = as_int(params.get("width"))
    height = as_int(params.get("height"))
    if width and height:
        return width, height
    aspect_ratio = first_text(params.get("aspectRatio"))
    return ASPECT_DIMENSIONS.get(aspect_ratio, (width, height))


def video_dimensions(params: dict[str, Any]) -> tuple[int | None, int | None]:
    aspect_ratio = first_text(params.get("aspectRatio"))
    if aspect_ratio in VIDEO_BASE_DIMENSIONS:
        return VIDEO_BASE_DIMENSIONS[aspect_ratio]

    width = as_int(params.get("width"))
    height = as_int(params.get("height"))
    if width and height:
        return width, height
    return width, height


def parse_music_duration_seconds(text: str) -> str:
    match = re.search(r"(?:~|about|around|approx\.?\s*)?(\d{1,2}):(\d{2})\s*(?:duration|long|minutes?|mins?)?", text, re.IGNORECASE)
    if match:
        return str((int(match.group(1)) * 60) + int(match.group(2)))
    match = re.search(r"(?:~|about|around|approx\.?\s*)?(\d{1,3})\s*(?:seconds?|secs?|s)\b", text, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r"(?:~|about|around|approx\.?\s*)?(\d{1,2})\s*(?:minutes?|mins?)\b", text, re.IGNORECASE)
    if match:
        return str(int(match.group(1)) * 60)
    return ""


def parse_music_language(text: str) -> str:
    lowered = text.lower()
    languages = {
        "japanese": "ja",
        "j-pop": "ja",
        "jpop": "ja",
        "spanish": "es",
        "espanol": "es",
        "español": "es",
        "english": "en",
        "korean": "ko",
        "k-pop": "ko",
        "kpop": "ko",
        "chinese": "zh",
        "mandarin": "zh",
        "french": "fr",
    }
    for needle, code in languages.items():
        if needle in lowered:
            return code
    return ""


def parse_music_keyscale(text: str) -> str:
    match = re.search(r"\b([A-G](?:#|b)?)\s+(major|minor)\b", text, re.IGNORECASE)
    if match:
        return f"{match.group(1).upper()} {match.group(2).lower()}"
    if re.search(r"\bminor\s+key\b", text, re.IGNORECASE):
        return "A minor"
    if re.search(r"\bmajor\s+key\b", text, re.IGNORECASE):
        return "C major"
    return ""


def parse_music_bpm(text: str) -> str:
    match = re.search(r"\b(\d{2,3})\s*bpm\b", text, re.IGNORECASE)
    return match.group(1) if match else ""


def looks_like_music_caption(prompt: str) -> bool:
    stripped = prompt.strip()
    lowered = stripped.lower()
    if "," not in stripped:
        return False
    if re.match(r"^(generate|create|make|compose|write|produce)\b", lowered):
        return False
    if re.search(r"\b(song|track|music)\s+(about|for|that|with)\b", lowered):
        return False
    return True


def normalize_music_caption(prompt: str) -> str:
    if looks_like_music_caption(prompt):
        return prompt

    lowered = prompt.lower()
    tags: list[str] = []
    genre_map = [
        ("j-pop", "Japanese J-pop"),
        ("jpop", "Japanese J-pop"),
        ("k-pop", "Korean K-pop"),
        ("kpop", "Korean K-pop"),
        ("city pop", "Japanese city pop"),
        ("lofi", "lofi hip hop"),
        ("hip hop", "hip hop"),
        ("latin pop", "Latin pop"),
        ("pop", "pop"),
        ("rock", "rock"),
        ("ballad", "ballad"),
        ("orchestral", "cinematic orchestral score"),
        ("cinematic", "cinematic score"),
        ("electronic", "electronic music"),
        ("edm", "EDM"),
        ("jazz", "jazz"),
        ("reggaeton", "reggaeton"),
    ]
    for needle, tag in genre_map:
        if needle in lowered:
            tags.append(tag)
            break
    if not tags:
        tags.append("pop")

    if "instrumental" in lowered or "[instrumental]" in lowered:
        tags.append("instrumental")
    elif "female" in lowered:
        tags.append("female vocal")
    elif "male" in lowered:
        tags.append("male vocal")
    elif "japanese" in lowered or "j-pop" in lowered or "jpop" in lowered:
        tags.append("Japanese vocal")
    else:
        tags.append("vocal song")

    mood_map = [
        ("sad", "melancholic mood"),
        ("triste", "melancholic mood"),
        ("melancholic", "melancholic mood"),
        ("emotional", "emotional"),
        ("happy", "upbeat mood"),
        ("dark", "dark mood"),
        ("romantic", "romantic mood"),
        ("energetic", "energetic"),
    ]
    for needle, tag in mood_map:
        if needle in lowered:
            tags.append(tag)

    instrument_map = [
        ("piano", "piano"),
        ("guitar", "guitar"),
        ("synth", "synth hooks"),
        ("bass", "electric bass"),
        ("drums", "drums"),
        ("strings", "strings"),
    ]
    for needle, tag in instrument_map:
        if needle in lowered:
            tags.append(tag)

    if "modern" in lowered:
        tags.append("modern production")
    if "radio" in lowered:
        tags.append("radio-ready mix")
    if "clean" in lowered:
        tags.append("clean mix")

    bpm = parse_music_bpm(prompt)
    if bpm:
        tags.append(f"{bpm} BPM")
    keyscale = parse_music_keyscale(prompt)
    if keyscale:
        tags.append(keyscale)

    return ", ".join(unique_items(tags))


def normalized_music_params(prompt: str, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    music_params = dict(params)
    if not first_text(music_params.get("duration")):
        duration = parse_music_duration_seconds(prompt)
        if duration:
            music_params["duration"] = duration
    if not first_text(music_params.get("bpm")):
        bpm = parse_music_bpm(prompt)
        if bpm:
            music_params["bpm"] = bpm
    if not first_text(music_params.get("keyscale")):
        keyscale = parse_music_keyscale(prompt)
        if keyscale:
            music_params["keyscale"] = keyscale
    if not first_text(music_params.get("language")):
        language = parse_music_language(prompt)
        if language:
            music_params["language"] = language
    return normalize_music_caption(prompt), music_params


def normalize_model_profile(value: str) -> str:
    aliases = {
        "qwen-image-edit-2511": "qwen-edit2511",
        "qwen-image-edit": "qwen-edit2511",
        "qwen-edit-2511": "qwen-edit2511",
        "flux-klein-snofs": "flux-klein-9b-snofs",
        "flux-2-klein-9b-snofs": "flux-klein-9b-snofs",
    }
    return aliases.get(value, value)


def normalize_video_model_profile(value: str) -> str:
    aliases = {
        "ltx": "ltx23-10eros",
        "ltx23": "ltx23-10eros",
        "ltx-2.3": "ltx23-10eros",
        "ltx-2.3-10eros": "ltx23-10eros",
        "ltx23-local": "ltx23-10eros",
        "seedance": "seedance2-api",
        "seedance2": "seedance2-api",
        "seedance-2": "seedance2-api",
        "seedance-2.0": "seedance2-api",
    }
    return aliases.get(value, value)


def video_mode_for_profile(mode: str, model_profile: str, media: dict[str, list[Path]]) -> str:
    if model_profile == "ltx23-10eros" and mode.startswith("seedance2-"):
        if mode == "seedance2-flf2v":
            return "flf2v"
        if mode == "seedance2-r2v":
            return "i2v"
        return "t2v"
    if model_profile != "seedance2-api" or mode.startswith("seedance2-"):
        return mode
    if mode == "flf2v" or len(media.get("image", [])) >= 2:
        return "seedance2-flf2v"
    if mode in {"i2v", "ia2av", "motion-track"} or selected_input(media, "image"):
        return "seedance2-r2v"
    return "seedance2-t2v"


def divisible_by_16(value: int) -> int:
    lower = max(16, value - (value % 16))
    upper = lower if value % 16 == 0 else lower + 16
    return lower if abs(value - lower) <= abs(upper - value) else upper


def image_dimensions(path: Path | None) -> tuple[int | None, int | None]:
    if path is None:
        return None, None
    try:
        with Image.open(path) as image:
            return image.size
    except Exception:
        return None, None


def half_scale_image_input(path: Path, inputs_dir: Path, label: str) -> Path:
    with Image.open(path) as image:
        width, height = image.size
        target_width = max(16, width // 2)
        target_height = max(16, height // 2)
        target_width -= target_width % 2
        target_height -= target_height % 2
        resized = image.convert("RGB").resize((target_width, target_height), Image.Resampling.LANCZOS)
        destination = inputs_dir / f"{label}-half.png"
        resized.save(destination)
        return destination


def maybe_half_scale_ltx_image_input(path_value: str, out_dir: Path, mode: str) -> str:
    if mode.startswith("seedance2-") or mode not in {"i2v", "ia2av", "flf2v", "motion-track"}:
        return path_value
    if not path_value:
        return path_value

    path = Path(path_value)
    if not path.is_file():
        return path_value

    inputs_dir = out_dir.parent / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    try:
        return str(half_scale_image_input(path, inputs_dir, path.stem[:48] or "input"))
    except Exception:
        return path_value


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
    model_profile = normalize_model_profile(first_text(params.get("modelProfile"), params.get("profile")))
    aspect_ratio = first_text(params.get("aspectRatio"))
    changes_aspect_ratio = aspect_ratio in CHANGE_ASPECT_RATIOS

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
    image_input_path = selected_input(media, "image")
    if mode == "edit" and model_profile == "flux-klein-9b-snofs" and (not width or not height):
        input_width, input_height = image_dimensions(image_input_path)
        if input_width and input_height:
            width, height = divisible_by_16(input_width), divisible_by_16(input_height)
    if width and height and mode == "generate":
        command.extend(["--width", str(width), "--height", str(height)])
    if width and height and mode == "edit" and model_profile == "flux-klein-9b-snofs":
        command.extend(["--width", str(width), "--height", str(height)])
    if changes_aspect_ratio and mode in {"grok-generate", "grok-edit"}:
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
        model_profile = normalize_video_model_profile(first_text(params.get("modelProfile"), params.get("profile")))
        if not model_profile and skill_id == "comfy-videogen":
            raise RuntimeError("comfy-videogen requires params.modelProfile. The agent must ask the user which video model to use.")
        mode = normalize_video_mode(command_from_params(params, default_mode))
        mode = video_mode_for_profile(mode, model_profile, media)
        command = ["comfy-videogen", mode, "--out", str(out_dir)]
        if not mode.startswith("seedance2-"):
            command.extend(["--models-dir", str(model_dir)])
        command.extend(["--prompt", prompt])
        image_input = first_text(params.get("inputPath")) or str(selected_input(media, "image") or "")
        image_input = maybe_half_scale_ltx_image_input(image_input, out_dir, mode)
        if mode in {"i2v", "ia2av", "motion-track", "seedance2-r2v"} and image_input:
            command.extend(["--input", image_input])
        if mode in {"flf2v", "seedance2-flf2v"}:
            image_inputs = media.get("image", [])
            first = maybe_half_scale_ltx_image_input(
                first_text(params.get("firstPath")) or str(image_inputs[0] if image_inputs else ""),
                out_dir,
                mode,
            )
            last = maybe_half_scale_ltx_image_input(
                first_text(params.get("lastPath")) or str(image_inputs[-1] if image_inputs else ""),
                out_dir,
                mode,
            )
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
        width, height = video_dimensions(params)
        if width and height and not mode.startswith("seedance2-"):
            command.extend(["--width", str(width), "--height", str(height)])
        if first_text(params.get("aspectRatio")) and mode.startswith("seedance2-"):
            command.extend(["--ratio", first_text(params.get("aspectRatio"))])
        duration = as_int(params.get("duration"))
        if duration is not None:
            if mode.startswith("seedance2-"):
                command.extend(["--duration", str(duration)])
            elif as_int(params.get("length")) is None:
                fps = as_int(params.get("fps")) or 24
                command.extend(["--length", str(duration * fps)])
        for key in ("length", "fps", "duration", "seed"):
            value = as_int(params.get(key))
            if key == "duration" and duration is not None:
                continue
            if value is not None:
                command.extend([f"--{key}", str(value)])
        return command, repo_root()

    if skill_id == "comfy-musicgen":
        prompt, music_params = normalized_music_params(prompt, params)
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
        lyrics = first_text(music_params.get("lyrics"))
        if lyrics:
            command.extend(["--lyrics", lyrics])
        for key, cli_key in (
            ("duration", "duration"),
            ("bpm", "bpm"),
            ("steps", "steps"),
            ("cfg", "cfg"),
            ("language", "language"),
            ("keyscale", "keyscale"),
            ("timeSignature", "time-signature"),
            ("time_signature", "time-signature"),
            ("sampler", "sampler"),
            ("scheduler", "scheduler"),
        ):
            value = first_text(music_params.get(key))
            if not value and key in MUSIC_QUALITY_DEFAULTS:
                value = MUSIC_QUALITY_DEFAULTS[key]
            if value:
                command.extend([f"--{cli_key}", value])
        extra_lora = music_params.get("extraLora") or music_params.get("extra_lora")
        if isinstance(extra_lora, list):
            for value in extra_lora:
                resolved = first_text(value)
                if resolved:
                    command.extend(["--extra-lora", resolved])
        else:
            resolved = first_text(extra_lora)
            if resolved:
                command.extend(["--extra-lora", resolved])
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
    env.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
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


def prompt_from_command(command: list[str], fallback: str) -> str:
    try:
        index = command.index("--prompt")
    except ValueError:
        return fallback
    if index + 1 >= len(command):
        return fallback
    return command[index + 1]


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
    print(json.dumps(raw_result_from_cli(result, command, prompt_from_command(command, base_prompt(payload)))))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"comfy action failed: {exc}", file=sys.stderr)
        sys.exit(1)
