from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from typing import Any

RUNTIME_DIR = Path(__file__).resolve().parents[2] / "_comfy_runtime"
sys.path.insert(0, str(RUNTIME_DIR))

import comfy_action  # noqa: E402


PREVIEW_COUNT = 3
PREVIEW_RESOLUTION = "360p"
ALLOWED_PROFILES = {"ltx23-10eros", "ltx23-dasiwa-golden-lace-v3"}
SKILL_ID = "ltx-seed-seeker"
SKILL_LABEL = "LTX Seed Seeker"
ALLOWED_VIDEO_MODES = {"i2v"}
ALLOWED_ASPECT_RATIOS = {"9:16", "16:9", "4:3"}
ALLOWED_DURATIONS = {3, 5, 7, 10, 15}
ALLOWED_RERENDER_RESOLUTIONS = {"720p", "1080p"}


def first_text(*values: object) -> str:
    return comfy_action.first_text(*values)


def as_int(value: object) -> int | None:
    return comfy_action.as_int(value)


def normalize_run_mode(params: dict[str, Any], payload: dict[str, Any]) -> str:
    mode = first_text(params.get("runMode"), params.get("mode"), params.get("command"))
    if not mode and selected_seed_preview(payload) is not None:
        return "rerender"
    return (mode or "preview").strip().lower().replace("_", "-")


def normalize_profile(value: object) -> str:
    profile = comfy_action.normalize_video_model_profile(first_text(value))
    if profile not in ALLOWED_PROFILES:
        raise RuntimeError(f"{SKILL_LABEL} requires modelProfile to be ltx23-10eros or ltx23-dasiwa-golden-lace-v3.")
    return profile


def normalize_video_mode(value: object) -> str:
    mode = comfy_action.normalize_video_mode(first_text(value, "i2v"))
    if mode not in ALLOWED_VIDEO_MODES:
        raise RuntimeError(f"{SKILL_LABEL} only supports i2v. First/last-frame mode has been removed.")
    return mode


def normalize_aspect_ratio(value: object) -> str:
    aspect_ratio = first_text(value)
    if aspect_ratio not in ALLOWED_ASPECT_RATIOS:
        raise RuntimeError(f"{SKILL_LABEL} requires aspectRatio to be one of 9:16, 16:9, or 4:3.")
    return aspect_ratio


def normalize_duration(value: object) -> int:
    duration = as_int(value)
    if duration not in ALLOWED_DURATIONS:
        raise RuntimeError(f"{SKILL_LABEL} requires duration to be 3, 5, 7, 10, or 15 seconds.")
    return int(duration)


def normalize_rerender_resolution(value: object) -> str:
    resolution = first_text(value, "720p")
    if resolution not in ALLOWED_RERENDER_RESOLUTIONS:
        raise RuntimeError(f"{SKILL_LABEL} rerender requires targetResolution to be 720p or 1080p.")
    return resolution


def output_root(run_outputs: Path) -> Path:
    return run_outputs.parent


def artifact_url_for_path(path: Path) -> str:
    root = comfy_action.artifacts_root()
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError:
        return ""
    return f"/api/artifacts/{relative.as_posix()}"


def ensure_source_under_artifacts(path: Path, inputs_dir: Path, index: int) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(comfy_action.artifacts_root())
        return resolved
    except ValueError as exc:
        raise RuntimeError(f"Selected image input must be a local Loki artifact path: {path}") from exc


def image_paths_from_params(params: dict[str, Any]) -> list[Path]:
    paths: list[Path] = []
    for key in ("inputPath",):
        value = first_text(params.get(key))
        if value:
            path = Path(value).expanduser()
            if path not in paths:
                paths.append(path)
    return paths


def preview_source_images(payload: dict[str, Any], run_outputs: Path) -> list[Path]:
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    media = comfy_action.materialize_selected_media(payload, output_root(run_outputs) / "inputs")
    images = [*media.get("image", []), *image_paths_from_params(params)]
    if not images:
        raise RuntimeError(f"{SKILL_LABEL} preview requires one selected or attached image.")

    normalized = [
        ensure_source_under_artifacts(path, output_root(run_outputs) / "inputs", index)
        for index, path in enumerate(images, start=1)
    ]
    if not normalized:
        raise RuntimeError(f"{SKILL_LABEL} preview could not resolve any selected image inputs.")
    return normalized


