import base64
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from PIL import Image


SKILL_ID = "imagegen"
SUPPORTED_IMAGE_MIME_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
RESOLUTION_VALUES = {
    "1024x1024": (1024, 1024),
    "1536x1024": (1536, 1024),
    "1024x1536": (1024, 1536),
    "2048x2048": (2048, 2048),
    "2048x1152": (2048, 1152),
    "3840x2160": (3840, 2160),
    "2160x3840": (2160, 3840),
    "auto": None,
}


def read_payload() -> dict:
    raw_payload = sys.stdin.read()
    if not raw_payload.strip():
        return {}
    return json.loads(raw_payload)


def first_text(*values: object) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def artifacts_root() -> Path:
    return Path(os.environ.get("LOKI_ARTIFACTS_ROOT", repo_root() / ".loki")).resolve()


def safe_slug(value: str, fallback: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-")
    return slug[:80] or fallback


def parse_data_url(data_url: str) -> tuple[str, bytes]:
    header, separator, encoded = data_url.partition(",")
    if separator != "," or not header.startswith("data:"):
        raise ValueError("invalid data URL")

    mime_type = header[5:].split(";", 1)[0] or "application/octet-stream"
    if ";base64" not in header:
        raise ValueError("only base64 data URLs are supported")

    return mime_type, base64.b64decode(encoded)


def extension_for_mime_type(mime_type: str) -> str:
    if mime_type in SUPPORTED_IMAGE_MIME_TYPES:
        return SUPPORTED_IMAGE_MIME_TYPES[mime_type]
    return mimetypes.guess_extension(mime_type) or ".bin"


def write_data_url_image(data_url: str, destination: Path) -> Path | None:
    mime_type, data = parse_data_url(data_url)
    if mime_type not in SUPPORTED_IMAGE_MIME_TYPES:
        return None

    destination = destination.with_suffix(extension_for_mime_type(mime_type))
    destination.write_bytes(data)
    return destination


def resolve_artifact_src(src: str) -> Path | None:
    if not src.startswith("/api/artifacts/"):
        return None

    artifact_path = (artifacts_root() / src.removeprefix("/api/artifacts/")).resolve()
    try:
        artifact_path.relative_to(artifacts_root())
    except ValueError:
        return None

    return artifact_path if artifact_path.is_file() else None


def materialize_selected_images(payload: dict, inputs_dir: Path) -> list[Path]:
    inputs_dir.mkdir(parents=True, exist_ok=True)
    materialized: list[Path] = []
    attachments = payload.get("attachments")
    if isinstance(attachments, list):
        for attachment_index, attachment in enumerate(attachments, start=1):
            if not isinstance(attachment, dict) or attachment.get("omitted"):
                continue
            if attachment.get("kind") != "image":
                continue
            data_url = first_text(attachment.get("dataUrl"))
            if not data_url.startswith("data:image/"):
                continue
            try:
                image_path = write_data_url_image(data_url, inputs_dir / f"attachment-{attachment_index:02d}")
            except Exception:
                image_path = None
            if image_path is not None:
                materialized.append(image_path)

    snapshots = payload.get("selectedCardSnapshots")
    if not isinstance(snapshots, list):
        return materialized

    for snapshot_index, snapshot in enumerate(snapshots, start=1):
        if not isinstance(snapshot, dict):
            continue

        image_data_urls: list[str] = []
        media_assets = snapshot.get("mediaAssets")
        if isinstance(media_assets, list):
            for asset in media_assets:
                if not isinstance(asset, dict):
                    continue
                if asset.get("kind") != "image":
                    continue
                data_url = first_text(asset.get("dataUrl"), asset.get("src"))
                artifact_path = resolve_artifact_src(data_url)
                if artifact_path is not None:
                    materialized.append(artifact_path)
                elif data_url.startswith("data:image/"):
                    image_data_urls.append(data_url)

        if not image_data_urls:
            preview = snapshot.get("preview")
            if isinstance(preview, dict) and not preview.get("omitted"):
                data_url = first_text(preview.get("dataUrl"))
                if data_url.startswith("data:image/"):
                    image_data_urls.append(data_url)

        card_slug = safe_slug(first_text(snapshot.get("displayTitle"), snapshot.get("name")), f"card-{snapshot_index}")
        for image_index, data_url in enumerate(image_data_urls, start=1):
            try:
                image_path = write_data_url_image(
                    data_url,
                    inputs_dir / f"{snapshot_index:02d}-{image_index:02d}-{card_slug}",
                )
            except Exception:
                image_path = None

            if image_path is not None:
                materialized.append(image_path)

    return materialized


def write_output_schema(run_dir: Path) -> Path:
    schema_path = run_dir / "codex-output-schema.json"
    image_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["title", "prompt", "imagePath", "mimeType", "width", "height"],
        "properties": {
            "title": {"type": "string"},
            "prompt": {"type": "string"},
            "imagePath": {"type": "string"},
            "mimeType": {"type": "string"},
            "width": {"type": "integer"},
            "height": {"type": "integer"},
        },
    }
    schema_path.write_text(
        json.dumps(
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["images", "diagnostics"],
                "properties": {
                    "images": {
                        "type": "array",
                        "minItems": 1,
                        "items": image_schema,
                    },
                    "diagnostics": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["level", "title", "message"],
                            "properties": {
                                "level": {"type": "string", "enum": ["info", "warning", "error"]},
                                "title": {"type": "string"},
                                "message": {"type": "string"},
                            },
                        },
                    },
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return schema_path


NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "uno": 1,
    "dos": 2,
    "tres": 3,
    "cuatro": 4,
    "cinco": 5,
    "seis": 6,
    "siete": 7,
    "ocho": 8,
    "nueve": 9,
    "diez": 10,
}
MULTI_IMAGE_HINT_RE = re.compile(
    r"\b("
    r"multiple|several|options|variants?|storyboards?|sequence|frames?|shots?|steps?|panels?|scenes?|"
    r"varias?|varios|opciones|variantes|secuencia|fotogramas?|cuadros?|pasos?|paneles?|escenas?"
    r")\b",
    re.IGNORECASE,
)


def positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def infer_requested_image_count(prompt: str, params: dict) -> int:
    explicit_count = positive_int(params.get("imageCount"))
    if explicit_count:
        return explicit_count

    count_pattern = re.compile(
        r"\b(\d{1,2})\s*(?:images?|cards?|options?|variants?|frames?|shots?|steps?|panels?|"
        r"imagenes?|imágenes?|cards?|opciones|variantes|fotogramas?|cuadros?|pasos?|paneles?)\b",
        re.IGNORECASE,
    )
    match = count_pattern.search(prompt)
    if match:
        return int(match.group(1))

    for word, count in NUMBER_WORDS.items():
        if re.search(
            rf"\b{re.escape(word)}\s+(?:images?|cards?|options?|variants?|frames?|shots?|steps?|panels?|"
            r"imagenes?|imágenes?|cards?|opciones|variantes|fotogramas?|cuadros?|pasos?|paneles?)\b",
            prompt,
            re.IGNORECASE,
        ):
            return count

    return 4 if MULTI_IMAGE_HINT_RE.search(prompt) else 1


def extract_json_object(text: str) -> dict:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", stripped)
        if not match:
            raise
        parsed = json.loads(match.group(0))

    if not isinstance(parsed, dict):
        raise ValueError("Codex response must be a JSON object")
    return parsed


