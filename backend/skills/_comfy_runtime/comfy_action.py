from __future__ import annotations

import json
import math
import mimetypes
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

try:
    from PIL import Image
except ModuleNotFoundError:
    Image = None


IMAGE_MIME_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/jpg": ".jpg", "image/webp": ".webp"}
AUDIO_MIME_TYPES = {"audio/wav": ".wav", "audio/x-wav": ".wav", "audio/mpeg": ".mp3", "audio/mp3": ".mp3", "audio/flac": ".flac"}
VIDEO_MIME_TYPES = {"video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov"}
ASPECT_DIMENSIONS = {
    "1:1": (1024, 1024),
    "4:3": (1152, 864),
    "16:9": (1344, 768),
    "9:16": (768, 1344),
}
IDEOGRAM_ASPECT_DIMENSIONS = {
    "1:1": (1024, 1024),
    "3:2": (1248, 832),
    "4:3": (1152, 864),
    "16:9": (1360, 768),
    "21:9": (1344, 576),
    "2:3": (832, 1248),
    "3:4": (864, 1152),
    "9:16": (768, 1360),
}
IDEOGRAM_QUALITY_PROFILES = {
    "quality": {"steps": 48, "mu": "0.0", "std": "1.5", "preset_id": "V4_QUALITY_48"},
    "default": {"steps": 20, "mu": "0.0", "std": "1.75", "preset_id": "V4_DEFAULT_20"},
    "turbo": {"steps": 12, "mu": "0.5", "std": "1.75", "preset_id": "V4_TURBO_12"},
}
IDEOGRAM_FORBIDDEN_REFERENCE_PHRASES = (
    "reference image",
    "selected image",
    "source image",
    "input image",
    "based on the image",
    "based on the reference",
    "from the reference",
    "use the reference",
    "maintain the reference",
    "recreate the reference",
    "imagen de referencia",
    "imagen seleccionada",
    "imagen fuente",
    "imagen de entrada",
    "basado en la imagen",
    "basada en la imagen",
    "basado en la referencia",
    "basada en la referencia",
    "de la referencia",
    "usar la referencia",
    "mantener la referencia",
    "recrear la referencia",
)
VIDEO_BASE_DIMENSIONS = {
    "1:1": (512, 512),
    "4:3": (512, 384),
    "16:9": (512, 288),
    "9:16": (288, 512),
}
VIDEO_RESOLUTION_DIMENSIONS = {
    "360p": {
        "1:1": (360, 360),
        "4:3": (480, 360),
        "16:9": (640, 360),
        "9:16": (360, 640),
    },
    "480p": {
        "1:1": (480, 480),
        "4:3": (640, 480),
        "16:9": (848, 480),
        "9:16": (480, 848),
    },
    "720p": {
        "1:1": (720, 720),
        "4:3": (960, 720),
        "16:9": (1280, 720),
        "9:16": (720, 1280),
    },
    "1080p": {
        "1:1": (1080, 1080),
        "4:3": (1440, 1080),
        "16:9": (1920, 1080),
        "9:16": (1080, 1920),
    },
}
WAN_FPS_VALUES = {16, 24}
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


def extension_for_mime(mime_type: str) -> str:
    return (
        IMAGE_MIME_TYPES.get(mime_type)
        or AUDIO_MIME_TYPES.get(mime_type)
        or VIDEO_MIME_TYPES.get(mime_type)
        or mimetypes.guess_extension(mime_type)
        or ".bin"
    )


def resolve_artifact_src(src: str) -> Path | None:
    if not src.startswith("/api/artifacts/"):
        return None

    artifact_path = (artifacts_root() / src.removeprefix("/api/artifacts/")).resolve()
    try:
        artifact_path.relative_to(artifacts_root())
    except ValueError:
        return None

    return artifact_path if artifact_path.is_file() else None


def append_media_path(media: dict[str, list[Path]], kind: str, path: Path | None) -> bool:
    if path is None or kind not in media:
        return False
    if path in media[kind]:
        return False
    media[kind].append(path)
    return True


def append_metadata_artifact(media: dict[str, list[Path]], snapshot: dict[str, Any]) -> bool:
    metadata = snapshot.get("metadata")
    if not isinstance(metadata, dict):
        return False

    kind = first_text(metadata.get("kind"))
    if kind not in media:
        return False

    artifact_url = first_text(metadata.get("artifactUrl"))
    return append_media_path(media, kind, resolve_artifact_src(artifact_url))


def append_local_media_references(media: dict[str, list[Path]], payload: dict[str, Any]) -> None:
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    for references in (params.get("localMediaReferences"), context.get("localMediaReferences")):
        if not isinstance(references, list):
            continue
        for reference in references:
            if not isinstance(reference, dict):
                continue
            kind = first_text(reference.get("kind"))
            if kind not in media:
                continue
            path = Path(first_text(reference.get("path"))).resolve()
            try:
                path.relative_to(artifacts_root())
            except ValueError:
                continue
            append_media_path(media, kind, path if path.is_file() else None)


