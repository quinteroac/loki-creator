from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.models import (
    CodexImageGenerationRequest,
    CodexImageGenerationResponse,
    SkillArtifact,
    SkillDefinition,
    SkillOutputConfig,
    SkillRawResult,
)
from app.services.card_packager import CardPackagerService


CODEX_IMAGE_SKILL_ID = "codex-image-direct"
BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent
IMAGEGEN_ACTION_PATH = REPO_ROOT / "backend" / "skills" / "imagegen" / "scripts" / "card_action.py"


class CodexImageGenerationError(RuntimeError):
    pass


def first_text(*values: object) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


class CodexImageGenerationService:
    def __init__(self, artifacts_root: Path, *, packager: CardPackagerService | None = None) -> None:
        self.artifacts_root = artifacts_root.resolve()
        self.packager = packager or CardPackagerService()

    def generate(self, payload: CodexImageGenerationRequest) -> CodexImageGenerationResponse:
        prompt = payload.prompt.strip()
        if not prompt:
            raise CodexImageGenerationError("Codex image generation requires a prompt.")
        self.reject_preview_only_image_media(payload.selected_card_snapshots, payload.attachments)

        params = {
            "prompt": prompt,
            "skillPrompt": prompt,
            "resolution": payload.resolution,
        }
        raw = self.invoke_action(prompt, params, payload.selected_card_snapshots, payload.attachments, payload.context)
        raw_result = self.validated_raw_result(raw)
        result = self.packager.package(
            skill=self.skill_definition(),
            run_id=f"generation_{uuid4().hex}",
            prompt=prompt,
            params=params,
            raw_result=raw_result,
        )
        return CodexImageGenerationResponse(cards=result.cards)

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
                    raise CodexImageGenerationError("Codex image inputs must be local Loki artifacts; preview-only media is not executable.")
            metadata = snapshot.get("metadata")
            if isinstance(metadata, dict) and metadata.get("kind") == "image" and not first_text(metadata.get("artifactUrl")):
                raise CodexImageGenerationError("Codex image inputs must be local Loki artifacts; preview-only media is not executable.")

        for attachment in attachments:
            if not isinstance(attachment, dict) or attachment.get("omitted"):
                continue
            if attachment.get("kind") == "image" and not first_text(attachment.get("artifactUrl"), attachment.get("src")):
                raise CodexImageGenerationError("Codex image inputs must be local Loki artifacts; preview-only media is not executable.")

    def invoke_action(
        self,
        prompt: str,
        params: dict[str, Any],
        selected_card_snapshots: list[dict[str, Any]],
        attachments: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        if not IMAGEGEN_ACTION_PATH.is_file():
            raise CodexImageGenerationError(f"Codex image action not found at {IMAGEGEN_ACTION_PATH}.")

        run_id = f"generation_{uuid4().hex}"
        action_context = {
            **context,
            "selectedCardSnapshots": selected_card_snapshots,
        }
        action_payload = {
            "runId": run_id,
            "skillId": "imagegen",
            "prompt": prompt,
            "params": params,
            "context": action_context,
            "selectedCardSnapshots": selected_card_snapshots,
            "attachments": attachments,
        }
        process = subprocess.run(
            [sys.executable, str(IMAGEGEN_ACTION_PATH)],
            input=json.dumps(action_payload),
            text=True,
            capture_output=True,
            cwd=str(REPO_ROOT),
            env={**os.environ, "LOKI_ARTIFACTS_ROOT": str(self.artifacts_root)},
            timeout=int(os.environ.get("LOKI_CODEX_DIRECT_TIMEOUT_SECONDS", "930")),
            check=False,
        )
        if process.returncode != 0:
            message = process.stderr.strip() or process.stdout.strip() or "Codex image action failed."
            raise CodexImageGenerationError(message)
        try:
            result = json.loads(process.stdout)
        except json.JSONDecodeError as exc:
            raise CodexImageGenerationError("Codex image action did not return valid JSON.") from exc
        if not isinstance(result, dict):
            raise CodexImageGenerationError("Codex image action did not return a JSON object.")
        return result

    def validated_raw_result(self, raw: dict[str, Any]) -> SkillRawResult:
        artifacts = raw.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            raise CodexImageGenerationError("Codex image action completed without returning artifacts.")

        validated: list[SkillArtifact] = []
        for item in artifacts:
            if not isinstance(item, dict):
                raise CodexImageGenerationError("Codex image action returned an invalid artifact.")
            artifact = SkillArtifact.model_validate(item)
            if artifact.kind != "image":
                raise CodexImageGenerationError(f"Codex artifact kind must be image, got {artifact.kind}.")
            path = Path(artifact.path).expanduser().resolve()
            try:
                path.relative_to(self.artifacts_root)
            except ValueError as exc:
                raise CodexImageGenerationError(f"Codex artifact must be inside Loki artifacts root: {path}") from exc
            if not path.is_file():
                raise CodexImageGenerationError(f"Codex artifact path does not exist: {path}")
            artifact.path = str(path)
            validated.append(artifact)

        diagnostics = raw.get("diagnostics") if isinstance(raw.get("diagnostics"), list) else []
        return SkillRawResult(artifacts=validated, diagnostics=diagnostics)

    def skill_definition(self) -> SkillDefinition:
        return SkillDefinition(
            id=CODEX_IMAGE_SKILL_ID,
            name="Codex image",
            description="Direct Codex image generation and editing.",
            path="backend/app/services/codex_image.py",
            visibility="user",
            capabilities=["image-generation", "image-editing", "codex"],
            output=SkillOutputConfig(kind="image"),
        )
