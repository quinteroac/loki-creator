from __future__ import annotations

import html
import json
import mimetypes
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4


SKILL_ID = "hyperframes-text-video"
HYPERFRAMES_VERSION = "0.6.79"
IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
VIDEO_MIME_TYPES = {"video/mp4", "video/webm", "video/quicktime", "video/x-matroska"}
VIDEO_RESOLUTION_DIMENSIONS = {
    "480p": {
        "16:9": (848, 480),
        "9:16": (480, 848),
        "1:1": (480, 480),
    },
    "720p": {
        "16:9": (1280, 720),
        "9:16": (720, 1280),
        "1:1": (720, 720),
    },
}
BLOCK_KINDS = {"title", "subtitle", "lowerThird", "quote", "cta"}
PRESETS = {"title-card", "lower-third", "karaoke-subtitle", "quote", "caption-stack", "cta"}
POSITIONS = {"center", "top", "bottom", "lower-left", "lower-right"}
DEFAULT_PRESET_BY_KIND = {
    "title": "title-card",
    "subtitle": "karaoke-subtitle",
    "lowerThird": "lower-third",
    "quote": "quote",
    "cta": "cta",
}
DEFAULT_POSITION_BY_PRESET = {
    "title-card": "center",
    "lower-third": "lower-left",
    "karaoke-subtitle": "bottom",
    "quote": "center",
    "caption-stack": "bottom",
    "cta": "bottom",
}


def read_payload() -> dict[str, Any]:
    raw = sys.stdin.read()
    return json.loads(raw) if raw.strip() else {}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def artifacts_root() -> Path:
    return Path(os.environ.get("LOKI_ARTIFACTS_ROOT", repo_root() / ".loki")).resolve()


def first_text(*values: object) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def safe_slug(value: str, fallback: str) -> str:
    slug = "".join(character if character.isalnum() or character in {"-", "_"} else "-" for character in value.lower())
    slug = "-".join(part for part in slug.split("-") if part)
    return slug[:80] or fallback


def output_dir(payload: dict[str, Any]) -> Path:
    run_id = first_text(payload.get("runId"), f"skill_run_{uuid4().hex}")
    skill_id = first_text(payload.get("skillId"), SKILL_ID)
    path = artifacts_root() / "skills" / skill_id / safe_slug(run_id, "run") / "outputs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_root(outputs: Path) -> Path:
    return outputs.parent


def parse_duration(value: object) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def parse_fps(value: object) -> float | None:
    if not isinstance(value, str) or not value or value == "0/0":
        return None
    numerator, separator, denominator = value.partition("/")
    try:
        parsed = float(numerator) / float(denominator) if separator else float(value)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    return parsed if parsed > 0 else None


def first_stream(probe: dict[str, Any], codec_type: str) -> dict[str, Any] | None:
    streams = probe.get("streams")
    if not isinstance(streams, list):
        return None
    for stream in streams:
        if isinstance(stream, dict) and stream.get("codec_type") == codec_type:
            return stream
    return None


def ffprobe(path: Path) -> dict[str, Any]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        str(path),
    ]
    process = subprocess.run(command, text=True, capture_output=True, check=False)
    if process.returncode != 0:
        message = process.stderr.strip() or process.stdout.strip() or "ffprobe failed"
        raise RuntimeError(f"Could not inspect media {path}: {message}")
    return json.loads(process.stdout or "{}")


def video_info(path: Path) -> dict[str, Any]:
    probe = ffprobe(path)
    video_stream = first_stream(probe, "video")
    if video_stream is None:
        raise RuntimeError(f"Selected artifact is not a video: {path}")

    format_info = probe.get("format") if isinstance(probe.get("format"), dict) else {}
    duration = parse_duration(video_stream.get("duration")) or parse_duration(format_info.get("duration"))
    fps = parse_fps(video_stream.get("avg_frame_rate")) or parse_fps(video_stream.get("r_frame_rate"))
    width = int(video_stream.get("width") or 0)
    height = int(video_stream.get("height") or 0)
    if duration is None:
        raise RuntimeError(f"Could not read video duration: {path}")
    if fps is None:
        fps = 30.0
    if width <= 0 or height <= 0:
        raise RuntimeError(f"Could not read video dimensions: {path}")
    return {
        "duration": duration,
        "fps": fps,
        "width": width,
        "height": height,
        "hasAudio": first_stream(probe, "audio") is not None,
    }