def materialize_selected_media(payload: dict[str, Any], inputs_dir: Path) -> dict[str, list[Path]]:
    inputs_dir.mkdir(parents=True, exist_ok=True)
    media: dict[str, list[Path]] = {"image": [], "audio": [], "video": []}
    append_local_media_references(media, payload)

    attachments = payload.get("attachments")
    if isinstance(attachments, list):
        for attachment in attachments:
            if not isinstance(attachment, dict) or attachment.get("omitted"):
                continue
            kind = first_text(attachment.get("kind"))
            if kind not in media:
                continue
            append_media_path(media, kind, resolve_artifact_src(first_text(attachment.get("artifactUrl"), attachment.get("src"))))

    snapshots = payload.get("selectedCardSnapshots")
    if not isinstance(snapshots, list):
        return media

    for snapshot in snapshots:
        if not isinstance(snapshot, dict):
            continue

        append_metadata_artifact(media, snapshot)

        assets = snapshot.get("mediaAssets")
        if isinstance(assets, list):
            for asset in assets:
                if not isinstance(asset, dict):
                    continue
                kind = first_text(asset.get("kind"))
                if kind not in media:
                    continue
                src = first_text(asset.get("src"))
                append_media_path(media, kind, resolve_artifact_src(src))

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
    return first_text(params.get("command"), params.get("videoMode"), params.get("mode"), default)


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
        "wan-image-to-video": "wan22-i2v",
        "wan-reference-to-video": "wan22-i2v",
        "wan22-image-to-video": "wan22-i2v",
        "wan22-reference-to-video": "wan22-i2v",
        "wan-first-last-frame": "wan22-flf2v",
        "wan22-first-last-frame": "wan22-flf2v",
        "wan22-first-last-frame-to-video": "wan22-flf2v",
        "wan-sound-to-video": "wan22-s2v",
        "wan2.2-sound-to-video": "wan22-s2v",
        "wan22-sound-to-video": "wan22-s2v",
        "wan-s2v": "wan22-s2v",
        "wan2.2-s2v": "wan22-s2v",
        "sound-to-video": "wan22-s2v",
        "s2v": "wan22-s2v",
    }
    return aliases.get(normalized, normalized)


def dimensions(params: dict[str, Any]) -> tuple[int | None, int | None]:
    width = as_int(params.get("width"))
    height = as_int(params.get("height"))
    if width and height:
        return width, height
    aspect_ratio = first_text(params.get("aspectRatio"))
    return ASPECT_DIMENSIONS.get(aspect_ratio, (width, height))


def ideogram_dimensions(params: dict[str, Any]) -> tuple[int | None, int | None]:
    width = as_int(params.get("width"))
    height = as_int(params.get("height"))
    if width and height:
        return width, height
    aspect_ratio = first_text(params.get("aspectRatio"))
    return IDEOGRAM_ASPECT_DIMENSIONS.get(aspect_ratio, (width, height))


def video_dimensions(params: dict[str, Any]) -> tuple[int | None, int | None]:
    width = as_int(params.get("width"))
    height = as_int(params.get("height"))
    if width and height:
        return width, height
    aspect_ratio = first_text(params.get("aspectRatio"))
    resolution = first_text(params.get("resolution"))
    if resolution in VIDEO_RESOLUTION_DIMENSIONS and aspect_ratio in VIDEO_RESOLUTION_DIMENSIONS[resolution]:
        return VIDEO_RESOLUTION_DIMENSIONS[resolution][aspect_ratio]
    if aspect_ratio in VIDEO_BASE_DIMENSIONS:
        return VIDEO_BASE_DIMENSIONS[aspect_ratio]
    return width, height


def video_dimensions_for_resolution(params: dict[str, Any]) -> tuple[int | None, int | None]:
    aspect_ratio = first_text(params.get("aspectRatio"))
    resolution = first_text(params.get("resolution"))
    if resolution in VIDEO_RESOLUTION_DIMENSIONS and aspect_ratio in VIDEO_RESOLUTION_DIMENSIONS[resolution]:
        return VIDEO_RESOLUTION_DIMENSIONS[resolution][aspect_ratio]
    return None, None


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
        "ltx23-dasiwa": "ltx23-dasiwa-golden-lace-v3",
        "ltx23-dasiwa-golden-lace": "ltx23-dasiwa-golden-lace-v3",
        "dasiwa-golden-lace": "ltx23-dasiwa-golden-lace-v3",
        "golden-lace": "ltx23-dasiwa-golden-lace-v3",
        "seedance": "seedance2-api",
        "seedance2": "seedance2-api",
        "seedance-2": "seedance2-api",
        "seedance-2.0": "seedance2-api",
        "wan": "wan22-i2v",
        "wan2.2": "wan22-i2v",
        "wan-2.2": "wan22-i2v",
        "wan22": "wan22-i2v",
        "wan-normal": "wan22-i2v",
        "wan22-normal": "wan22-i2v",
        "wan-s2v": "wan22-s2v",
        "wan2.2-s2v": "wan22-s2v",
        "wan22-s2v": "wan22-s2v",
        "wan-sound-to-video": "wan22-s2v",
        "wan22-sound-to-video": "wan22-s2v",
        "dasiwa": "wan22-dasiwa-tastysin-i2v",
        "dasiwa-tastysin": "wan22-dasiwa-tastysin-i2v",
        "tastysin": "wan22-dasiwa-tastysin-i2v",
        "dasiwa-boundbite": "wan22-dasiwa-boundbite-i2v",
        "boundbite": "wan22-dasiwa-boundbite-i2v",
        "dasiwa-s2v": "wan22-dasiwa-littledemon-v2-s2v",
        "dasiwa-littledemon": "wan22-dasiwa-littledemon-v2-s2v",
        "dasiwa-littledemon-v2": "wan22-dasiwa-littledemon-v2-s2v",
        "littledemon": "wan22-dasiwa-littledemon-v2-s2v",
        "littledemon-v2": "wan22-dasiwa-littledemon-v2-s2v",
    }
    return aliases.get(value, value)