def selected_seed_preview(payload: dict[str, Any]) -> dict[str, Any] | None:
    snapshots = payload.get("selectedCardSnapshots")
    if not isinstance(snapshots, list):
        return None

    for snapshot in snapshots:
        if not isinstance(snapshot, dict):
            continue
        metadata = snapshot.get("metadata")
        if not isinstance(metadata, dict):
            continue
        seed_seeker = metadata.get("seedSeeker")
        if not isinstance(seed_seeker, dict):
            continue
        if first_text(seed_seeker.get("mode")) == "preview" and as_int(metadata.get("seed")) is not None:
            return metadata

    return None


def source_urls_from_metadata(metadata: dict[str, Any]) -> list[str]:
    urls = metadata.get("sourceImageArtifactUrls")
    if not isinstance(urls, list):
        seed_seeker = metadata.get("seedSeeker")
        urls = seed_seeker.get("sourceImageArtifactUrls") if isinstance(seed_seeker, dict) else []
    return [url for url in urls if isinstance(url, str) and url.startswith("/api/artifacts/")]


def rerender_source_images(metadata: dict[str, Any]) -> list[Path]:
    images = [path for url in source_urls_from_metadata(metadata) if (path := comfy_action.resolve_artifact_src(url))]
    if not images:
        raise RuntimeError(f"{SKILL_LABEL} rerender requires a selected preview with stored source image artifacts.")
    return images


def seed_values(params: dict[str, Any], count: int) -> list[int]:
    base_seed = as_int(params.get("seed"))
    if base_seed is not None:
        return [base_seed + index for index in range(count)]

    generator = random.SystemRandom()
    seeds: list[int] = []
    while len(seeds) < count:
        seed = generator.randint(1, 2_147_483_647)
        if seed not in seeds:
            seeds.append(seed)
    return seeds


def video_dimensions(aspect_ratio: str, resolution: str) -> tuple[int, int]:
    width, height = comfy_action.video_dimensions({"aspectRatio": aspect_ratio, "resolution": resolution})
    if not width or not height:
        raise RuntimeError(f"{SKILL_LABEL} could not resolve dimensions for {resolution} {aspect_ratio}.")
    return width, height


def floor_to_multiple(value: int, multiple: int) -> int:
    return max(multiple, value - (value % multiple))


def ltx_base_dimensions(target_width: int, target_height: int) -> tuple[int, int]:
    return floor_to_multiple(target_width // 2, 16), floor_to_multiple(target_height // 2, 16)


def ltx_image_input(path: Path, out_dir: Path, mode: str, label: str) -> str:
    if mode != "i2v":
        return str(path)

    inputs_dir = out_dir.parent / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    try:
        return str(comfy_action.half_scale_image_input(path, inputs_dir, label))
    except Exception:
        return str(path)


def command_image_args(command: list[str], mode: str, out_dir: Path, images: list[Path]) -> None:
    image_input = ltx_image_input(images[0], out_dir, mode, f"{out_dir.name}-input")
    command.extend(["--input", image_input])


def build_seed_command(
    *,
    prompt: str,
    model_profile: str,
    video_mode: str,
    aspect_ratio: str,
    resolution: str,
    duration: int,
    seed: int,
    images: list[Path],
    out_dir: Path,
    run_root: Path,
) -> tuple[list[str], Path, int, int, int, int, int, int]:
    target_width, target_height = video_dimensions(aspect_ratio, resolution)
    width, height = ltx_base_dimensions(target_width, target_height)
    fps = comfy_action.default_video_fps(video_mode)
    length = comfy_action.video_length_from_duration(video_mode, duration, fps)
    cwd = comfy_action.write_run_comfy_config(
        run_root,
        capability=comfy_action.videogen_capability(video_mode),
        model_profile=model_profile,
    )
    command = [
        "comfy-videogen",
        video_mode,
        "--models-dir",
        str(comfy_action.models_dir()),
        "--out",
        str(out_dir),
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
        "--seed",
        str(seed),
    ]
    command_image_args(command, video_mode, out_dir, images)
    return command, cwd, width, height, width * 2, height * 2, target_width, target_height


def artifact_paths_from_cli(payload: dict[str, Any]) -> list[Path]:
    if payload.get("ok") is False:
        raise RuntimeError(json.dumps(payload, indent=2))

    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list):
        raise RuntimeError("Comfy command did not return artifacts.")

    paths = [Path(path) for path in artifacts if isinstance(path, str)]
    valid_paths = [path for path in paths if path.is_file()]
    if not valid_paths:
        raise RuntimeError("Comfy command did not return a valid video artifact.")
    return valid_paths