def image_info(path: Path) -> dict[str, Any]:
    try:
        from PIL import Image
    except ModuleNotFoundError as exc:
        raise RuntimeError("Pillow is required to inspect image backgrounds.") from exc

    with Image.open(path) as image:
        width, height = image.size
    if width <= 0 or height <= 0:
        raise RuntimeError(f"Could not read image dimensions: {path}")
    return {"width": width, "height": height}


def require_tools() -> None:
    missing = [tool for tool in ("npx", "ffmpeg", "ffprobe") if shutil.which(tool) is None]
    if missing:
        raise RuntimeError(f"Missing required tool(s): {', '.join(missing)}")


def run_command(command: list[str], *, cwd: Path | None = None) -> None:
    process = subprocess.run(command, text=True, capture_output=True, check=False, cwd=cwd)
    if process.returncode != 0:
        message = process.stderr.strip() or process.stdout.strip() or "command failed"
        raise RuntimeError(f"{command[0]} failed: {message[-2000:]}")


def resolve_artifact_src(src: str) -> Path | None:
    if not src.startswith("/api/artifacts/"):
        return None
    artifact_path = (artifacts_root() / src.removeprefix("/api/artifacts/")).resolve()
    try:
        artifact_path.relative_to(artifacts_root())
    except ValueError:
        return None
    return artifact_path if artifact_path.is_file() else None


def local_artifact_path(source: str) -> Path:
    if source.startswith("data:"):
        raise RuntimeError("HyperFrames background must be a local Loki artifact; inline dataUrl is not executable media input.")

    artifact_path = resolve_artifact_src(source)
    if artifact_path is not None:
        return artifact_path

    path = Path(source).expanduser().resolve()
    try:
        path.relative_to(artifacts_root())
    except ValueError as exc:
        raise RuntimeError(f"HyperFrames background must be a local Loki artifact, got: {source[:80]}") from exc
    if not path.is_file():
        raise RuntimeError(f"HyperFrames background path does not exist: {path}")
    return path


def media_kind_for(path: Path, declared_kind: str = "", mime_type: str = "") -> str:
    if declared_kind in {"image", "video"}:
        return declared_kind
    guessed = mime_type or mimetypes.guess_type(path.name)[0] or ""
    if guessed in IMAGE_MIME_TYPES or guessed.startswith("image/"):
        return "image"
    if guessed in VIDEO_MIME_TYPES or guessed.startswith("video/"):
        return "video"
    raise RuntimeError(f"Selected artifact is not a supported image or video: {path.name}")


def append_candidate(candidates: list[tuple[Path, str]], source: str, declared_kind: str = "", mime_type: str = "") -> None:
    path = local_artifact_path(source)
    kind = media_kind_for(path, declared_kind, mime_type)
    candidate = (path, kind)
    if candidate not in candidates:
        candidates.append(candidate)


def append_from_asset(candidates: list[tuple[Path, str]], asset: dict[str, Any]) -> None:
    kind = first_text(asset.get("kind"))
    mime_type = first_text(asset.get("mimeType"))
    if kind not in {"image", "video", "source"} and not mime_type.startswith(("image/", "video/")):
        return
    source = first_text(asset.get("src"), asset.get("artifactUrl"))
    if source:
        append_candidate(candidates, source, kind if kind in {"image", "video"} else "", mime_type)
        return
    if first_text(asset.get("dataUrl"), asset.get("preview")):
        raise RuntimeError("HyperFrames background must be a local Loki artifact; preview/dataUrl media is not executable input.")