def is_wan22_s2v_profile(model_profile: str) -> bool:
    return model_profile in {
        "wan22-s2v",
        "wan22-dasiwa-littledemon-v2-s2v",
    }


def is_wan22_profile(model_profile: str) -> bool:
    return model_profile in {
        "wan22-i2v",
        "wan22-dasiwa-tastysin-i2v",
        "wan22-dasiwa-boundbite-i2v",
    } or is_wan22_s2v_profile(model_profile)


def video_mode_for_profile(mode: str, model_profile: str, media: dict[str, list[Path]]) -> str:
    if is_wan22_profile(model_profile):
        if mode == "wan22-s2v" or is_wan22_s2v_profile(model_profile):
            return "wan22-s2v"
        if mode == "wan22-flf2v" or mode == "flf2v" or len(media.get("image", [])) >= 2:
            return "wan22-flf2v"
        return "wan22-i2v"
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


def default_video_fps(mode: str) -> int:
    return 16 if mode.startswith("wan22-") else 24


def wan_fps(value: object) -> int:
    if value is None or value == "":
        return 16
    fps = as_int(value)
    if fps is None or fps not in WAN_FPS_VALUES:
        raise RuntimeError("WAN FPS must be 16 or 24.")
    return fps


def video_fps_for_params(mode: str, params: dict[str, Any]) -> int:
    if mode.startswith("wan22-"):
        return wan_fps(params.get("fps"))
    return as_int(params.get("fps")) or default_video_fps(mode)


def video_length_from_duration(mode: str, duration: int, fps: int) -> int:
    if mode.startswith("wan22-"):
        return duration * fps + 1
    return duration * fps


def format_seconds(value: float) -> str:
    rounded = math.ceil(value * 1000) / 1000
    return f"{rounded:.3f}".rstrip("0").rstrip(".")


def audio_duration_seconds(path: str | Path) -> float:
    if shutil.which("ffprobe") is None:
        raise RuntimeError("ffprobe is required to measure audio duration for comfy-s2vidgen.")

    process = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if process.returncode != 0:
        message = process.stderr.strip() or process.stdout.strip() or "Could not read audio duration"
        raise RuntimeError(message)

    try:
        duration = float(process.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError) as exc:
        raise RuntimeError(f"Could not parse audio duration for {path}") from exc
    if duration <= 0:
        raise RuntimeError(f"Audio duration must be positive for {path}")
    return duration


def divisible_by_16(value: int) -> int:
    lower = max(16, value - (value % 16))
    upper = lower if value % 16 == 0 else lower + 16
    return lower if abs(value - lower) <= abs(upper - value) else upper


def image_dimensions(path: Path | None) -> tuple[int | None, int | None]:
    if path is None or Image is None:
        return None, None
    try:
        with Image.open(path) as image:
            return image.size
    except Exception:
        return None, None


def half_scale_image_input(path: Path, inputs_dir: Path, label: str) -> Path:
    if Image is None:
        raise RuntimeError("Pillow is required to resize LTX image inputs.")
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
    if mode.startswith(("seedance2-", "wan22-")) or mode not in {"i2v", "ia2av", "flf2v", "motion-track"}:
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


def storyboard_image_segments(mode: str, images: list[Path]) -> list[tuple[Path, Path | None]]:
    if not mode.endswith("flf2v"):
        return [(image, None) for image in images]
    if not images:
        return []
    if len(images) == 1:
        return [(images[0], images[0])]

    segments: list[tuple[Path, Path | None]] = []
    for index in range(0, len(images), 2):
        first = images[index]
        last = images[index + 1] if index + 1 < len(images) else first
        segments.append((first, last))
    return segments


def imagegen_capability(mode: str) -> str:
    return {
        "generate": "imagegen.generate",
        "edit": "imagegen.edit",
        "upscale": "imagegen.upscale",
        "grok-generate": "imagegen.grok-generate",
        "grok-edit": "imagegen.grok-edit",
    }.get(mode, f"imagegen.{mode}")


def videogen_capability(mode: str) -> str:
    return f"videogen.{mode}"


def command_without_options(command: list[str], option_names: set[str]) -> list[str]:
    result: list[str] = []
    skip_next = False
    for index, token in enumerate(command):
        if skip_next:
            skip_next = False
            continue
        if token in option_names:
            if index + 1 < len(command) and not command[index + 1].startswith("--"):
                skip_next = True
            continue
        result.append(token)
    return result