def build_codex_prompt(payload: dict, run_dir: Path, output_dir: Path, selected_images: list[Path]) -> str:
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    prompt = first_text(
        params.get("prompt"),
        params.get("skillPrompt"),
        params.get("outputText"),
        payload.get("prompt"),
    )
    title_hint = first_text(params.get("title"), params.get("name"), "Generated image")
    resolution = normalize_resolution(params.get("resolution"))
    dimensions = RESOLUTION_VALUES[resolution]
    resolution_requirement = (
        f"Prefer an output near {dimensions[0]}x{dimensions[1]} pixels when the built-in image generator supports it."
        if dimensions
        else "Let Codex choose the output dimensions that best fit the request."
    )
    retry_requirement = (
        "If the built-in image generator returns a different pixel size, accept the generated image and report its real dimensions."
        if dimensions
        else "Do not force a specific pixel size when resolution is auto."
    )

    selected_image_lines = "\n".join(f"- {path}" for path in selected_images) or "- none"
    requested_image_count = infer_requested_image_count(prompt, params)
    count_requirement = (
        f"Create exactly {requested_image_count} separate final image files for this request."
        if requested_image_count > 1
        else "Create exactly 1 final image file for this request unless the user's request explicitly requires multiple separate images."
    )

    return f"""Use the Codex imagegen skill to create the requested raster image artifact for Loki Creator.

Execution boundary:
- Use only Codex's built-in image generation/editing path provided by the imagegen skill.
- Do not use ComfyUI, comfy-agent-tools, comfy-imagegen, comfy-image-generate, comfy-image-edit, comfy-image-upscale, or any backend/skills/comfy-* skill.
- Do not read Comfy skill instructions and do not run commands whose names start with comfy-.
- If you cannot use Codex imagegen directly, fail rather than substituting a Comfy workflow.

User request:
{prompt}

Title hint:
{title_hint}

Resolution:
{resolution}

Selected image inputs available as --image attachments:
{selected_image_lines}

Output requirements:
- Use the imagegen skill's default built-in image generation/editing path unless the request explicitly requires a fallback.
- If image attachments are present, treat them as visual input from selected Loki canvas cards and edit or derive from them when the user request asks to modify selected content.
- {count_requirement}
- For storyboards, sequences, numbered lists, asset packs, frames, variants, or options, save each item as its own separate image file. Do not combine separate requested items into a collage, contact sheet, grid, comic page, or single composite unless the user explicitly asks for one combined image.
- {resolution_requirement}
- {retry_requirement}
- Do not crop, pad, stretch, upscale, downscale, or post-process the output just to fake a requested resolution.
- Save every final image file inside this directory: {output_dir}
- Use distinct descriptive filenames for each output image.
- Do not save the final image only under CODEX_HOME or another temporary location; copy or move the chosen image into the output directory above.
- Do not modify repository source files.
- Always include diagnostics. Use an empty array when there are no issues. Each diagnostic must include level, title, and message; use an empty title string if there is no concise title.
- Return only JSON matching this schema:
  {{"images":[{{"title":"short card title","prompt":"final generation/edit prompt","imagePath":"absolute path to final image","mimeType":"image/png or image/jpeg or image/webp","width":1024,"height":1024}}],"diagnostics":[]}}

Loki run directory:
{run_dir}
"""


def normalize_resolution(value: object) -> str:
    resolution = first_text(value)
    if resolution in RESOLUTION_VALUES:
        return resolution
    raise RuntimeError(
        "imagegen requires params.resolution to be one of: "
        f"{', '.join(RESOLUTION_VALUES.keys())}"
    )


def read_image_dimensions(image_path: Path) -> tuple[int | None, int | None]:
    try:
        with Image.open(image_path) as image:
            return image.size
    except Exception:
        return None, None


def resolve_codex_bin() -> str:
    configured_bin = os.environ.get("LOKI_CODEX_BIN")
    if configured_bin:
        configured_path = Path(configured_bin).expanduser()
        if shutil.which(configured_bin) or configured_path.exists():
            return str(configured_path if configured_path.exists() else configured_bin)
        raise RuntimeError(f"Codex executable not found: {configured_bin}")

    path_bin = shutil.which("codex")
    if path_bin:
        return path_bin

    home = Path.home()
    candidates = [
        *home.glob(".vscode-server/extensions/openai.chatgpt-*/bin/linux-x86_64/codex"),
        home / ".local" / "bin" / "codex",
        home / ".bun" / "bin" / "codex",
    ]
    executable_candidates = [candidate for candidate in candidates if candidate.is_file() and os.access(candidate, os.X_OK)]
    if executable_candidates:
        return str(sorted(executable_candidates)[-1])

    raise RuntimeError(
        "Codex executable not found. Set LOKI_CODEX_BIN to the absolute codex binary path "
        "or start the backend with codex available on PATH."
    )


