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

try:
    from PIL import Image
except ModuleNotFoundError:
    Image = None


COMFY_DIRECT_SKILL_ID = "comfy-direct"
BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent
IMAGE_DIMENSIONS = {
    "1:1": (1024, 1024),
    "4:3": (1152, 864),
    "16:9": (1344, 768),
    "9:16": (768, 1344),
}
FORBIDDEN_REFERENCE_PHRASES = (
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
BERNINI_IMAGE_PROFILE = "wan22-bernini-image"
KREA2_IMAGE_PROFILE = "krea2-turbo"
BERNINI_MODEL_OVERRIDES = {
    "unet-high": "diffusion_models/Wan22_Bernini_HIGH_mxfp8.safetensors",
    "unet-low": "diffusion_models/Wan22_Bernini_LOW_mxfp8.safetensors",
    "lora": "loras/wan22/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16_.safetensors",
    "text-encoder": "clip/nsfw_wan_umt5-xxl_fp8_scaled.safetensors",
    "vae": "vae/wan_2.1_vae.safetensors",
}


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
        "krea": KREA2_IMAGE_PROFILE,
        "krea2": KREA2_IMAGE_PROFILE,
        "krea-2": KREA2_IMAGE_PROFILE,
        "krea2-fp8": KREA2_IMAGE_PROFILE,
        "krea2-turbo-fp8": KREA2_IMAGE_PROFILE,
        "bernini": BERNINI_IMAGE_PROFILE,
        "wan22-bernini": BERNINI_IMAGE_PROFILE,
        "wan-bernini-image": BERNINI_IMAGE_PROFILE,
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


def image_cli_mode(image_mode: str, profile: str) -> str:
    if image_mode == "r2i":
        return "krea2-generate" if profile == KREA2_IMAGE_PROFILE else "generate"
    if image_mode == "generate" and profile == KREA2_IMAGE_PROFILE:
        return "krea2-generate"
    return image_mode


def divisible_by_16(value: int) -> int:
    lower = max(16, value - (value % 16))
    upper = lower if value % 16 == 0 else lower + 16
    return lower if abs(value - lower) <= abs(upper - value) else upper


def reject_reference_language(prompt: str) -> None:
    lowered = prompt.lower()
    for phrase in FORBIDDEN_REFERENCE_PHRASES:
        if phrase in lowered:
            raise ComfyGenerationError(
                "Comfy image r2i prompt must be a standalone visual description. "
                f"Remove reference-language phrase: {phrase!r}."
            )


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
        if params.get("modelProfile") == BERNINI_IMAGE_PROFILE:
            raw = self.extract_bernini_image_result(raw, out_dir)
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

    def image_dimensions(self, path: Path) -> tuple[int, int]:
        if Image is None:
            raise ComfyGenerationError("Pillow is required to read image dimensions for FLUX Klein image editing.")
        try:
            with Image.open(path) as image:
                width, height = image.size
        except Exception as exc:
            raise ComfyGenerationError(f"Could not read image dimensions for {path}.") from exc
        if width <= 0 or height <= 0:
            raise ComfyGenerationError(f"Image dimensions must be positive for {path}.")
        return width, height

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
        if payload.image_mode in {"generate", "r2i", "edit"} and not profile:
            raise ComfyGenerationError("Comfy image generation requires modelProfile.")
        if payload.image_mode in {"r2i", "edit", "upscale"} and not media["image"]:
            raise ComfyGenerationError(f"Comfy image {payload.image_mode} requires one selected or attached image.")
        if payload.image_mode == "r2i":
            reject_reference_language(prompt)
        if profile == KREA2_IMAGE_PROFILE and payload.image_mode not in {"generate", "r2i"}:
            raise ComfyGenerationError("Krea2 Turbo only supports Comfy image generate and r2i modes.")

        if payload.image_mode == "edit" and profile == BERNINI_IMAGE_PROFILE:
            return self.build_bernini_image_command(payload, prompt, out_dir, media)

        cli_mode = image_cli_mode(payload.image_mode, profile)
        command = [self.executable("comfy-imagegen"), cli_mode, "--out", str(out_dir)]
        if payload.image_mode in {"generate", "r2i", "edit", "upscale"}:
            command.extend(["--models-dir", str(self.models_dir())])
        if payload.image_mode in {"generate", "r2i", "edit"}:
            command.extend(["--prompt", prompt])
        if payload.image_mode in {"edit", "upscale"}:
            command.extend(["--input", str(media["image"][0])])
        if payload.image_mode in {"generate", "r2i"}:
            width, height = IMAGE_DIMENSIONS[payload.aspect_ratio]
            command.extend(["--width", str(width), "--height", str(height)])
        if payload.image_mode == "edit" and profile == "flux-klein-9b-snofs":
            input_width, input_height = self.image_dimensions(media["image"][0])
            command.extend(["--width", str(divisible_by_16(input_width)), "--height", str(divisible_by_16(input_height))])
        if payload.seed is not None:
            command.extend(["--seed", str(payload.seed)])

        capability = f"imagegen.{cli_mode}"
        cwd = self.write_run_comfy_config(out_dir.parent, capability=capability, model_profile=profile) if profile else REPO_ROOT
        params = {
            "tool": payload.tool,
            "imageMode": payload.image_mode,
            "modelProfile": profile,
            "aspectRatio": payload.aspect_ratio,
            "seed": payload.seed,
        }
        return command, cwd, "image", params

    def build_bernini_image_command(
        self,
        payload: ComfyGenerationRequest,
        prompt: str,
        out_dir: Path,
        media: dict[str, list[Path]],
    ) -> tuple[list[str], Path, Literal["image"], dict[str, Any]]:
        width, height = IMAGE_DIMENSIONS[payload.aspect_ratio]
        command = [
            self.executable("comfy-videogen"),
            "wan22-bernini",
            "--out",
            str(out_dir),
            "--models-dir",
            str(self.models_dir()),
            "--prompt",
            prompt,
            "--reference-image",
            str(media["image"][0]),
            "--width",
            str(width),
            "--height",
            str(height),
            "--fps",
            str(WAN_FPS),
            "--length",
            "1",
        ]
        for key, model_path in BERNINI_MODEL_OVERRIDES.items():
            command.extend([f"--{key}", str(self.models_dir() / model_path)])
        if payload.seed is not None:
            command.extend(["--seed", str(payload.seed)])

        cwd = self.write_run_comfy_config(out_dir.parent, capability="videogen.wan22-bernini", model_profile="wan22-bernini")
        params = {
            "tool": payload.tool,
            "imageMode": payload.image_mode,
            "modelProfile": BERNINI_IMAGE_PROFILE,
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
        self.validate_comfy_cuda(command, cwd, env)
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

    def extract_bernini_image_result(self, raw: dict[str, Any], out_dir: Path) -> dict[str, Any]:
        artifacts = raw.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            raise ComfyGenerationError("Comfy Bernini image edit completed without returning a video artifact to extract.")

        source_video = ""
        for artifact in artifacts:
            path_value = artifact if isinstance(artifact, str) else artifact.get("path") if isinstance(artifact, dict) else None
            if isinstance(path_value, str) and Path(path_value).suffix.lower() in {".mp4", ".mov", ".webm"}:
                source_video = path_value
                break
        if not source_video:
            raise ComfyGenerationError("Comfy Bernini image edit did not return a video artifact that can be converted to an image.")
        if shutil.which("ffmpeg") is None:
            raise ComfyGenerationError("ffmpeg is required to extract the Bernini image edit frame.")

        image_path = out_dir / "bernini-image-edit.png"
        process = subprocess.run(
            ["ffmpeg", "-y", "-i", source_video, "-frames:v", "1", str(image_path)],
            text=True,
            capture_output=True,
            check=False,
        )
        if process.returncode != 0:
            message = process.stderr.strip() or process.stdout.strip() or "Could not extract Bernini image edit frame."
            raise ComfyGenerationError(message)
        if not image_path.is_file():
            raise ComfyGenerationError("ffmpeg completed but did not create the Bernini image edit artifact.")

        return {
            **raw,
            "kind": "image",
            "mode": BERNINI_IMAGE_PROFILE,
            "title": "Bernini image edit",
            "artifacts": [str(image_path)],
            "sourceVideoArtifact": source_video,
        }

    def validate_comfy_cuda(self, command: list[str], cwd: Path, env: dict[str, str]) -> None:
        if not self.env_value_enabled(env.get("LOKI_REQUIRE_COMFY_CUDA")):
            return
        if not command or Path(command[0]).name not in {"comfy-imagegen", "comfy-videogen"}:
            return

        executable = shutil.which(command[0])
        if not executable:
            raise ComfyGenerationError(f"Comfy CLI not found while validating CUDA: {command[0]}")

        python = self.python_from_cli_shebang(Path(executable))
        if not python:
            raise ComfyGenerationError(f"Could not determine Python runtime for {command[0]} to validate CUDA.")

        check = subprocess.run(
            [
                python,
                "-c",
                (
                    "import sys, torch; "
                    "ok = torch.cuda.is_available(); "
                    "print(f'torch={torch.__version__} torch_cuda={torch.version.cuda} cuda_available={ok} device_count={torch.cuda.device_count()}', file=sys.stderr); "
                    "sys.exit(0 if ok else 42)"
                ),
            ],
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        if check.returncode != 0:
            detail = (check.stderr or check.stdout).strip()
            raise ComfyGenerationError(
                "Comfy CUDA validation failed. PyTorch cannot see a CUDA GPU, so Loki refused to run Comfy on CPU. "
                f"{detail} Set LOKI_REQUIRE_COMFY_CUDA=0 only if CPU generation is intentional."
            )

    def env_value_enabled(self, value: str | None) -> bool:
        return (value or "").strip().lower() in {"1", "true", "yes", "on"}

    def python_from_cli_shebang(self, executable: Path) -> str | None:
        try:
            first_line = executable.read_text(encoding="utf-8", errors="ignore").splitlines()[0]
        except (OSError, IndexError):
            return None
        if not first_line.startswith("#!"):
            return None
        python = first_line[2:].strip().split()[0]
        if "python" not in Path(python).name:
            return None
        return python

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