def storyboard_commands(
    command: list[str],
    cwd: Path,
    mode: str,
    out_dir: Path,
    media: dict[str, list[Path]],
) -> list[tuple[list[str], Path]]:
    if mode not in {"i2v", "flf2v", "wan22-i2v", "wan22-flf2v", "seedance2-r2v", "seedance2-flf2v"}:
        return [(command, cwd)]

    images = media.get("image", [])
    segments = storyboard_image_segments(mode, images)
    if len(segments) <= 1:
        return [(command, cwd)]

    base = command_without_options(command, {"--input", "--first", "--last", "--out"})
    commands: list[tuple[list[str], Path]] = []
    for index, (first, last) in enumerate(segments, start=1):
        segment_out = out_dir / f"storyboard-{index:02d}"
        segment_command = [*base, "--out", str(segment_out)]
        if mode.endswith("flf2v"):
            segment_command.extend(["--first", str(first), "--last", str(last or first)])
        else:
            segment_command.extend(["--input", str(first)])
        commands.append((segment_command, cwd))
    return commands


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


def lora_architecture_for_profile(model_profile: str) -> str:
    if is_anima_profile(model_profile):
        return "anima"
    if model_profile in {"ltx23-10eros", "ltx23-dasiwa-golden-lace-v3"}:
        return "ltx23"
    if is_wan22_profile(model_profile):
        return "wan22"
    if model_profile == "qwen-edit2511":
        return "qwen-image-edit"
    if model_profile == "flux-klein-9b-snofs":
        return "flux-klein"
    return ""


def first_scalar_text(*values: object) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (int, float)):
            return str(value)
    return ""


def extra_lora_value_from_raw(raw: object) -> str:
    if isinstance(raw, dict):
        path = first_text(raw.get("path"), raw.get("name"), raw.get("file"))
        if not path:
            return ""
        model_strength = first_scalar_text(raw.get("modelStrength"), raw.get("model_strength"), raw.get("strength"))
        clip_strength = first_scalar_text(raw.get("clipStrength"), raw.get("clip_strength"))
        if model_strength:
            path = f"{path}:{model_strength}"
            if clip_strength:
                path = f"{path}:{clip_strength}"
        return path
    return first_text(raw)