def run_codex(payload: dict, run_dir: Path, selected_images: list[Path]) -> dict:
    codex_bin = resolve_codex_bin()

    output_dir = run_dir / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    schema_path = write_output_schema(run_dir)
    response_path = run_dir / "codex-response.json"
    prompt = build_codex_prompt(payload, run_dir, output_dir, selected_images)

    command = [
        codex_bin,
        "exec",
        "--cd",
        str(run_dir),
        "--dangerously-bypass-approvals-and-sandbox",
        "--output-schema",
        str(schema_path),
        "--output-last-message",
        str(response_path),
    ]
    for image_path in selected_images:
        command.extend(["--image", str(image_path)])
    command.append("-")

    timeout_seconds = int(os.environ.get("LOKI_IMAGEGEN_CODEX_TIMEOUT_SECONDS", "900"))
    process = subprocess.run(
        command,
        input=prompt,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    (run_dir / "codex-stdout.log").write_text(process.stdout, encoding="utf-8")
    (run_dir / "codex-stderr.log").write_text(process.stderr, encoding="utf-8")

    if process.returncode != 0:
        message = process.stderr.strip() or process.stdout.strip() or "Codex image generation failed"
        raise RuntimeError(message)
    if not response_path.is_file():
        raise RuntimeError("Codex did not write an output response file")

    return extract_json_object(response_path.read_text(encoding="utf-8"))


def validate_output_image(result: dict, run_dir: Path) -> tuple[Path, str]:
    image_path_value = first_text(result.get("imagePath"))
    if not image_path_value:
        raise RuntimeError("Codex response did not include imagePath")

    image_path = Path(image_path_value).expanduser().resolve()
    root = artifacts_root()
    try:
        image_path.relative_to(root)
    except ValueError:
        try:
            image_path.relative_to(run_dir)
        except ValueError as exc:
            raise RuntimeError("Codex imagePath must be inside the Loki artifacts directory") from exc

    if not image_path.is_file():
        raise RuntimeError(f"Codex imagePath does not exist: {image_path}")

    mime_type = first_text(result.get("mimeType")) or mimetypes.guess_type(image_path.name)[0] or "image/png"
    if not mime_type.startswith("image/"):
        raise RuntimeError(f"Codex output is not an image: {mime_type}")

    return image_path, mime_type


def normalize_codex_images(result: dict) -> list[dict]:
    images = result.get("images")
    if isinstance(images, list):
        return [image for image in images if isinstance(image, dict)]
    if first_text(result.get("imagePath")):
        return [result]
    return []


def normalize_codex_diagnostics(result: dict) -> list[dict | str]:
    diagnostics = result.get("diagnostics")
    if not isinstance(diagnostics, list):
        return []

    normalized: list[dict | str] = []
    for diagnostic in diagnostics:
        if isinstance(diagnostic, str) and diagnostic.strip():
            normalized.append(diagnostic.strip())
        elif isinstance(diagnostic, dict):
            message = first_text(diagnostic.get("message"))
            if message:
                level = first_text(diagnostic.get("level")) or "warning"
                if level not in {"info", "warning", "error"}:
                    level = "warning"
                normalized.append(
                    {
                        "level": level,
                        "title": first_text(diagnostic.get("title")) or None,
                        "message": message,
                    }
                )
    return normalized


def main() -> None:
    payload = read_payload()
    run_id = first_text(payload.get("runId"), f"skill_run_{uuid4().hex}")
    run_dir = (artifacts_root() / "skills" / SKILL_ID / safe_slug(run_id, "run")).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "request.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    selected_images = materialize_selected_images(payload, run_dir / "inputs")
    result = run_codex(payload, run_dir, selected_images)
    codex_images = normalize_codex_images(result)
    if not codex_images:
        raise RuntimeError("Codex response did not include images")

    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    resolution = normalize_resolution(params.get("resolution"))
    artifacts: list[dict] = []
    diagnostics = normalize_codex_diagnostics(result)
    image_count = len(codex_images)

    for image_index, codex_image in enumerate(codex_images, start=1):
        try:
            image_path, mime_type = validate_output_image(codex_image, run_dir)
        except Exception as error:
            diagnostics.append(
                {
                    "level": "warning",
                    "title": f"Image {image_index} skipped",
                    "message": str(error),
                    "metadata": {"imageIndex": image_index, "imageCount": image_count},
                }
            )
            continue

        width, height = read_image_dimensions(image_path)
        title = first_text(codex_image.get("title"), result.get("title"), f"Generated image {image_index}")
        final_prompt = first_text(codex_image.get("prompt"), result.get("prompt"), payload.get("prompt"))

        metadata = {
            "resolution": resolution,
            "requestedResolution": resolution,
            "imageIndex": image_index,
            "imageCount": image_count,
            "tags": ["imagegen"],
            "capabilities": ["image-generation", "image-editing"],
        }
        if width:
            metadata["width"] = width
        if height:
            metadata["height"] = height

        artifacts.append(
            {
                "path": str(image_path),
                "kind": "image",
                "mimeType": mime_type,
                "title": title,
                "prompt": final_prompt,
                "metadata": metadata,
            }
        )

    if not artifacts:
        details = "; ".join(
            diagnostic["message"] for diagnostic in diagnostics if isinstance(diagnostic, dict) and diagnostic.get("message")
        )
        raise RuntimeError(f"Codex did not produce any valid image artifacts{': ' + details if details else ''}")

    print(json.dumps({"artifacts": artifacts, "diagnostics": diagnostics}))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"imagegen action failed: {error}", file=sys.stderr)
        sys.exit(1)
