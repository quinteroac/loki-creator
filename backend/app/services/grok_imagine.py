from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from app.models import (
    GrokGenerationResponse,
    GrokImageGenerationRequest,
    GrokVideoGenerationRequest,
    SkillArtifact,
    SkillDefinition,
    SkillOutputConfig,
    SkillRawResult,
)
from app.services.card_packager import CardPackagerService


GROK_IMAGE_SKILL_ID = "grok-imagine-image-direct"
GROK_VIDEO_SKILL_ID = "grok-imagine-video-direct"
BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent
GROK_RUNTIME_PATH = REPO_ROOT / "backend" / "skills" / "_grok_runtime" / "grok_imagine_action.py"


class GrokImagineGenerationError(RuntimeError):
    pass


def first_text(*values: object) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


class GrokImagineGenerationService:
    def __init__(self, artifacts_root: Path, *, packager: CardPackagerService | None = None) -> None:
        self.artifacts_root = artifacts_root.resolve()
        self.packager = packager or CardPackagerService()

    def generate_image(self, payload: GrokImageGenerationRequest) -> GrokGenerationResponse:
        prompt = payload.prompt.strip()
        if not prompt:
            raise GrokImagineGenerationError("Grok image generation requires a prompt.")
        self.reject_preview_only_image_media(payload.selected_card_snapshots, payload.attachments)

        params = {
            "skillPrompt": prompt,
            "aspectRatio": payload.aspect_ratio,
            "resolution": payload.resolution,
        }
        raw = self.invoke_runtime("grok-imagine-image", prompt, params, payload.selected_card_snapshots, payload.attachments, payload.context)
        raw_result = self.validated_raw_result(raw, expected_kind="image")
        result = self.packager.package(
            skill=self.skill_definition(
                GROK_IMAGE_SKILL_ID,
                "Grok image",
                "Direct Grok Imagine image generation and editing.",
                "image",
                ["image-generation", "image-editing", "grok", "xai"],
            ),
            run_id=f"generation_{uuid4().hex}",
            prompt=prompt,
            params=params,
            raw_result=raw_result,
        )
        return GrokGenerationResponse(cards=result.cards)

    def generate_video(self, payload: GrokVideoGenerationRequest) -> GrokGenerationResponse:
        prompt = payload.prompt.strip()
        if not prompt:
            raise GrokImagineGenerationError("Grok video generation requires a prompt.")
        self.reject_preview_only_image_media(payload.selected_card_snapshots, payload.attachments)

        params = {
            "skillPrompt": prompt,
            "aspectRatio": payload.aspect_ratio,
            "resolution": payload.resolution,
            "duration": payload.duration,
            "pollTimeoutMs": 15 * 60 * 1000,
        }
        raw = self.invoke_runtime("grok-imagine-video", prompt, params, payload.selected_card_snapshots, payload.attachments, payload.context)
        raw_result = self.validated_raw_result(raw, expected_kind="video")
        result = self.packager.package(
            skill=self.skill_definition(
                GROK_VIDEO_SKILL_ID,
                "Grok video",
                "Direct Grok Imagine video generation.",
                "video",
                ["video-generation", "image-to-video", "grok", "xai"],
            ),
            run_id=f"generation_{uuid4().hex}",
            prompt=prompt,
            params=params,
            raw_result=raw_result,
        )
        return GrokGenerationResponse(cards=result.cards)

    def reject_preview_only_image_media(
        self,
        selected_card_snapshots: list[dict[str, Any]],
        attachments: list[dict[str, Any]],
    ) -> None:
        for snapshot in selected_card_snapshots:
            if not isinstance(snapshot, dict):
                continue
            for asset in snapshot.get("mediaAssets", []):
                if not isinstance(asset, dict) or asset.get("omitted"):
                    continue
                if asset.get("kind") == "image" and not first_text(asset.get("src")):
                    raise GrokImagineGenerationError("Grok image inputs must be local Loki artifacts; preview-only media is not executable.")
            metadata = snapshot.get("metadata")
            if isinstance(metadata, dict) and metadata.get("kind") == "image" and not first_text(metadata.get("artifactUrl")):
                raise GrokImagineGenerationError("Grok image inputs must be local Loki artifacts; preview-only media is not executable.")

        for attachment in attachments:
            if not isinstance(attachment, dict) or attachment.get("omitted"):
                continue
            if attachment.get("kind") == "image" and not first_text(attachment.get("artifactUrl"), attachment.get("src")):
                raise GrokImagineGenerationError("Grok image inputs must be local Loki artifacts; preview-only media is not executable.")

    def invoke_runtime(
        self,
        skill_id: str,
        prompt: str,
        params: dict[str, Any],
        selected_card_snapshots: list[dict[str, Any]],
        attachments: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        runtime = self.load_runtime()
        handler = self.runtime_handler(runtime, skill_id)
        run_id = f"generation_{uuid4().hex}"
        diagnostic_dir = self.artifacts_root / "skills" / skill_id / run_id
        diagnostic_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "runId": run_id,
            "skillId": skill_id,
            "prompt": prompt,
            "params": params,
            "context": context,
            "selectedCardSnapshots": selected_card_snapshots,
            "attachments": attachments,
        }
        self.write_diagnostic_json(diagnostic_dir / "request.json", payload)
        try:
            result = handler(payload)
        except Exception as exc:
            self.write_diagnostic_json(
                diagnostic_dir / "error.json",
                {
                    "error": str(exc),
                    "type": type(exc).__name__,
                },
            )
            raise GrokImagineGenerationError(str(exc)) from exc
        if not isinstance(result, dict):
            self.write_diagnostic_json(
                diagnostic_dir / "error.json",
                {
                    "error": "Grok runtime did not return a JSON object.",
                    "type": type(result).__name__,
                },
            )
            raise GrokImagineGenerationError("Grok runtime did not return a JSON object.")
        self.write_diagnostic_json(diagnostic_dir / "raw-result.json", result)
        return result

    def write_diagnostic_json(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def load_runtime(self) -> Any:
        spec = importlib.util.spec_from_file_location("loki_grok_imagine_action", GROK_RUNTIME_PATH)
        if spec is None or spec.loader is None:
            raise GrokImagineGenerationError(f"Grok runtime not found at {GROK_RUNTIME_PATH}.")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def runtime_handler(self, runtime: Any, skill_id: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
        name = "imagine_image" if skill_id == "grok-imagine-image" else "imagine_video"
        handler = getattr(runtime, name, None)
        if not callable(handler):
            raise GrokImagineGenerationError(f"Grok runtime handler is missing: {name}.")
        return handler

    def validated_raw_result(self, raw: dict[str, Any], *, expected_kind: str) -> SkillRawResult:
        artifacts = raw.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            raise GrokImagineGenerationError("Grok runtime completed without returning artifacts.")

        validated: list[SkillArtifact] = []
        for item in artifacts:
            if not isinstance(item, dict):
                raise GrokImagineGenerationError("Grok runtime returned an invalid artifact.")
            artifact = SkillArtifact.model_validate(item)
            if artifact.kind != expected_kind:
                raise GrokImagineGenerationError(f"Grok artifact kind must be {expected_kind}, got {artifact.kind}.")
            path = Path(artifact.path).expanduser().resolve()
            try:
                path.relative_to(self.artifacts_root)
            except ValueError as exc:
                raise GrokImagineGenerationError(f"Grok artifact must be inside Loki artifacts root: {path}") from exc
            if not path.is_file():
                raise GrokImagineGenerationError(f"Grok artifact path does not exist: {path}")
            artifact.path = str(path)
            validated.append(artifact)

        return SkillRawResult(artifacts=validated)

    def skill_definition(
        self,
        skill_id: str,
        name: str,
        description: str,
        kind: str,
        capabilities: list[str],
    ) -> SkillDefinition:
        return SkillDefinition(
            id=skill_id,
            name=name,
            description=description,
            path="backend/app/services/grok_imagine.py",
            visibility="user",
            capabilities=capabilities,
            output=SkillOutputConfig(kind=kind),
        )
