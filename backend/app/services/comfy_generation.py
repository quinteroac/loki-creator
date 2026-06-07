from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from app.models import (
    ComfyGenerationRequest,
    ComfyGenerationResponse,
    SkillArtifact,
    SkillDefinition,
    SkillOutputConfig,
    SkillRawResult,
)
from app.services.card_packager import CardPackagerService


COMFY_DIRECT_SKILL_ID = "comfy-direct"
BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent
IMAGE_DIMENSIONS = {
    "1:1": (1024, 1024),
    "4:3": (1152, 864),
    "16:9": (1344, 768),
    "9:16": (768, 1344),
}
VIDEO_DIMENSIONS = {
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
WAN_FPS = 16


class ComfyGenerationError(RuntimeError):
    pass


def first_text(*values: object) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def normalize_image_profile(value: str) -> str:
    aliases = {
        "qwen-image-edit-2511": "qwen-edit2511",
        "qwen-image-edit": "qwen-edit2511",
        "qwen-edit-2511": "qwen-edit2511",
        "flux-klein-snofs": "flux-klein-9b-snofs",
        "flux-2-klein-9b-snofs": "flux-klein-9b-snofs",
    }
    return aliases.get(value.strip(), value.strip())


def normalize_video_profile(value: str) -> str:
    aliases = {
        "ltx": "ltx23-10eros",
        "ltx23": "ltx23-10eros",
        "ltx-2.3": "ltx23-10eros",
        "ltx-2.3-10eros": "ltx23-10eros",
        "dasiwa": "ltx23-dasiwa-golden-lace-v3",
        "ltx23-dasiwa": "ltx23-dasiwa-golden-lace-v3",
        "golden-lace": "ltx23-dasiwa-golden-lace-v3",
        "wan": "wan22-i2v",
        "wan2.2": "wan22-i2v",
        "wan22": "wan22-i2v",
        "dasiwa-tastysin": "wan22-dasiwa-tastysin-i2v",
        "tastysin": "wan22-dasiwa-tastysin-i2v",
        "boundbite": "wan22-dasiwa-boundbite-i2v",
    }
    return aliases.get(value.strip(), value.strip())


class ComfyGenerationService:
    def __init__(self, artifacts_root: Path, *, packager: CardPackagerService | None = None) -> None:
        self.artifacts_root = artifacts_root.resolve()
        self.packager = packager or CardPackagerService()

    def generate(self, payload: ComfyGenerationRequest) -> ComfyGenerationResponse:
        prompt = payload.prompt.strip()
        if not prompt:
            raise ComfyGenerationError("Comfy generation requires a prompt.")

        run_id = f"generation_{uuid4().hex}"
        out_dir = self.output_dir(run_id)
        media = self.selected_media(payload)
        command, cwd, expected_kind, params = self.build_command(payload, prompt, out_dir, media)
        raw = self.run_command(command, cwd)
        raw_result = self.validated_raw_result(raw, expected_kind=expected_kind, prompt=prompt)
        result = self.packager.package(
            skill=self.skill_definition(expected_kind),
            run_id=run_id,
            prompt=prompt,
            params=params,
            raw_result=raw_result,
        )
        return ComfyGenerationResponse(cards=result.cards)

    def output_dir(self, run_id: str) -> Path:
        path = self.artifacts_root / "generations" / "comfy" / run_id / "outputs"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def models_dir(self) -> Path:
        return Path(os.environ.get("LOKI_COMFY_MODELS_DIR", REPO_ROOT / ".loki" / "models" / "comfyui")).resolve()

    def executable(self, name: str) -> str:
        found = shutil.which(name)
        if found:
            return found
        repo_local = REPO_ROOT / "backend" / ".venv" / "bin" / name
        if repo_local.is_file():
            return str(repo_local)
        raise ComfyGenerationError(f"Comfy CLI executable not found: {name}. Run comfy-tools-setup first.")

    def selected_media(self, payload: ComfyGenerationRequest) -> dict[str, list[Path]]:
        media: dict[str, list[Path]] = {"image": [], "video": [], "audio": []}
        context = payload.context if isinstance(payload.context, dict) else {}
        for references in (context.get("localMediaReferences"),):
            if not isinstance(references, list):
                continue
            for reference in references:
                if not isinstance(reference, dict):
                    continue
                kind = first_text(reference.get("kind"))
                if kind not in media:
                    continue
                path = Path(first_text(reference.get("path"))).expanduser().resolve()
                self.append_media_path(media, kind, path)

        for snapshot in payload.selected_card_snapshots:
            if not isinstance(snapshot, dict):
                continue
            metadata = snapshot.get("metadata")
            if isinstance(metadata, dict):
                kind = first_text(metadata.get("kind"))
                if kind in media:
                    self.append_media_path(media, kind, self.resolve_artifact_url(first_text(metadata.get("artifactUrl"))))
            assets = snapshot.get("mediaAssets")
            if not isinstance(assets, list):
                continue
            for asset in assets:
                if not isinstance(asset, dict) or asset.get("omitted"):
                    continue
                kind = first_text(asset.get("kind"))
                if kind not in media:
                    continue
                src = first_text(asset.get("src"))
                if not src and first_text(asset.get("dataUrl")):
                    raise ComfyGenerationError("Comfy inputs must be local Loki artifacts; preview-only media is not executable.")
                self.append_media_path(media, kind, self.resolve_artifact_url(src))

        for attachment in payload.attachments:
            if not isinstance(attachment, dict) or attachment.get("omitted"):
                continue
            kind = first_text(attachment.get("kind"))
            if kind not in media:
                continue
            source = first_text(attachment.get("artifactUrl"), attachment.get("src"))
            if not source and first_text(attachment.get("dataUrl")):
                raise ComfyGenerationError("Comfy inputs must be local Loki artifacts; attached previews are not executable.")
            self.append_media_path(media, kind, self.resolve_artifact_url(source))
        return media

    def resolve_artifact_url(self, src: str) -> Path | None:
        if not src:
            return None
        if not src.startswith("/api/artifacts/"):
            path = Path(src).expanduser().resolve()
            return path if path.is_file() else None
        path = (self.artifacts_root / src.removeprefix("/api/artifacts/")).resolve()
        try:
            path.relative_to(self.artifacts_root)
        except ValueError as exc:
            raise ComfyGenerationError(f"Comfy artifact path escapes Loki artifacts root: {src}") from exc
        return path if path.is_file() else None

    def append_media_path(self, media: dict[str, list[Path]], kind: str, path: Path | None) -> None:
        if path is None:
            return
        resolved = path.resolve()
        try:
            resolved.relative_to(self.artifacts_root)
        except ValueError as exc:
            raise ComfyGenerationError(f"Comfy input must be inside Loki artifacts root: {resolved}") from exc
        if not resolved.is_file():
            raise ComfyGenerationError(f"Comfy input path does not exist: {resolved}")
        if resolved not in media[kind]:
            media[kind].append(resolved)

    def write_run_comfy_config(self, run_dir: Path, *, capability: str, model_profile: str) -> Path:
        base_config = self.local_comfy_config()
        config = {
            **base_config,
            "models_dir": str(self.models_dir()),
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

    def local_comfy_config(self) -> dict[str, Any]:
        config_path = REPO_ROOT / ".comfy-agent-tools.json"
        if not config_path.is_file():
            return {}
        try:
            parsed = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ComfyGenerationError(".comfy-agent-tools.json is not valid JSON.") from exc
        if not isinstance(parsed, dict):
            raise ComfyGenerationError(".comfy-agent-tools.json must contain a JSON object.")
        return parsed

    def build_command(
        self,
        payload: ComfyGenerationRequest,
        prompt: str,
        out_dir: Path,
        media: dict[str, list[Path]],
    ) -> tuple[list[str], Path, Literal["image", "video"], dict[str, Any]]:
        if payload.tool == "image":
            return self.build_image_command(payload, prompt, out_dir, media)
        return self.build_video_command(payload, prompt, out_dir, media)

    def build_image_command(
        self,
        payload: ComfyGenerationRequest,
        prompt: str,
        out_dir: Path,
        media: dict[str, list[Path]],
    ) -> tuple[list[str], Path, Literal["image"], dict[str, Any]]:
        profile = normalize_image_profile(payload.model_profile)
        if payload.image_mode in {"generate", "edit"} and not profile:
            raise ComfyGenerationError("Comfy image generation requires modelProfile.")
        if payload.image_mode in {"edit", "upscale"} and not media["image"]:
            raise ComfyGenerationError(f"Comfy image {payload.image_mode} requires one selected or attached image.")

        command = [self.executable("comfy-imagegen"), payload.image_mode, "--out", str(out_dir)]
        if payload.image_mode in {"generate", "edit", "upscale"}:
            command.extend(["--models-dir", str(self.models_dir())])
        if payload.image_mode in {"generate", "edit"}:
            command.extend(["--prompt", prompt])
        if payload.image_mode in {"edit", "upscale"}:
            command.extend(["--input", str(media["image"][0])])
        if payload.image_mode == "generate":
            width, height = IMAGE_DIMENSIONS[payload.aspect_ratio]
            command.extend(["--width", str(width), "--height", str(height)])
        if payload.seed is not None:
            command.extend(["--seed", str(payload.seed)])

        capability = f"imagegen.{payload.image_mode}"
        cwd = self.write_run_comfy_config(out_dir.parent, capability=capability, model_profile=profile) if profile else REPO_ROOT
        params = {
            "tool": payload.tool,
            "imageMode": payload.image_mode,
            "modelProfile": profile,
            "aspectRatio": payload.aspect_ratio,
            "seed": payload.seed,
        }
        return command, cwd, "image", params

    def build_video_command(
        self,
        payload: ComfyGenerationRequest,
        prompt: str,
        out_dir: Path,
        media: dict[str, list[Path]],
    ) -> tuple[list[str], Path, Literal["video"], dict[str, Any]]:
        profile = normalize_video_profile(payload.model_profile)
        if not profile:
            raise ComfyGenerationError("Comfy video generation requires modelProfile.")
        if payload.video_mode in {"i2v", "wan22-i2v"} and not media["image"]:
            raise ComfyGenerationError(f"Comfy video {payload.video_mode} requires one selected or attached image.")
        if payload.video_mode in {"flf2v", "wan22-flf2v"} and not media["image"]:
            raise ComfyGenerationError(f"Comfy video {payload.video_mode} requires at least one selected or attached image.")

        width, height = VIDEO_DIMENSIONS[payload.resolution][payload.aspect_ratio]
        fps = WAN_FPS if payload.video_mode.startswith("wan22-") else 24
        length = payload.duration * fps + (1 if payload.video_mode.startswith("wan22-") else 0)
        command = [
            self.executable("comfy-videogen"),
            payload.video_mode,
            "--out",
            str(out_dir),
            "--models-dir",
            str(self.models_dir()),
            "--prompt",
            prompt,
            "--width",
            str(width),
            "--height",
            str(height),
            "--length",
            str(length),
        ]
        if payload.video_mode.startswith("wan22-"):
            command.extend(["--fps", str(fps)])
        if payload.video_mode in {"i2v", "wan22-i2v"}:
            command.extend(["--input", str(media["image"][0])])
        if payload.video_mode in {"flf2v", "wan22-flf2v"}:
            first = media["image"][0]
            last = media["image"][-1]
            command.extend(["--first", str(first), "--last", str(last)])
        if payload.seed is not None:
            command.extend(["--seed", str(payload.seed)])

        cwd = self.write_run_comfy_config(out_dir.parent, capability=f"videogen.{payload.video_mode}", model_profile=profile)
        params = {
            "tool": payload.tool,
            "videoMode": payload.video_mode,
            "modelProfile": profile,
            "aspectRatio": payload.aspect_ratio,
            "resolution": payload.resolution,
            "duration": payload.duration,
            "seed": payload.seed,
        }
        return command, cwd, "video", params

    def run_command(self, command: list[str], cwd: Path) -> dict[str, Any]:
        env = {**os.environ, "PYTHONUNBUFFERED": "1"}
        env.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
        timeout_seconds = int(os.environ.get("LOKI_COMFY_DIRECT_TIMEOUT_SECONDS", "0"))
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
            message = process.stderr.strip() or process.stdout.strip() or "Comfy command failed."
            raise ComfyGenerationError(message)
        try:
            parsed = json.loads(process.stdout)
        except json.JSONDecodeError as exc:
            raise ComfyGenerationError(f"Comfy command did not return valid JSON: {process.stdout[:500]}") from exc
        if not isinstance(parsed, dict):
            raise ComfyGenerationError("Comfy command returned non-object JSON.")
        return parsed

    def validated_raw_result(self, raw: dict[str, Any], *, expected_kind: Literal["image", "video"], prompt: str) -> SkillRawResult:
        if raw.get("ok") is False:
            raise ComfyGenerationError(json.dumps(raw, indent=2))
        artifacts = raw.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            raise ComfyGenerationError("Comfy command completed without returning artifacts.")

        validated: list[SkillArtifact] = []
        for item in artifacts:
            path_value = item if isinstance(item, str) else item.get("path") if isinstance(item, dict) else None
            if not isinstance(path_value, str) or not path_value.strip():
                raise ComfyGenerationError("Comfy command returned an invalid artifact.")
            path = Path(path_value).expanduser().resolve()
            try:
                path.relative_to(self.artifacts_root)
            except ValueError as exc:
                raise ComfyGenerationError(f"Comfy artifact must be inside Loki artifacts root: {path}") from exc
            if not path.is_file():
                raise ComfyGenerationError(f"Comfy artifact path does not exist: {path}")
            metadata = raw if not isinstance(item, dict) else {**raw, **dict(item.get("metadata", {}))}
            validated.append(
                SkillArtifact(
                    path=str(path),
                    kind=expected_kind,
                    title=first_text(raw.get("title"), raw.get("mode"), f"Comfy {expected_kind}"),
                    prompt=prompt,
                    metadata=metadata,
                )
            )
        return SkillRawResult(artifacts=validated)

    def skill_definition(self, kind: Literal["image", "video"]) -> SkillDefinition:
        return SkillDefinition(
            id=COMFY_DIRECT_SKILL_ID,
            name="Comfy",
            description="Direct Comfy generation through comfy-agent-tools CLIs.",
            path="backend/app/services/comfy_generation.py",
            visibility="user",
            capabilities=["comfy", f"{kind}-generation", "direct-generation"],
            output=SkillOutputConfig(kind=kind),
        )