def extra_lora_values_from_keys(params: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    values: list[str] = []
    for key in keys:
        raw = params.get(key)
        if isinstance(raw, list):
            values.extend(extra_lora_value_from_raw(value) for value in raw)
        else:
            values.append(extra_lora_value_from_raw(raw))
    return [value for value in values if value]


def extra_lora_values(params: dict[str, Any]) -> list[str]:
    return extra_lora_values_from_keys(
        params,
        ("extraLora", "extra_lora", "extraLoras", "extra_loras", "lora", "loras"),
    )


def resolve_extra_lora(value: str, architecture: str) -> str:
    lora_path, separator, strengths = value.partition(":")
    path = Path(lora_path).expanduser()
    suffix = f"{separator}{strengths}" if separator else ""
    if path.is_absolute():
        return value
    if path.parent != Path("."):
        candidates = [repo_root() / path, models_dir() / path]
        if path.parts and path.parts[0] == "loras":
            candidates = [models_dir() / path, repo_root() / path]
        for candidate in candidates:
            if candidate.is_file():
                return f"{candidate}{suffix}"
        return value

    search_dirs = []
    if architecture:
        search_dirs.append(models_dir() / "loras" / architecture)
    search_dirs.append(models_dir() / "loras")

    normalized_name = lora_path.lower().replace("_", "-").replace(" ", "-")
    matches: list[Path] = []
    for search_dir in search_dirs:
        if not search_dir.is_dir():
            continue
        candidates = sorted(search_dir.glob("*.safetensors"))
        exact_names = {normalized_name, f"{normalized_name}.safetensors"}
        for candidate in candidates:
            candidate_key = candidate.name.lower().replace("_", "-").replace(" ", "-")
            candidate_stem = candidate.stem.lower().replace("_", "-").replace(" ", "-")
            if candidate_key in exact_names or candidate_stem == normalized_name:
                return f"{candidate}{suffix}"
        matches.extend(
            candidate
            for candidate in candidates
            if normalized_name in candidate.stem.lower().replace("_", "-").replace(" ", "-")
        )

    if matches:
        return f"{matches[0]}{suffix}"
    return value


def append_extra_loras(command: list[str], params: dict[str, Any], model_profile: str) -> None:
    architecture = lora_architecture_for_profile(model_profile)
    for value in extra_lora_values(params):
        command.extend(["--extra-lora", resolve_extra_lora(value, architecture)])


def append_wan_video_loras(command: list[str], params: dict[str, Any], model_profile: str) -> None:
    architecture = lora_architecture_for_profile(model_profile)
    for value in extra_lora_values(params):
        command.extend(["--extra-lora", resolve_extra_lora(value, architecture)])
    for value in extra_lora_values_from_keys(
        params,
        ("extraLoraHigh", "extra_lora_high", "extraLorasHigh", "extra_loras_high", "loraHigh", "lora_high"),
    ):
        command.extend(["--extra-lora-high", resolve_extra_lora(value, architecture)])
    for value in extra_lora_values_from_keys(
        params,
        ("extraLoraLow", "extra_lora_low", "extraLorasLow", "extra_loras_low", "loraLow", "lora_low"),
    ):
        command.extend(["--extra-lora-low", resolve_extra_lora(value, architecture)])


def append_wan_s2v_lora(command: list[str], params: dict[str, Any], model_profile: str) -> None:
    loras = extra_lora_values(params)
    if not loras:
        return
    if len(loras) > 1:
        raise RuntimeError("WAN S2V accepts only one LoRA. Use a single params.extraLora value.")

    resolved = resolve_extra_lora(loras[0], lora_architecture_for_profile(model_profile))
    lora_path, _separator, strengths = resolved.partition(":")
    command.extend(["--lora", lora_path])
    model_strength = strengths.split(":", 1)[0] if strengths else first_scalar_text(
        params.get("loraStrength"),
        params.get("lora_strength"),
    )
    if model_strength:
        command.extend(["--lora-strength", model_strength])


def normalize_ideogram_mode(value: str) -> str:
    normalized = value.strip().lower().replace("_", "-")
    aliases = {
        "text-to-image": "t2i",
        "txt2img": "t2i",
        "reference-to-image": "r2i",
        "ref-to-image": "r2i",
        "reference-image": "r2i",
        "reference-image-to-image": "r2i",
    }
    return aliases.get(normalized, normalized)


def normalize_ideogram_quality(value: str) -> str:
    normalized = value.strip().lower().replace("_", "-")
    aliases = {
        "v4-quality-48": "quality",
        "v4-default-20": "default",
        "v4-turbo-12": "turbo",
    }
    return aliases.get(normalized, normalized)


def normalize_ideogram_profile(value: str) -> str:
    normalized = value.strip().lower().replace("_", "-")
    aliases = {
        "ideogram4": "ideogram4-fp8",
        "ideogram-4": "ideogram4-fp8",
        "ideogram-v4": "ideogram4-fp8",
        "ideogram4-fp8-scaled": "ideogram4-fp8",
    }
    return aliases.get(normalized, normalized)


def text_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [first_text(item) for item in value if first_text(item)]
    text = first_text(value)
    if not text:
        return []
    return [item.strip() for item in text.split(",") if item.strip()]


def first_param_text(params: dict[str, Any], *keys: str) -> str:
    return first_text(*(params.get(key) for key in keys))


def format_bbox(value: object) -> str:
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",")]
    elif isinstance(value, list) and len(value) == 4:
        parts = [str(part).strip() for part in value]
    elif isinstance(value, tuple) and len(value) == 4:
        parts = [str(part).strip() for part in value]
    else:
        raise RuntimeError("Ideogram bbox must be a 4-item list or y_min,x_min,y_max,x_max string.")

    if len(parts) != 4:
        raise RuntimeError("Ideogram bbox must contain exactly four values: y_min,x_min,y_max,x_max.")
    try:
        numbers = [int(part) for part in parts]
    except ValueError as exc:
        raise RuntimeError("Ideogram bbox coordinates must be integers from 0 to 1000.") from exc
    y_min, x_min, y_max, x_max = numbers
    if any(number < 0 or number > 1000 for number in numbers):
        raise RuntimeError("Ideogram bbox coordinates must be within 0..1000.")
    if y_min >= y_max or x_min >= x_max:
        raise RuntimeError("Ideogram bbox must satisfy y_min < y_max and x_min < x_max.")
    return ",".join(str(number) for number in numbers)


def ideogram_object_values(params: dict[str, Any]) -> list[str]:
    raw = params.get("objects") or params.get("object")
    values = raw if isinstance(raw, list) else [raw]
    result: list[str] = []
    for value in values:
        if isinstance(value, str):
            text = value.strip()
            if text:
                result.append(text)
            continue
        if not isinstance(value, dict):
            continue
        bbox = format_bbox(value.get("bbox") or value.get("box"))
        description = first_text(value.get("description"), value.get("prompt"), value.get("label"))
        if not description:
            raise RuntimeError("Each Ideogram object requires a description.")
        result.append(f"{bbox}|{description}")
    return result


def ideogram_text_values(params: dict[str, Any]) -> list[str]:
    raw = params.get("texts") or params.get("textElements") or params.get("text")
    values = raw if isinstance(raw, list) else [raw]
    result: list[str] = []
    for value in values:
        if isinstance(value, str):
            text = value.strip()
            if text:
                result.append(text)
            continue
        if not isinstance(value, dict):
            continue
        bbox = format_bbox(value.get("bbox") or value.get("box"))
        content = first_text(value.get("text"), value.get("content"), value.get("copy"))
        description = first_text(value.get("description"), value.get("prompt"), value.get("style"))
        if not content:
            raise RuntimeError("Each Ideogram text element requires text/content.")
        if not description:
            raise RuntimeError("Each Ideogram text element requires a description.")
        result.append(f"{bbox}|{content}|{description}")
    return result


