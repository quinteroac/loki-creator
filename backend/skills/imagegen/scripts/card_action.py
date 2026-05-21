import base64
import html
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from PIL import Image


SKILL_ID = "imagegen"
SOURCE_ACTION_ID = "codex-imagegen"
SUPPORTED_IMAGE_MIME_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
ASPECT_RATIO_VALUES = {
    "1:1": 1 / 1,
    "4:3": 4 / 3,
    "16:9": 16 / 9,
    "9:16": 9 / 16,
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


def materialize_selected_images(payload: dict, inputs_dir: Path) -> list[Path]:
    inputs_dir.mkdir(parents=True, exist_ok=True)
    materialized: list[Path] = []
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
                if data_url.startswith("data:image/"):
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
    schema_path.write_text(
        json.dumps(
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["title", "prompt", "imagePath", "mimeType"],
                "properties": {
                    "title": {"type": "string"},
                    "prompt": {"type": "string"},
                    "imagePath": {"type": "string"},
                    "mimeType": {"type": "string"},
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return schema_path


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
    aspect_ratio = normalize_aspect_ratio(params.get("aspectRatio"))

    selected_image_lines = "\n".join(f"- {path}" for path in selected_images) or "- none"

    return f"""Use the Codex imagegen skill to create the requested raster image artifact for Loki Creator.

User request:
{prompt}

Title hint:
{title_hint}

Aspect ratio:
{aspect_ratio}

Selected image inputs available as --image attachments:
{selected_image_lines}

Output requirements:
- Use the imagegen skill's default built-in image generation/editing path unless the request explicitly requires a fallback.
- If image attachments are present, treat them as visual input from selected Loki canvas cards and edit or derive from them when the user request asks to modify selected content.
- The final generated image file itself must have aspect ratio {aspect_ratio}. This is a hard requirement.
- If an attempt returns the wrong aspect ratio, regenerate with the requested aspect ratio before choosing the final image.
- Do not crop, pad, stretch, or post-process an incorrectly shaped output to fake the requested aspect ratio.
- Save exactly one final image file inside this directory: {output_dir}
- Do not save the final image only under CODEX_HOME or another temporary location.
- Do not modify repository source files.
- Return only JSON matching this schema:
  {{"title":"short card title","prompt":"final generation/edit prompt","imagePath":"absolute path to final image","mimeType":"image/png or image/jpeg or image/webp"}}

Loki run directory:
{run_dir}
"""


def normalize_aspect_ratio(value: object) -> str:
    aspect_ratio = first_text(value)
    return aspect_ratio if aspect_ratio in ASPECT_RATIO_VALUES else "1:1"


def validate_output_aspect_ratio(image_path: Path, aspect_ratio: str) -> None:
    target_ratio = ASPECT_RATIO_VALUES.get(aspect_ratio)
    if target_ratio is None:
        return

    with Image.open(image_path) as image:
        width, height = image.size
        if width <= 0 or height <= 0:
            return

        current_ratio = width / height
        if abs(current_ratio - target_ratio) / target_ratio <= 0.025:
            return

    raise RuntimeError(
        f"Codex returned an image with aspect ratio {width}:{height}, "
        f"but Loki requested {aspect_ratio}. Regenerate with the requested aspect ratio; "
        "do not crop, pad, or post-process an incorrect output."
    )


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
        str(repo_root()),
        "--dangerously-bypass-approvals-and-sandbox",
        "--output-schema",
        str(schema_path),
        "--output-last-message",
        str(response_path),
    ]
    for image_path in selected_images:
        command.extend(["--image", str(image_path)])
    command.append(prompt)

    timeout_seconds = int(os.environ.get("LOKI_IMAGEGEN_CODEX_TIMEOUT_SECONDS", "900"))
    process = subprocess.run(
        command,
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


def create_card_html(artifact_url: str, title: str) -> str:
    escaped_url = html.escape(artifact_url, quote=True)
    escaped_title = html.escape(title)
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <style>
      html,
      body {{
        width: 100%;
        height: 100%;
        margin: 0;
        background: #111111;
      }}
      body {{
        display: grid;
        place-items: center;
        overflow: hidden;
      }}
      img {{
        display: block;
        width: 100%;
        height: 100%;
        object-fit: contain;
        background: #111111;
      }}
    </style>
  </head>
  <body>
    <img src="{escaped_url}" alt="{escaped_title}" />
  </body>
</html>"""


def main() -> None:
    payload = read_payload()
    run_id = first_text(payload.get("runId"), f"skill_run_{uuid4().hex}")
    run_dir = (artifacts_root() / "skills" / SKILL_ID / safe_slug(run_id, "run")).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "request.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    selected_images = materialize_selected_images(payload, run_dir / "inputs")
    result = run_codex(payload, run_dir, selected_images)
    image_path, mime_type = validate_output_image(result, run_dir)
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    aspect_ratio = normalize_aspect_ratio(params.get("aspectRatio"))
    validate_output_aspect_ratio(image_path, aspect_ratio)
    artifact_path = image_path.relative_to(artifacts_root()).as_posix()
    title = first_text(result.get("title"), "Generated image")
    final_prompt = first_text(result.get("prompt"), payload.get("prompt"))

    card = {
        "id": f"card_{uuid4().hex}",
        "name": title,
        "prompt": final_prompt,
        "html": create_card_html(f"/api/artifacts/{artifact_path}", title),
        "sourceSkillId": SKILL_ID,
        "sourceActionId": SOURCE_ACTION_ID,
        "metadata": {
            "kind": "image",
            "title": title,
            "description": final_prompt,
            "artifactUrl": f"/api/artifacts/{artifact_path}",
            "thumbnailUrl": f"/api/artifacts/{artifact_path}",
            "preferredAspectRatio": aspect_ratio,
            "aspectRatio": aspect_ratio,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "tags": ["imagegen"],
            "capabilities": ["image-generation", "image-editing"],
        },
    }
    print(json.dumps({"cards": [card]}))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"imagegen action failed: {error}", file=sys.stderr)
        sys.exit(1)
