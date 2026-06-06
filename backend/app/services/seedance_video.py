from __future__ import annotations

import base64
import json
import mimetypes
import os
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from uuid import uuid4

from app.models import (
    SeedanceVideoGenerationRequest,
    SeedanceVideoGenerationResponse,
    SkillArtifact,
    SkillDefinition,
    SkillRawResult,
)
from app.models.skills import SkillOutputConfig
from app.services.card_packager import CardPackagerService


OPENROUTER_BASE_URL = "https://openrouter.ai"
SEEDANCE_MODEL = "bytedance/seedance-2.0-fast"
SEEDANCE_SKILL_ID = "openrouter-seedance-direct"
SEEDANCE_RESOLUTION = "480p"
IMAGE_MIME_EXTENSIONS = {"image/png": ".png", "image/jpeg": ".jpg", "image/jpg": ".jpg", "image/webp": ".webp"}
AUDIO_MIME_EXTENSIONS = {
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/mp4": ".m4a",
    "audio/aac": ".aac",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/webm": ".webm",
}


class SeedanceVideoGenerationError(RuntimeError):
    pass


def first_text(*values: object) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


class SeedanceVideoGenerationService:
    def __init__(
        self,
        artifacts_root: Path,
        *,
        packager: CardPackagerService | None = None,
        poll_interval_seconds: float = 10,
        poll_timeout_seconds: float = 15 * 60,
    ) -> None:
        self.artifacts_root = artifacts_root.resolve()
        self.packager = packager or CardPackagerService()
        self.poll_interval_seconds = poll_interval_seconds
        self.poll_timeout_seconds = poll_timeout_seconds

    def generate(self, payload: SeedanceVideoGenerationRequest) -> SeedanceVideoGenerationResponse:
        prompt = payload.prompt.strip()
        if not prompt:
            raise SeedanceVideoGenerationError("Seedance video generation requires a prompt.")

        run_id = f"generation_{uuid4().hex}"
        request_body = self.build_request_body(payload, prompt)
        started = self.request_json("POST", "/api/v1/videos", request_body)
        job_id = first_text(started.get("id"))
        polling_url = first_text(started.get("polling_url"))
        if not job_id and not polling_url:
            raise SeedanceVideoGenerationError("OpenRouter video response did not include a job id or polling URL.")

        completed = self.poll_video(job_id, polling_url)
        video_url = self.video_url(completed, job_id)
        output_path, mime_type = self.download_video(video_url, self.output_dir(run_id) / "seedance-video.mp4")

        raw_result = SkillRawResult(
            artifacts=[
                SkillArtifact(
                    path=str(output_path),
                    kind="video",
                    mimeType=mime_type,
                    title="Seedance video",
                    prompt=prompt,
                    metadata={
                        "provider": "openrouter",
                        "model": SEEDANCE_MODEL,
                        "jobId": first_text(completed.get("id"), job_id),
                        "generationId": first_text(completed.get("generation_id"), started.get("generation_id")),
                        "status": first_text(completed.get("status")),
                        "duration": payload.duration,
                        "resolution": SEEDANCE_RESOLUTION,
                        "aspectRatio": payload.aspect_ratio,
                        "source": "reference-to-video",
                        "inputImageCount": 1,
                        "inputAudioCount": self.input_audio_count(request_body),
                        "usage": completed.get("usage") if isinstance(completed.get("usage"), dict) else None,
                    },
                )
            ]
        )
        result = self.packager.package(
            skill=self.seedance_skill_definition(),
            run_id=run_id,
            prompt=prompt,
            params={"aspectRatio": payload.aspect_ratio, "duration": payload.duration, "resolution": SEEDANCE_RESOLUTION},
            raw_result=raw_result,
        )
        return SeedanceVideoGenerationResponse(cards=result.cards)

    def build_request_body(self, payload: SeedanceVideoGenerationRequest, prompt: str) -> dict[str, Any]:
        image_reference = self.first_reference(payload, "image")
        if image_reference is None:
            raise SeedanceVideoGenerationError("Seedance video generation requires one selected or attached image.")

        references = [image_reference]
        audio_reference = self.first_reference(payload, "audio")
        if audio_reference is not None:
            references.append(audio_reference)

        return {
            "model": SEEDANCE_MODEL,
            "prompt": prompt,
            "resolution": SEEDANCE_RESOLUTION,
            "aspect_ratio": payload.aspect_ratio,
            "duration": payload.duration,
            "generate_audio": True,
            "input_references": references,
        }

    def first_reference(self, payload: SeedanceVideoGenerationRequest, media_kind: str) -> dict[str, Any] | None:
        local_reference = self.first_reference_from_local_media(payload, media_kind)
        if local_reference is not None:
            return local_reference
        selected = self.first_reference_from_snapshots(payload.selected_card_snapshots, media_kind)
        if selected is not None:
            return selected
        return self.first_reference_from_attachments(payload.attachments, media_kind)

    def first_reference_from_local_media(self, payload: SeedanceVideoGenerationRequest, media_kind: str) -> dict[str, Any] | None:
        context = payload.context if isinstance(payload.context, dict) else {}
        for references in (context.get("localMediaReferences"),):
            if not isinstance(references, list):
                continue
            for reference in references:
                if not isinstance(reference, dict) or first_text(reference.get("kind")) != media_kind:
                    continue
                source = first_text(reference.get("path"), reference.get("artifactUrl"))
                if source:
                    return self.reference_object(source, media_kind)
        return None

    def first_reference_from_snapshots(self, snapshots: list[dict[str, Any]], media_kind: str) -> dict[str, Any] | None:
        for snapshot in snapshots:
            source = self.reference_source_from_snapshot(snapshot, media_kind)
            if source:
                return self.reference_object(source, media_kind)
        return None

    def reference_source_from_snapshot(self, snapshot: dict[str, Any], media_kind: str) -> str:
        assets = snapshot.get("mediaAssets")
        if isinstance(assets, list):
            for asset in assets:
                if not isinstance(asset, dict) or asset.get("omitted"):
                    continue
                if first_text(asset.get("kind")) == media_kind:
                    source = first_text(asset.get("src"))
                    if source:
                        return source

        metadata = snapshot.get("metadata")
        if isinstance(metadata, dict) and first_text(metadata.get("kind")) == media_kind:
            source = first_text(metadata.get("artifactUrl"))
            if source:
                return source

        return ""

    def first_reference_from_attachments(self, attachments: list[dict[str, Any]], media_kind: str) -> dict[str, Any] | None:
        for attachment in attachments:
            if not isinstance(attachment, dict) or attachment.get("omitted"):
                continue
            if first_text(attachment.get("kind")) != media_kind:
                continue
            source = first_text(attachment.get("artifactUrl"), attachment.get("src"))
            if source:
                return self.reference_object(source, media_kind)
        return None

    def reference_object(self, source: str, media_kind: str) -> dict[str, Any]:
        url = self.normalize_reference_url(source, media_kind)
        if media_kind == "image":
            return {"type": "image_url", "image_url": {"url": url}}
        if media_kind == "audio":
            return {"type": "audio_url", "audio_url": {"url": url}}
        raise SeedanceVideoGenerationError(f"Unsupported Seedance reference kind: {media_kind}")

    def normalize_reference_url(self, source: str, media_kind: str) -> str:
        if source.startswith("data:"):
            raise SeedanceVideoGenerationError("Seedance references must be local Loki artifacts; inline dataUrl is not an executable media input.")
        artifact_path = self.resolve_artifact_src(source)
        if artifact_path is not None:
            return self.path_to_data_url(artifact_path, media_kind)
        path = Path(source).expanduser().resolve()
        try:
            path.relative_to(self.artifacts_root)
        except ValueError as exc:
            raise SeedanceVideoGenerationError(f"Seedance reference must be a local Loki artifact, got: {source[:80]}") from exc
        if not path.is_file():
            raise SeedanceVideoGenerationError(f"Seedance reference path does not exist: {path}")
        return self.path_to_data_url(path, media_kind)

    def resolve_artifact_src(self, source: str) -> Path | None:
        if not source.startswith("/api/artifacts/"):
            return None
        artifact_path = (self.artifacts_root / source.removeprefix("/api/artifacts/")).resolve()
        try:
            artifact_path.relative_to(self.artifacts_root)
        except ValueError:
            return None
        return artifact_path if artifact_path.is_file() else None

    def path_to_data_url(self, path: Path, media_kind: str) -> str:
        mime_type = mimetypes.guess_type(path.name)[0] or ("image/png" if media_kind == "image" else "audio/mpeg")
        if media_kind == "image" and not mime_type.startswith("image/"):
            raise SeedanceVideoGenerationError(f"Selected artifact is not an image: {path.name}")
        if media_kind == "audio" and not mime_type.startswith("audio/"):
            raise SeedanceVideoGenerationError(f"Selected artifact is not an audio file: {path.name}")
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    def request_json(self, method: str, path_or_url: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Authorization": f"Bearer {self.api_key()}"}
        if body is not None:
            headers["Content-Type"] = "application/json"

        url = path_or_url if path_or_url.startswith("http") else f"{OPENROUTER_BASE_URL}{path_or_url}"
        request = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=120) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise SeedanceVideoGenerationError(f"OpenRouter API returned HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise SeedanceVideoGenerationError(f"OpenRouter API request failed: {exc.reason}") from exc

    def api_key(self) -> str:
        key = first_text(os.environ.get("OPENROUTER_API_KEY"))
        if not key:
            raise SeedanceVideoGenerationError("OpenRouter auth not found. Set OPENROUTER_API_KEY.")
        return key

    def poll_video(self, job_id: str, polling_url: str) -> dict[str, Any]:
        deadline = time.time() + self.poll_timeout_seconds
        poll_path = polling_url or f"/api/v1/videos/{job_id}"
        last: dict[str, Any] = {}
        while time.time() <= deadline:
            last = self.request_json("GET", self.absolute_or_api_path(poll_path))
            status = first_text(last.get("status"))
            if status == "completed":
                return last
            if status in {"failed", "cancelled", "expired"}:
                error = first_text(last.get("error"))
                raise SeedanceVideoGenerationError(error or f"OpenRouter Seedance video generation {status}.")
            time.sleep(max(self.poll_interval_seconds, 0.25))
        raise SeedanceVideoGenerationError(f"Timed out waiting for OpenRouter Seedance video after {int(self.poll_timeout_seconds)}s.")

    def absolute_or_api_path(self, path_or_url: str) -> str:
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            return path_or_url
        if path_or_url.startswith("/"):
            return path_or_url
        return urljoin("/api/v1/videos/", path_or_url)

    def video_url(self, completed: dict[str, Any], job_id: str) -> str:
        unsigned_urls = completed.get("unsigned_urls")
        if isinstance(unsigned_urls, list):
            for value in unsigned_urls:
                url = first_text(value)
                if url:
                    return url
        if job_id:
            return f"{OPENROUTER_BASE_URL}/api/v1/videos/{job_id}/content?index=0"
        raise SeedanceVideoGenerationError("OpenRouter video response did not include a downloadable video URL.")

    def download_video(self, url: str, destination: Path) -> tuple[Path, str]:
        request = Request(url, headers={"Authorization": f"Bearer {self.api_key()}", "User-Agent": "loki-creator"})
        try:
            with urlopen(request, timeout=300) as response:
                content_type = response.headers.get_content_type() or "video/mp4"
                extension = mimetypes.guess_extension(content_type) or ".mp4"
                path = destination.with_suffix(extension)
                path.write_bytes(response.read())
                return path, content_type
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise SeedanceVideoGenerationError(f"OpenRouter video download returned HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise SeedanceVideoGenerationError(f"OpenRouter video download failed: {exc.reason}") from exc

    def output_dir(self, run_id: str) -> Path:
        path = self.artifacts_root / "generations" / "seedance-video" / run_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def input_audio_count(self, request_body: dict[str, Any]) -> int:
        references = request_body.get("input_references")
        if not isinstance(references, list):
            return 0
        return sum(1 for reference in references if isinstance(reference, dict) and first_text(reference.get("type")) == "audio_url")

    def seedance_skill_definition(self) -> SkillDefinition:
        return SkillDefinition(
            id=SEEDANCE_SKILL_ID,
            name="Seedance video",
            description="Direct OpenRouter Seedance reference-to-video generation.",
            path="backend/app/services/seedance_video.py",
            visibility="user",
            capabilities=["video-generation", "reference-to-video", "image-reference", "audio-reference", "openrouter", "seedance"],
            output=SkillOutputConfig(kind="video"),
        )