def reject_ideogram_reference_language(*values: str) -> None:
    for value in values:
        lowered = value.lower()
        for phrase in IDEOGRAM_FORBIDDEN_REFERENCE_PHRASES:
            if phrase in lowered:
                raise RuntimeError(
                    "Ideogram prompt must be a standalone visual description. "
                    f"Remove reference-language phrase: {phrase!r}."
                )


def build_ideogram4_command(
    *,
    params: dict[str, Any],
    prompt: str,
    out_dir: Path,
    media: dict[str, list[Path]],
) -> tuple[list[str], Path]:
    if not prompt:
        raise RuntimeError("ideogram4-image requires a final high-level prompt.")

    mode = normalize_ideogram_mode(first_param_text(params, "mode", "imageMode") or "t2i")
    if mode not in {"t2i", "r2i"}:
        raise RuntimeError("ideogram4-image params.mode must be t2i or r2i.")
    if mode == "r2i" and selected_input(media, "image") is None:
        raise RuntimeError("ideogram4-image r2i requires a selected or attached local image artifact.")

    aspect_ratio = first_param_text(params, "aspectRatio", "aspect_ratio")
    if not aspect_ratio:
        raise RuntimeError("ideogram4-image requires params.aspectRatio.")
    width, height = ideogram_dimensions(params)
    if not width or not height:
        raise RuntimeError(f"Unsupported Ideogram aspectRatio: {aspect_ratio}")

    quality = normalize_ideogram_quality(first_param_text(params, "qualityProfile", "quality", "preset") or "default")
    quality_profile = IDEOGRAM_QUALITY_PROFILES.get(quality)
    if quality_profile is None:
        raise RuntimeError("ideogram4-image qualityProfile must be Quality, Default, or Turbo.")

    style_aesthetics = first_param_text(params, "styleAesthetics", "style_aesthetics", "aesthetics")
    style_lighting = first_param_text(params, "styleLighting", "style_lighting", "lighting")
    style_medium = first_param_text(params, "styleMedium", "style_medium", "medium")
    style_photo = first_param_text(params, "stylePhoto", "style_photo", "photo")
    style_art_style = first_param_text(params, "styleArtStyle", "style_art_style", "artStyle", "art_style")
    background = first_param_text(params, "background")
    if not style_aesthetics or not style_lighting or not style_medium:
        raise RuntimeError("ideogram4-image requires styleAesthetics, styleLighting, and styleMedium in paramsJson.")
    if bool(style_photo) == bool(style_art_style):
        raise RuntimeError("ideogram4-image requires exactly one of stylePhoto or styleArtStyle in paramsJson.")
    if not background:
        raise RuntimeError("ideogram4-image requires background in paramsJson.")

    objects = ideogram_object_values(params)
    texts = ideogram_text_values(params)
    if not objects and not texts:
        raise RuntimeError("ideogram4-image requires at least one object or text element in paramsJson.")
    reject_ideogram_reference_language(prompt, background, *objects, *texts)

    model_profile = normalize_ideogram_profile(first_param_text(params, "modelProfile", "profile") or "ideogram4-fp8")
    if model_profile != "ideogram4-fp8":
        raise RuntimeError("ideogram4-image supports only modelProfile ideogram4-fp8.")

    command = [
        "comfy-imagegen",
        "ideogram4-generate",
        "--models-dir",
        str(models_dir()),
        "--out",
        str(out_dir),
        "--prompt",
        prompt,
        "--width",
        str(width),
        "--height",
        str(height),
        "--steps",
        str(as_int(params.get("steps")) or quality_profile["steps"]),
        "--mu",
        first_scalar_text(params.get("mu")) or str(quality_profile["mu"]),
        "--std",
        first_scalar_text(params.get("std")) or str(quality_profile["std"]),
        "--style-aesthetics",
        style_aesthetics,
        "--style-lighting",
        style_lighting,
        "--style-medium",
        style_medium,
        "--background",
        background,
        "--output-json",
        str(out_dir / "ideogram-prompt.json"),
    ]
    if style_photo:
        command.extend(["--style-photo", style_photo])
    if style_art_style:
        command.extend(["--style-art-style", style_art_style])
    for color in text_list(params.get("styleColors") or params.get("styleColor") or params.get("style_color")):
        command.extend(["--style-color", color])
    for value in objects:
        command.extend(["--object", value])
    for value in texts:
        command.extend(["--text", value])
    for key in ("cfg", "cfgOverrideValue", "cfg_override_value", "cfgOverrideStart", "cfg_override_start", "cfgOverrideEnd", "cfg_override_end", "sampler", "seed"):
        value = first_scalar_text(params.get(key))
        if value:
            cli_key = key.replace("_", "-")
            cli_key = re.sub(r"(?<!^)([A-Z])", r"-\1", cli_key).lower()
            command.extend([f"--{cli_key}", value])
    if params.get("disableCfgOverride") or params.get("disable_cfg_override"):
        command.append("--disable-cfg-override")

    cwd = write_run_comfy_config(out_dir.parent, capability="imagegen.ideogram4-generate", model_profile=model_profile)
    return command, cwd