def artifact_description(seed: int, prompt: str) -> str:
    return f"Seed: {seed}\nPrompt: {prompt}"


def artifact_metadata(
    *,
    seed: int,
    prompt: str,
    model_profile: str,
    video_mode: str,
    aspect_ratio: str,
    duration: int,
    resolution: str,
    width: int,
    height: int,
    source_image_urls: list[str],
    mode: str,
    cli_width: int,
    cli_height: int,
    requested_width: int,
    requested_height: int,
    preview_index: int | None = None,
    preview_count: int | None = None,
) -> dict[str, Any]:
    seed_seeker = {
        "mode": mode,
        "seed": seed,
        "basePrompt": prompt,
        "modelProfile": model_profile,
        "videoMode": video_mode,
        "aspectRatio": aspect_ratio,
        "duration": duration,
        "resolution": resolution,
        "requestedResolution": resolution,
        "cliWidth": cli_width,
        "cliHeight": cli_height,
        "requestedWidth": requested_width,
        "requestedHeight": requested_height,
        "sourceImageArtifactUrls": source_image_urls,
    }
    if preview_index is not None:
        seed_seeker["previewIndex"] = preview_index
    if preview_count is not None:
        seed_seeker["previewCount"] = preview_count

    return {
        "seedSeeker": seed_seeker,
        "seed": seed,
        "basePrompt": prompt,
        "modelProfile": model_profile,
        "videoMode": video_mode,
        "aspectRatio": aspect_ratio,
        "duration": duration,
        "resolution": resolution,
        "requestedResolution": resolution,
        "width": width,
        "height": height,
        "cliWidth": cli_width,
        "cliHeight": cli_height,
        "requestedWidth": requested_width,
        "requestedHeight": requested_height,
        "preferredAspectRatio": aspect_ratio,
        "sourceImageArtifactUrls": source_image_urls,
        "tags": [SKILL_ID, f"seed-{seed}", mode],
    }


def raw_artifact_result(
    *,
    video_path: Path,
    title: str,
    prompt: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        "artifacts": [
            {
                "path": str(video_path),
                "kind": "video",
                "mimeType": "video/mp4",
                "title": title,
                "prompt": prompt,
                "metadata": metadata,
            }
        ]
    }


def run_single_generation(
    *,
    prompt: str,
    model_profile: str,
    video_mode: str,
    aspect_ratio: str,
    resolution: str,
    duration: int,
    seed: int,
    images: list[Path],
    out_dir: Path,
    run_root: Path,
    source_image_urls: list[str],
    title: str,
    mode: str,
    preview_index: int | None = None,
    preview_count: int | None = None,
) -> dict[str, Any]:
    command, cwd, cli_width, cli_height, width, height, requested_width, requested_height = build_seed_command(
        prompt=prompt,
        model_profile=model_profile,
        video_mode=video_mode,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        duration=duration,
        seed=seed,
        images=images,
        out_dir=out_dir,
        run_root=run_root,
    )
    payload = comfy_action.run_command(command, cwd)
    video_path = artifact_paths_from_cli(payload)[0]
    metadata = artifact_metadata(
        seed=seed,
        prompt=prompt,
        model_profile=model_profile,
        video_mode=video_mode,
        aspect_ratio=aspect_ratio,
        duration=duration,
        resolution=resolution,
        width=width,
        height=height,
        source_image_urls=source_image_urls,
        mode=mode,
        cli_width=cli_width,
        cli_height=cli_height,
        requested_width=requested_width,
        requested_height=requested_height,
        preview_index=preview_index,
        preview_count=preview_count,
    )
    return raw_artifact_result(
        video_path=video_path,
        title=title,
        prompt=artifact_description(seed, prompt),
        metadata=metadata,
    )


def emit_partial(raw: dict[str, Any]) -> None:
    print(f"__LOKI_PARTIAL_RESULT__{json.dumps(raw)}", flush=True)


