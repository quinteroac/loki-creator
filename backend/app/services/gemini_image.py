from __future__ import annotations

import json
import mimetypes
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.models import (
    GeminiImageGenerationRequest,
    GeminiImageGenerationResponse,
    SkillArtifact,
    SkillDefinition,
    SkillOutputConfig,
    SkillRawResult,
)
from app.services.card_packager import CardPackagerService


GEMINI_IMAGE_SKILL_ID = "gemini-image-direct"
BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent


class GeminiImageGenerationError(RuntimeError):
    pass


def first_text(*values: object) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


class GeminiImageGenerationService:
    def __init__(self, artifacts_root: Path, *, packager: CardPackagerService | None = None) -> None:
        self.artifacts_root = artifacts_root.resolve()
        self.packager = packager or CardPackagerService()

    def generate(self, payload: GeminiImageGenerationRequest) -> GeminiImageGenerationResponse:
        prompt = payload.prompt.strip()
        if not prompt:
            raise GeminiImageGenerationError("Gemini image generation requires a prompt.")
        self.reject_preview_only_image_media(payload.selected_card_snapshots, payload.attachments)

        run_id = f"generation_{uuid4().hex}"
        run_dir = self.output_dir(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        selected_images = self.resolve_selected_image_paths(payload.selected_card_snapshots, payload.attachments, payload.context)
        params = {
            "prompt": prompt,
            "skillPrompt": prompt,
            "resolution": payload.resolution,
            "model": payload.model,
        }
        raw = self.invoke_agy(prompt, params, run_dir, selected_images)
        raw_result = self.validated_raw_result(raw)
        result = self.packager.package(
            skill=self.skill_definition(),
            run_id=run_id,
            prompt=prompt,
            params=params,
            raw_result=raw_result,
        )
        return GeminiImageGenerationResponse(cards=result.cards)

    def resolve_agy_bin(self) -> str:
        configured_bin = os.environ.get("LOKI_GEMINI_BIN")
        if configured_bin:
            configured_path = Path(configured_bin).expanduser()
            if shutil.which(configured_bin) or configured_path.exists():
                return str(configured_path if configured_path.exists() else configured_bin)
            raise GeminiImageGenerationError(f"Antigravity CLI executable not found: {configured_bin}")

        path_bin = shutil.which("agy")
        if path_bin:
            return path_bin

        raise GeminiImageGenerationError(
            "Antigravity CLI executable not found. Set LOKI_GEMINI_BIN to the absolute agy binary path "
            "or start the backend with agy available on PATH."
        )

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
                    raise GeminiImageGenerationError("Gemini image inputs must be local Loki artifacts; preview-only media is not executable.")
            metadata = snapshot.get("metadata")
            if isinstance(metadata, dict) and metadata.get("kind") == "image" and not first_text(metadata.get("artifactUrl")):
                raise GeminiImageGenerationError("Gemini image inputs must be local Loki artifacts; preview-only media is not executable.")

        for attachment in attachments:
            if not isinstance(attachment, dict) or attachment.get("omitted"):
                continue
            if attachment.get("kind") == "image" and not first_text(attachment.get("artifactUrl"), attachment.get("src")):
                raise GeminiImageGenerationError("Gemini image inputs must be local Loki artifacts; preview-only media is not executable.")

    def resolve_selected_image_paths(
        self,
        selected_card_snapshots: list[dict[str, Any]],
        attachments: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> list[Path]:
        paths: list[Path] = []

        for reference in context.get("localMediaReferences", []) if isinstance(context.get("localMediaReferences"), list) else []:
            if not isinstance(reference, dict) or reference.get("kind") != "image":
                continue
            self.append_local_path(paths, first_text(reference.get("path")))

        for attachment in attachments:
            if not isinstance(attachment, dict) or attachment.get("omitted") or attachment.get("kind") != "image":
                continue
            self.append_artifact_url(paths, first_text(attachment.get("artifactUrl"), attachment.get("src")))

        for snapshot in selected_card_snapshots:
            if not isinstance(snapshot, dict):
                continue
            metadata = snapshot.get("metadata")
            if isinstance(metadata, dict) and metadata.get("kind") == "image":
                self.append_artifact_url(paths, first_text(metadata.get("artifactUrl")))
            for asset in snapshot.get("mediaAssets", []):
                if not isinstance(asset, dict) or asset.get("omitted") or asset.get("kind") != "image":
                    continue
                self.append_artifact_url(paths, first_text(asset.get("src")))

        return paths

    def append_artifact_url(self, paths: list[Path], artifact_url: str) -> None:
        if not artifact_url.startswith("/api/artifacts/"):
            return
        self.append_local_path(paths, str(self.artifacts_root / artifact_url.removeprefix("/api/artifacts/")))

    def append_local_path(self, paths: list[Path], path_value: str) -> None:
        if not path_value:
            return
        path = Path(path_value).expanduser().resolve()
        try:
            path.relative_to(self.artifacts_root)
        except ValueError:
            return
        if path.is_file() and path not in paths:
            paths.append(path)

    def invoke_agy(
        self,
        prompt: str,
        params: dict[str, Any],
        run_dir: Path,
        selected_images: list[Path],
    ) -> dict[str, Any]:
        agy_bin = self.resolve_agy_bin()
        agy_prompt = self.build_agy_prompt(prompt, params, run_dir, selected_images)
        command = [
            agy_bin,
            "--dangerously-skip-permissions",
            "--add-dir",
            str(run_dir),
            "--print-timeout",
            os.environ.get("LOKI_GEMINI_DIRECT_PRINT_TIMEOUT", "5m"),
            "--model",
            first_text(params.get("model")),
            "-p",
            agy_prompt,
        ]
        process = subprocess.run(
            command,
            text=True,
            capture_output=True,
            cwd=str(REPO_ROOT),
            timeout=int(os.environ.get("LOKI_GEMINI_DIRECT_TIMEOUT_SECONDS", "930")),
            check=False,
        )
        (run_dir / "agy-stdout.log").write_text(process.stdout, encoding="utf-8")
        (run_dir / "agy-stderr.log").write_text(process.stderr, encoding="utf-8")
        if process.returncode != 0:
            message = process.stderr.strip() or process.stdout.strip() or "Gemini image generation failed."
            raise GeminiImageGenerationError(message)
        return self.parse_agy_stdout(process.stdout)

    def parse_agy_stdout(self, stdout: str) -> dict[str, Any]:
        decoder = json.JSONDecoder()
        objects: list[tuple[dict[str, Any], int]] = []
        index = 0
        while index < len(stdout):
            character = stdout[index]
            if character != "{":
                index += 1
                continue
            try:
                parsed, end_index = decoder.raw_decode(stdout[index:])
            except json.JSONDecodeError:
                index += 1
                continue
            if isinstance(parsed, dict):
                objects.append((parsed, index + end_index))
                index += end_index
                continue
            index += 1

        if not objects:
            raise GeminiImageGenerationError("Gemini image generation did not return a final valid JSON object.")
        if len(objects) > 1:
            raise GeminiImageGenerationError("Gemini image generation returned multiple possible final JSON objects.")
        parsed, end_index = objects[0]
        if stdout[end_index:].strip():
            raise GeminiImageGenerationError("Gemini image generation did not return a final valid JSON object.")
        return parsed

    def build_agy_prompt(
        self,
        prompt: str,
        params: dict[str, Any],
        run_dir: Path,
        selected_images: list[Path],
    ) -> str:
        selected_image_lines = "\n".join(f"- {path}" for path in selected_images) or "- none"
        return f"""Use Gemini image generation/editing capabilities through Antigravity CLI to create image artifacts for Loki Creator.

User request:
{prompt}

Resolution:
{first_text(params.get("resolution"))}

Selected local image inputs:
{selected_image_lines}

Execution contract:
- Save every final image file directly inside this directory: {run_dir}
- If selected local image inputs are listed and the user asks for an edit, treat the first selected image as the edit target.
- Preserve unmentioned content for edits.
- Do not use inline data URLs, previews, remote URLs, or files outside the listed local paths as executable image inputs.
- Do not use ComfyUI, comfy-agent-tools, comfy-imagegen, comfy-image-generate, comfy-image-edit, comfy-image-upscale, or any backend/skills/comfy-* skill.
- Do not write final images outside the requested directory.
- Do not modify repository source files.
- The final response must end with exactly one valid JSON object and no trailing prose, markdown, progress text, or code fences.
- Return exactly this JSON shape:
{{"images":[{{"title":"short card title","prompt":"final generation or edit prompt","imagePath":"absolute path to final image","mimeType":"image/png or image/jpeg or image/webp"}}],"diagnostics":[]}}
"""

    def validated_raw_result(self, raw: dict[str, Any]) -> SkillRawResult:
        images = raw.get("images")
        if not isinstance(images, list) or not images:
            raise GeminiImageGenerationError("Gemini image generation completed without returning images.")

        validated: list[SkillArtifact] = []
        for index, item in enumerate(images, start=1):
            if not isinstance(item, dict):
                raise GeminiImageGenerationError("Gemini image generation returned an invalid image entry.")
            image_path_value = first_text(item.get("imagePath"))
            if not image_path_value:
                raise GeminiImageGenerationError(f"Gemini image {index} did not include imagePath.")
            image_path = Path(image_path_value).expanduser().resolve()
            try:
                image_path.relative_to(self.artifacts_root)
            except ValueError as exc:
                raise GeminiImageGenerationError(f"Gemini imagePath must be inside Loki artifacts root: {image_path}") from exc
            if not image_path.is_file():
                raise GeminiImageGenerationError(f"Gemini imagePath does not exist: {image_path}")

            mime_type = first_text(item.get("mimeType")) or mimetypes.guess_type(image_path.name)[0] or "image/png"
            if not mime_type.startswith("image/"):
                raise GeminiImageGenerationError(f"Gemini output is not an image: {mime_type}")
            validated.append(
                SkillArtifact(
                    path=str(image_path),
                    kind="image",
                    mimeType=mime_type,
                    title=first_text(item.get("title"), f"Gemini image {index}"),
                    prompt=first_text(item.get("prompt")),
                    metadata={"tags": ["gemini"], "capabilities": ["image-generation", "image-editing"]},
                )
            )

        diagnostics = raw.get("diagnostics") if isinstance(raw.get("diagnostics"), list) else []
        return SkillRawResult(artifacts=validated, diagnostics=diagnostics)

    def output_dir(self, run_id: str) -> Path:
        return self.artifacts_root / "generations" / "gemini-image" / run_id

    def skill_definition(self) -> SkillDefinition:
        return SkillDefinition(
            id=GEMINI_IMAGE_SKILL_ID,
            name="Gemini image",
            description="Direct Gemini image generation and editing through Antigravity CLI.",
            path="backend/app/services/gemini_image.py",
            visibility="user",
            capabilities=["image-generation", "image-editing", "gemini", "antigravity"],
            output=SkillOutputConfig(kind="image"),
        )