def build_s2vidgen_command(
    *,
    params: dict[str, Any],
    prompt: str,
    out_dir: Path,
    media: dict[str, list[Path]],
) -> tuple[list[str], Path]:
    model_profile = normalize_video_model_profile(first_text(params.get("modelProfile"), params.get("profile")))
    if not is_wan22_s2v_profile(model_profile):
        raise RuntimeError("comfy-s2vidgen requires an S2V modelProfile such as wan22-s2v.")

    if not first_text(params.get("aspectRatio")):
        raise RuntimeError("comfy-s2vidgen requires params.aspectRatio. The agent must ask the user which frame to use.")
    if not first_text(params.get("resolution")):
        raise RuntimeError("comfy-s2vidgen requires params.resolution. The agent must ask the user which resolution to use.")

    image_input = first_text(params.get("inputPath")) or str(selected_input(media, "image") or "")
    if not image_input:
        raise RuntimeError("comfy-s2vidgen requires one input image from params.inputPath or a selected card snapshot.")
    audio_input = first_text(params.get("audioPath")) or str(selected_input(media, "audio") or "")
    if not audio_input:
        raise RuntimeError("comfy-s2vidgen requires one input audio clip from params.audioPath or a selected card snapshot.")

    width, height = video_dimensions_for_resolution(params)
    if not width or not height:
        raise RuntimeError("comfy-s2vidgen could not resolve video dimensions from aspectRatio and resolution.")

    fps = wan_fps(params.get("fps"))
    audio_duration = audio_duration_seconds(audio_input)
    length = max(1, math.ceil(audio_duration * fps))
    command = [
        "comfy-videogen",
        "wan22-s2v",
        "--models-dir",
        str(models_dir()),
        "--input",
        image_input,
        "--audio",
        audio_input,
        "--prompt",
        prompt,
        "--width",
        str(width),
        "--height",
        str(height),
        "--length",
        str(length),
        "--fps",
        str(fps),
        "--audio-duration",
        format_seconds(audio_duration),
        "--out",
        str(out_dir),
    ]
    append_wan_s2v_lora(command, params, model_profile)
    cwd = write_run_comfy_config(out_dir.parent, capability="videogen.wan22-s2v", model_profile=model_profile)
    return command, cwd


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
    if mode in {"generate", "edit"}:
        append_extra_loras(command, params, model_profile)

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

    if skill_id == "comfy-s2vidgen":
        return build_s2vidgen_command(params=params, prompt=prompt, out_dir=out_dir, media=media)

    if skill_id == "ideogram4-image":
        return build_ideogram4_command(params=params, prompt=prompt, out_dir=out_dir, media=media)

    if skill_id in {"comfy-videogen", "comfy-motion-track-control"}:
        has_image = selected_input(media, "image") is not None
        has_audio = selected_input(media, "audio") is not None
        default_mode = "ia2av" if has_image and has_audio else "i2v" if has_image else "t2v"
        if skill_id == "comfy-motion-track-control":
            default_mode = "motion-track"
        model_profile = normalize_video_model_profile(first_text(params.get("modelProfile"), params.get("profile")))
        if not model_profile and skill_id == "comfy-videogen":
            raise RuntimeError("comfy-videogen requires params.modelProfile. The agent must ask the user which video model to use.")
        requested_mode = normalize_video_mode(command_from_params(params, default_mode))
        if skill_id == "comfy-videogen" and (requested_mode == "wan22-s2v" or is_wan22_s2v_profile(model_profile)):
            raise RuntimeError("WAN S2V generation has moved to comfy-s2vidgen.")
        mode = requested_mode
        mode = video_mode_for_profile(mode, model_profile, media)
        cwd = write_run_comfy_config(
            out_dir.parent,
            capability=videogen_capability(mode),
            model_profile=model_profile,
        ) if model_profile else repo_root()
        command = ["comfy-videogen", mode, "--out", str(out_dir)]
        if not mode.startswith("seedance2-"):
            command.extend(["--models-dir", str(model_dir)])
        command.extend(["--prompt", prompt])
        image_input = first_text(params.get("inputPath")) or str(selected_input(media, "image") or "")
        image_input = maybe_half_scale_ltx_image_input(image_input, out_dir, mode)
        if mode in {"i2v", "ia2av", "motion-track", "seedance2-r2v", "wan22-i2v", "wan22-s2v"} and image_input:
            command.extend(["--input", image_input])
        if mode in {"flf2v", "seedance2-flf2v", "wan22-flf2v"}:
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
        if mode in {"ia2av", "wan22-s2v"} and audio_input:
            command.extend(["--audio", audio_input])
        control_video = first_text(params.get("controlVideoPath")) or str(selected_input(media, "video") or "")
        if mode == "motion-track" and control_video:
            command.extend(["--control-video", control_video])
        width, height = video_dimensions(params)
        if width and height and not mode.startswith("seedance2-"):
            command.extend(["--width", str(width), "--height", str(height)])
        if first_text(params.get("aspectRatio")) and mode.startswith("seedance2-"):
            command.extend(["--ratio", first_text(params.get("aspectRatio"))])
        if first_text(params.get("resolution")) and mode.startswith("seedance2-"):
            command.extend(["--resolution", first_text(params.get("resolution"))])
        duration = as_int(params.get("duration"))
        if duration is not None:
            if mode.startswith("seedance2-"):
                command.extend(["--duration", str(duration)])
            elif as_int(params.get("length")) is None:
                fps = video_fps_for_params(mode, params)
                length = video_length_from_duration(mode, duration, fps)
                command.extend(["--length", str(length)])
        if mode in {"wan22-i2v", "wan22-flf2v"}:
            command.extend(["--fps", str(wan_fps(params.get("fps")))])
        for key in ("length", "fps", "duration", "seed"):
            value = as_int(params.get(key))
            if key == "duration" and duration is not None:
                continue
            if key == "fps" and mode in {"wan22-i2v", "wan22-flf2v"}:
                continue
            if value is not None:
                command.extend([f"--{key}", str(value)])
        if mode in {"wan22-i2v", "wan22-flf2v"}:
            for key, cli_key in (
                ("highNoiseSteps", "high-steps"),
                ("highSteps", "high-steps"),
                ("high_steps", "high-steps"),
                ("lowNoiseSteps", "low-steps"),
                ("lowSteps", "low-steps"),
                ("low_steps", "low-steps"),
            ):
                value = as_int(params.get(key))
                if value is not None:
                    command.extend([f"--{cli_key}", str(value)])
            append_wan_video_loras(command, params, model_profile)
        return command, cwd

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
    timeout_seconds = int(os.environ.get("LOKI_COMFY_TIMEOUT_SECONDS", "0"))
    process = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout_seconds if timeout_seconds > 0 else None,
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