def selected_background(payload: dict[str, Any]) -> tuple[Path, str]:
    candidates: list[tuple[Path, str]] = []
    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    references = context.get("localMediaReferences")
    if isinstance(references, list):
        for reference in references:
            if not isinstance(reference, dict):
                continue
            kind = first_text(reference.get("kind"))
            if kind not in {"image", "video"}:
                continue
            source = first_text(reference.get("path"), reference.get("artifactUrl"))
            if source:
                append_candidate(candidates, source, kind)

    snapshots = payload.get("selectedCardSnapshots")
    if isinstance(snapshots, list):
        for snapshot in snapshots:
            if not isinstance(snapshot, dict):
                continue
            assets = snapshot.get("mediaAssets")
            if isinstance(assets, list):
                for asset in assets:
                    if isinstance(asset, dict) and not asset.get("omitted"):
                        append_from_asset(candidates, asset)
            metadata = snapshot.get("metadata")
            if isinstance(metadata, dict):
                kind = first_text(metadata.get("kind"))
                if kind in {"image", "video"}:
                    source = first_text(metadata.get("artifactUrl"))
                    if source:
                        append_candidate(candidates, source, kind)

    attachments = payload.get("attachments")
    if isinstance(attachments, list):
        for attachment in attachments:
            if not isinstance(attachment, dict) or attachment.get("omitted"):
                continue
            kind = first_text(attachment.get("kind"))
            mime_type = first_text(attachment.get("mimeType"))
            if kind not in {"image", "video"} and not mime_type.startswith(("image/", "video/")):
                continue
            source = first_text(attachment.get("artifactUrl"), attachment.get("src"))
            if source:
                append_candidate(candidates, source, kind if kind in {"image", "video"} else "", mime_type)
            elif first_text(attachment.get("dataUrl")):
                raise RuntimeError("HyperFrames background must be a local Loki artifact; attachment dataUrl is not executable input.")

    unique = []
    seen: set[Path] = set()
    for path, kind in candidates:
        resolved = path.resolve()
        if resolved not in seen:
            unique.append((resolved, kind))
            seen.add(resolved)

    if not unique:
        raise RuntimeError("hyperframes-text-video requires exactly one selected image or video artifact.")
    if len(unique) > 1:
        raise RuntimeError("hyperframes-text-video requires exactly one background; multiple selected image/video artifacts were found.")
    return unique[0]


def parse_json_object(value: object, label: str) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{label} must be valid JSON.") from exc
        if isinstance(parsed, dict):
            return parsed
    raise RuntimeError(f"{label} must be a JSON object.")