def run_preview(payload: dict[str, Any], *, emit_partials: bool = True) -> dict[str, Any]:
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    run_outputs = comfy_action.output_dir(payload)
    run_root = output_root(run_outputs)
    prompt = comfy_action.base_prompt(payload)
    if not prompt:
        raise RuntimeError(f"{SKILL_LABEL} preview requires a video prompt.")

    model_profile = normalize_profile(params.get("modelProfile"))
    video_mode = normalize_video_mode(params.get("videoMode"))
    aspect_ratio = normalize_aspect_ratio(params.get("aspectRatio"))
    duration = normalize_duration(params.get("duration"))
    images = preview_source_images(payload, run_outputs)
    source_image_urls = [url for path in images if (url := artifact_url_for_path(path))]
    seeds = seed_values(params, PREVIEW_COUNT)
    results: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []

    for index, seed in enumerate(seeds, start=1):
        try:
            raw = run_single_generation(
                prompt=prompt,
                model_profile=model_profile,
                video_mode=video_mode,
                aspect_ratio=aspect_ratio,
                resolution=PREVIEW_RESOLUTION,
                duration=duration,
                seed=seed,
                images=images,
                out_dir=run_outputs / f"preview-{index:02d}",
                run_root=run_root,
                source_image_urls=source_image_urls,
                title=f"LTX Seed Seeker preview {index} seed {seed}",
                mode="preview",
                preview_index=index,
                preview_count=PREVIEW_COUNT,
            )
        except Exception as exc:
            diagnostics.append(
                {
                    "level": "warning",
                    "title": f"Seed preview {index} failed",
                    "message": str(exc),
                    "metadata": {"seed": seed, "previewIndex": index},
                }
            )
            continue

        if emit_partials:
            emit_partial(raw)
        else:
            results.append(raw)

    if not emit_partials:
        if not results:
            messages = "; ".join(first_text(diagnostic.get("message")) for diagnostic in diagnostics)
            raise RuntimeError(f"{SKILL_LABEL} preview failed for all seeds: {messages}")
        return comfy_action.combine_raw_results([*results, {"diagnostics": diagnostics}])

    if len(diagnostics) == PREVIEW_COUNT:
        messages = "; ".join(first_text(diagnostic.get("message")) for diagnostic in diagnostics)
        raise RuntimeError(f"{SKILL_LABEL} preview failed for all seeds: {messages}")
    return {"diagnostics": diagnostics} if diagnostics else {}


def run_rerender(payload: dict[str, Any]) -> dict[str, Any]:
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    run_outputs = comfy_action.output_dir(payload)
    run_root = output_root(run_outputs)
    metadata = selected_seed_preview(payload)
    if metadata is None:
        raise RuntimeError(f"{SKILL_LABEL} rerender requires selecting one LTX Seed Seeker preview card.")

    seed = as_int(metadata.get("seed"))
    if seed is None:
        raise RuntimeError(f"Selected {SKILL_LABEL} preview does not include a seed.")

    prompt = first_text(metadata.get("basePrompt"))
    if not prompt:
        raise RuntimeError(f"Selected {SKILL_LABEL} preview does not include the original prompt.")
    model_profile = normalize_profile(metadata.get("modelProfile"))
    video_mode = normalize_video_mode(metadata.get("videoMode"))
    aspect_ratio = normalize_aspect_ratio(metadata.get("aspectRatio"))
    duration = normalize_duration(metadata.get("duration"))
    resolution = normalize_rerender_resolution(params.get("targetResolution") or params.get("resolution"))
    images = rerender_source_images(metadata)
    source_image_urls = source_urls_from_metadata(metadata)

    return run_single_generation(
        prompt=prompt,
        model_profile=model_profile,
        video_mode=video_mode,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        duration=duration,
        seed=seed,
        images=images,
        out_dir=run_outputs / f"rerender-{resolution}",
        run_root=run_root,
        source_image_urls=source_image_urls,
        title=f"LTX Seed Seeker {resolution} seed {seed}",
        mode="rerender",
    )


def main() -> None:
    payload = comfy_action.read_payload()
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    run_mode = normalize_run_mode(params, payload)
    if run_mode == "preview":
        print(json.dumps(run_preview(payload, emit_partials=True)))
        return
    if run_mode == "rerender":
        print(json.dumps(run_rerender(payload)))
        return
    raise RuntimeError(f"{SKILL_LABEL} runMode must be preview or rerender.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ltx seed seeker action failed: {exc}", file=sys.stderr)
        sys.exit(1)