def value_after_option(command: list[str], option: str) -> str:
    try:
        index = command.index(option)
    except ValueError:
        return ""
    if index + 1 >= len(command):
        return ""
    return command[index + 1]


def prompt_from_cli_payload(payload: dict[str, Any], command: list[str], fallback: str) -> str:
    prompt_json_path = first_text(
        payload.get("prompt_json"),
        payload.get("promptJson"),
        value_after_option(command, "--output-json"),
    )
    if not prompt_json_path:
        return fallback

    path = Path(prompt_json_path)
    if not path.is_file():
        return fallback

    try:
        return path.read_text(encoding="utf-8").strip() or fallback
    except OSError:
        return fallback


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
        artifact_prompt = prompt_from_cli_payload(payload, command, prompt)
        return {
            "artifacts": [
                {
                    "path": str(path),
                    "kind": artifact_kind(payload),
                    "title": first_text(payload.get("title"), payload.get("mode"), "Comfy artifact"),
                    "prompt": artifact_prompt,
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


def combine_raw_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    combined: dict[str, Any] = {
        "artifacts": [],
        "diagnostics": [],
        "cards": [],
    }
    for result in results:
        for key in ("artifacts", "diagnostics", "cards"):
            values = result.get(key)
            if isinstance(values, list):
                combined[key].extend(values)
        for key in ("html", "text"):
            value = result.get(key)
            if value:
                existing = first_text(combined.get(key))
                combined[key] = f"{existing}\n\n{value}".strip() if existing else value

    return {key: value for key, value in combined.items() if value}


def annotate_storyboard_raw_result(
    raw: dict[str, Any],
    *,
    segment_index: int,
    segment_count: int,
    source_images: tuple[Path, Path | None],
) -> None:
    for artifact in raw.get("artifacts", []):
        if not isinstance(artifact, dict):
            continue
        metadata = artifact.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
            artifact["metadata"] = metadata
        metadata["storyboard"] = {
            "segmentIndex": segment_index,
            "segmentCount": segment_count,
            "sourceImages": [str(image) for image in source_images if image is not None],
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
    commands = storyboard_commands(command, cwd, command[1] if len(command) > 1 else "", run_dir, input_media)
    if shutil.which(command[0]) is None:
        raise RuntimeError(
            f"Comfy CLI not found: {command[0]}. Install with `uv tool install git+https://github.com/quinteroac/comfy-agent-tools`."
        )
    results: list[dict[str, Any]] = []
    segments = storyboard_image_segments(command[1] if len(command) > 1 else "", input_media.get("image", []))

    for index, (segment_command, segment_cwd) in enumerate(commands, start=1):
        result = run_command(segment_command, segment_cwd)
        raw = raw_result_from_cli(result, segment_command, prompt_from_command(segment_command, base_prompt(payload)))
        if len(segments) == len(commands):
            annotate_storyboard_raw_result(
                raw,
                segment_index=index,
                segment_count=len(commands),
                source_images=segments[index - 1],
            )
        for artifact in raw.get("artifacts", []):
            if isinstance(artifact, dict):
                artifact["title"] = f"{first_text(artifact.get('title'), 'Comfy video')} {index}" if len(commands) > 1 else artifact.get("title")
        if len(commands) > 1:
            print(f"__LOKI_PARTIAL_RESULT__{json.dumps(raw)}", flush=True)
        results.append(raw)
    if len(commands) > 1:
        print(json.dumps({
            "diagnostics": [{
                "level": "info",
                "title": "Storyboard video generation completed",
                "message": f"Generated {len(commands)} storyboard video segment(s).",
            }]
        }))
    else:
        print(json.dumps(combine_raw_results(results)))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"comfy action failed: {exc}", file=sys.stderr)
        sys.exit(1)