def number(value: object, label: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{label} must be a number.") from exc
    if parsed < 0:
        raise RuntimeError(f"{label} must be non-negative.")
    return parsed


def positive_number(value: object, label: str) -> float:
    parsed = number(value, label)
    if parsed <= 0:
        raise RuntimeError(f"{label} must be greater than zero.")
    return parsed


def int_choice(value: object, default: int, label: str, minimum: int, maximum: int) -> int:
    if value is None or value == "":
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{label} must be an integer.") from exc
    if parsed < minimum or parsed > maximum:
        raise RuntimeError(f"{label} must be between {minimum} and {maximum}.")
    return parsed


def output_dimensions(params: dict[str, Any]) -> tuple[str, str, int, int]:
    video_resolution = first_text(params.get("videoResolution"))
    if video_resolution not in VIDEO_RESOLUTION_DIMENSIONS:
        raise RuntimeError("hyperframes-text-video requires params.videoResolution to be 480p or 720p.")
    aspect_ratio = first_text(params.get("aspectRatio"))
    dimensions = VIDEO_RESOLUTION_DIMENSIONS[video_resolution].get(aspect_ratio)
    if dimensions is None:
        raise RuntimeError("hyperframes-text-video requires params.aspectRatio to be 16:9, 9:16, or 1:1.")
    width, height = dimensions
    return video_resolution, aspect_ratio, width, height


def validate_script(script: dict[str, Any], *, background_kind: str, media: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    video_resolution, aspect_ratio, width, height = output_dimensions(params)
    background_fit = first_text(script.get("backgroundFit"), "cover")
    if background_fit not in {"cover", "contain"}:
        raise RuntimeError("scriptJson.backgroundFit must be cover or contain.")

    fps = int_choice(script.get("fps"), 30, "scriptJson.fps", 1, 60)
    duration = parse_duration(script.get("durationSeconds"))
    if duration is None:
        if background_kind == "video":
            duration = float(media["duration"])
        else:
            raise RuntimeError("scriptJson.durationSeconds is required for image backgrounds.")

    blocks = script.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        raise RuntimeError("scriptJson.blocks must contain at least one text block.")

    normalized_blocks: list[dict[str, Any]] = []
    for index, block in enumerate(blocks, start=1):
        if not isinstance(block, dict):
            raise RuntimeError(f"scriptJson.blocks[{index}] must be an object.")
        kind = first_text(block.get("kind"))
        if kind not in BLOCK_KINDS:
            raise RuntimeError(f"scriptJson.blocks[{index}].kind must be one of {', '.join(sorted(BLOCK_KINDS))}.")
        text = first_text(block.get("text"))
        if not text:
            raise RuntimeError(f"scriptJson.blocks[{index}].text is required.")
        start = number(block.get("start"), f"scriptJson.blocks[{index}].start")
        block_duration = positive_number(block.get("duration"), f"scriptJson.blocks[{index}].duration")
        if start + block_duration > duration + 0.001:
            raise RuntimeError(f"scriptJson.blocks[{index}] timing exceeds composition duration.")
        preset = first_text(block.get("preset"), DEFAULT_PRESET_BY_KIND[kind])
        if preset not in PRESETS:
            raise RuntimeError(f"scriptJson.blocks[{index}].preset must be a supported HyperFrames text preset.")
        position = first_text(block.get("position"), DEFAULT_POSITION_BY_PRESET[preset])
        if position not in POSITIONS:
            raise RuntimeError(f"scriptJson.blocks[{index}].position must be a supported text position.")
        normalized_blocks.append(
            {
                "kind": kind,
                "text": text,
                "start": start,
                "duration": block_duration,
                "preset": preset,
                "position": position,
            }
        )

    return {
        "durationSeconds": duration,
        "fps": fps,
        "videoResolution": video_resolution,
        "aspectRatio": aspect_ratio,
        "width": width,
        "height": height,
        "backgroundFit": background_fit,
        "blocks": normalized_blocks,
    }


def block_class(block: dict[str, Any]) -> str:
    return f"text-block preset-{block['preset']} position-{block['position']}"


def generate_index_html(
    *,
    composition_id: str,
    title: str,
    asset_name: str,
    background_kind: str,
    script: dict[str, Any],
    width: int,
    height: int,
) -> str:
    duration_seconds = float(script["durationSeconds"])
    fit = script["backgroundFit"]
    media = (
        f'<img class="background-media" src="assets/{html.escape(asset_name)}" alt="" />'
        if background_kind == "image"
        else f'<video id="backgroundVideo" class="background-media" src="assets/{html.escape(asset_name)}" muted playsinline preload="auto"></video>'
    )
    block_markup = []
    for index, block in enumerate(script["blocks"], start=1):
        start_seconds = format_seconds(float(block["start"]))
        duration_seconds_attr = format_seconds(float(block["duration"]))
        escaped_text = html.escape(block["text"])
        block_markup.append(
            "\n".join(
                [
                    f'<section id="block-{index}" class="clip {block_class(block)}" data-start="{start_seconds}" data-duration="{duration_seconds_attr}" data-track-index="{index}">',
                    f"  <span>{escaped_text}</span>",
                    "</section>",
                ]
            )
        )

    blocks_json = json.dumps(script["blocks"])
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)}</title>
  <style>
    html, body {{ margin:0; width:100%; height:100%; overflow:hidden; background:#050505; }}
    body {{ display:grid; place-items:center; font-family:"DM Sans", Inter, "Helvetica Neue", Helvetica, Arial, sans-serif; }}
    [data-composition-id] {{ position:relative; width:{width}px; height:{height}px; overflow:hidden; background:#050505; color:white; }}
    .background-media {{ position:absolute; inset:0; width:100%; height:100%; object-fit:{fit}; object-position:center; }}
    .text-block {{ position:absolute; z-index:2; box-sizing:border-box; display:flex; opacity:0; transform:translate3d(0,18px,0) scale(.985); filter:drop-shadow(0 8px 22px rgba(0,0,0,.42)); }}
    .text-block span {{ display:inline-block; max-width:100%; color:#fff; text-wrap:balance; line-height:1.02; letter-spacing:0; }}
    .position-center {{ inset:0; align-items:center; justify-content:center; padding:8%; text-align:center; }}
    .position-top {{ left:6%; right:6%; top:7%; justify-content:center; text-align:center; }}
    .position-bottom {{ left:7%; right:7%; bottom:7%; justify-content:center; text-align:center; }}
    .position-lower-left {{ left:6%; right:28%; bottom:9%; justify-content:flex-start; text-align:left; }}
    .position-lower-right {{ left:28%; right:6%; bottom:9%; justify-content:flex-end; text-align:right; }}
    .preset-title-card span {{ font-size:clamp(60px, 8.5vw, 164px); font-weight:800; }}
    .preset-lower-third span {{ padding:.42em .62em; background:rgba(0,0,0,.68); border-left:10px solid #ff4f64; font-size:clamp(34px, 4vw, 78px); font-weight:750; }}
    .preset-karaoke-subtitle span {{ padding:.42em .62em; background:rgba(0,0,0,.72); border-radius:18px; font-size:clamp(32px, 4.4vw, 74px); font-weight:800; }}
    .preset-quote span {{ max-width:82%; font-size:clamp(48px, 6.2vw, 126px); font-weight:780; font-style:italic; }}
    .preset-caption-stack span {{ padding:.36em .54em; background:rgba(255,255,255,.92); color:#111; border-radius:16px; font-size:clamp(34px, 4.3vw, 82px); font-weight:850; text-transform:uppercase; }}
    .preset-cta span {{ padding:.48em .75em; background:#ff4f64; color:#fff; border-radius:999px; font-size:clamp(36px, 4.6vw, 86px); font-weight:850; }}
    .duration-anchor {{ position:absolute; inset:0; width:1px; height:1px; opacity:0; pointer-events:none; }}
  </style>
</head>
<body>
  <main id="{composition_id}" data-composition-id="{composition_id}" data-start="0" data-duration="{format_seconds(duration_seconds)}" data-width="{width}" data-height="{height}" data-track-index="0">
    {media}
    <section id="duration-anchor" class="clip duration-anchor" data-start="0" data-duration="{format_seconds(duration_seconds)}" data-track-index="999"></section>
    {"".join(block_markup)}
  </main>
  <script>
    (function () {{
      const compositionId = {json.dumps(composition_id)};
      const durationSeconds = {json.dumps(duration_seconds)};
      const blocks = {blocks_json};
      const video = document.getElementById("backgroundVideo");
      const elements = blocks.map((_, index) => document.getElementById(`block-${{index + 1}}`));
      function clamp(value, min, max) {{ return Math.max(min, Math.min(max, value)); }}
      function ease(value) {{ const t = clamp(value, 0, 1); return t * t * (3 - 2 * t); }}
      function renderAt(ms) {{
        if (video && Number.isFinite(video.duration)) {{
          video.currentTime = Math.min(video.duration, Math.max(0, ms / 1000));
        }}
        blocks.forEach((block, index) => {{
          const element = elements[index];
          if (!element) return;
          const start = block.start * 1000;
          const end = start + block.duration * 1000;
          const intro = ease((ms - start) / 360);
          const outro = 1 - ease((ms - (end - 320)) / 320);
          const visible = ms >= start && ms <= end ? clamp(Math.min(intro, outro), 0, 1) : 0;
          const y = (1 - visible) * 18;
          const scale = .985 + visible * .015;
          element.style.opacity = String(visible);
          element.style.transform = `translate3d(0, ${{y}}px, 0) scale(${{scale}})`;
        }});
      }}
      const timeline = {{
        currentTime: 0,
        paused: true,
        duration() {{ return durationSeconds; }},
        seek(timeSeconds) {{
          this.currentTime = Number(timeSeconds) || 0;
          renderAt(this.currentTime * 1000);
          return this;
        }},
        pause() {{ this.paused = true; }},
        play() {{ this.paused = false; }}
      }};
      window.__timelines = window.__timelines || {{}};
      window.__timelines[compositionId] = timeline;
      timeline.seek(0);
    }})();
  </script>
</body>
</html>
"""


def write_project(project_dir: Path, *, background: Path, background_kind: str, script: dict[str, Any], title: str) -> Path:
    assets_dir = project_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    extension = background.suffix or (".png" if background_kind == "image" else ".mp4")
    asset_path = assets_dir / f"background{extension}"
    shutil.copy2(background, asset_path)
    (project_dir / "hyperframes.json").write_text(
        json.dumps(
            {
                "$schema": "https://hyperframes.heygen.com/schema/hyperframes.json",
                "registry": "https://raw.githubusercontent.com/heygen-com/hyperframes/main/registry",
                "paths": {"blocks": "compositions", "components": "compositions/components", "assets": "assets"},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (project_dir / "package.json").write_text(
        json.dumps({"name": "loki-hyperframes-text-video", "private": True, "type": "module"}, indent=2) + "\n",
        encoding="utf-8",
    )
    index_html = generate_index_html(
        composition_id="loki-hyperframes-text-video",
        title=title,
        asset_name=asset_path.name,
        background_kind=background_kind,
        script=script,
        width=int(script["width"]),
        height=int(script["height"]),
    )
    (project_dir / "index.html").write_text(index_html, encoding="utf-8")
    return asset_path


def hyperframes_command(*args: str) -> list[str]:
    return ["npx", "--yes", f"hyperframes@{HYPERFRAMES_VERSION}", *args]


def render_hyperframes(project_dir: Path, output_path: Path, fps: int) -> None:
    run_command(hyperframes_command("lint", str(project_dir)))
    run_command(hyperframes_command("inspect", str(project_dir)))
    run_command(
        hyperframes_command(
            "render",
            str(project_dir),
            "--format",
            "mp4",
            "--fps",
            str(fps),
            "--quality",
            "standard",
            "--strict",
            "--output",
            str(output_path),
        )
    )
    if not output_path.is_file():
        raise RuntimeError(f"HyperFrames render did not create expected output: {output_path}")


def format_seconds(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".") or "0"


def mux_original_audio(rendered_video: Path, source_video: Path, destination: Path, duration: float) -> None:
    formatted_duration = format_seconds(duration)
    run_command(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(rendered_video),
            "-i",
            str(source_video),
            "-filter_complex",
            (
                f"[1:a:0]atrim=0:{formatted_duration},asetpts=PTS-STARTPTS,"
                f"apad,atrim=0:{formatted_duration},"
                "aformat=channel_layouts=stereo,aresample=48000[a]"
            ),
            "-map",
            "0:v:0",
            "-map",
            "[a]",
            "-t",
            formatted_duration,
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(destination),
        ]
    )
    if not destination.is_file():
        raise RuntimeError(f"ffmpeg mux did not create expected output: {destination}")


def base_prompt(payload: dict[str, Any]) -> str:
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    return first_text(params.get("skillPrompt"), params.get("prompt"), params.get("outputText"), payload.get("prompt"))


def create_text_video(payload: dict[str, Any]) -> dict[str, Any]:
    require_tools()
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    outputs = output_dir(payload)
    root = run_root(outputs)
    project_dir = root / "project"
    project_dir.mkdir(parents=True, exist_ok=True)

    background, background_kind = selected_background(payload)
    media = video_info(background) if background_kind == "video" else image_info(background)
    script = validate_script(parse_json_object(params.get("scriptJson"), "params.scriptJson"), background_kind=background_kind, media=media, params=params)
    title = first_text(params.get("title"), "HyperFrames text video")
    write_project(project_dir, background=background, background_kind=background_kind, script=script, title=title)

    rendered_output = outputs / "hyperframes-render.mp4"
    render_hyperframes(project_dir, rendered_output, int(script["fps"]))
    final_output = outputs / "hyperframes-text-video.mp4"
    if background_kind == "video" and bool(media.get("hasAudio")):
        mux_original_audio(rendered_output, background, final_output, float(script["durationSeconds"]))
    else:
        shutil.copy2(rendered_output, final_output)

    metadata = {
        "kind": "video",
        "source": "hyperframes",
        "backgroundKind": background_kind,
        "backgroundPath": str(background),
        "durationSeconds": script["durationSeconds"],
        "fps": script["fps"],
        "videoResolution": script["videoResolution"],
        "aspectRatio": script["aspectRatio"],
        "width": script["width"],
        "height": script["height"],
        "backgroundFit": script["backgroundFit"],
        "blockCount": len(script["blocks"]),
        "hasAudio": background_kind == "video" and bool(media.get("hasAudio")),
        "projectDir": str(project_dir),
        "tags": [SKILL_ID, "hyperframes", "text-overlay"],
    }
    return {
        "artifacts": [
            {
                "path": str(final_output),
                "kind": "video",
                "mimeType": "video/mp4",
                "title": title,
                "prompt": base_prompt(payload),
                "metadata": metadata,
            }
        ]
    }


def main() -> None:
    print(json.dumps(create_text_video(read_payload())))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"hyperframes-text-video failed: {exc}", file=sys.stderr)
        sys.exit(1)
