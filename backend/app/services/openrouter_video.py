from __future__ import annotations

import base64
import json
import mimetypes
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from uuid import uuid4

from app.models import SkillArtifact, SkillDefinition, SkillRawResult
from app.models.skills import SkillOutputConfig
from app.services.card_packager import CardPackagerService


OPENROUTER_BASE_URL = "https://openrouter.ai"


class OpenRouterVideoRequest(Protocol):
    prompt: str
    aspect_ratio: str
    duration: int
    selected_card_snapshots: list[dict[str, Any]]
    attachments: list[dict[str, Any]]
    context: dict[str, Any]


class OpenRouterVideoGenerationError(RuntimeError):
    pass


@dataclass(frozen=True)
class OpenRouterVideoConfig:
    model: str
    skill_id: str
    name: str
    description: str
    output_folder: str
    output_filename: str
    resolution: str
    capabilities: tuple[str, ...]


def first_text(*values: object) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


class OpenRouterVideoGenerationService:
    config: OpenRouterVideoConfig
    error_type: type[OpenRouterVideoGenerationError] = OpenRouterVideoGenerationError
    response_type: type[Any]

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

    def generate(self, payload: OpenRouterVideoRequest) -> Any:
        prompt = payload.prompt.strip()
        if not prompt:
            self.fail(f"{self.config.name} video generation requires a prompt.")

        run_id = f"generation_{uuid4().hex}"
        request_body = self.build_request_body(payload, prompt)
        started = self.request_json("POST", "/api/v1/videos", request_body)
        job_id = first_text(started.get("id"))
        polling_url = first_text(started.get("polling_url"))
        if not job_id and not polling_url:
            self.fail("OpenRouter video response did not include a job id or polling URL.")

        completed = self.poll_video(job_id, polling_url)
        video_url = self.video_url(completed, job_id)
        output_path, mime_type = self.download_video(video_url, self.output_dir(run_id) / self.config.output_filename)
        metadata = {
            "provider": "openrouter",
            "model": self.config.model,
            "jobId": first_text(completed.get("id"), job_id),
            "generationId": first_text(completed.get("generation_id"), started.get("generation_id")),
            "status": first_text(completed.get("status")),
            "duration": payload.duration,
            "resolution": self.config.resolution,
            "aspectRatio": payload.aspect_ratio,
            "usage": completed.get("usage") if isinstance(completed.get("usage"), dict) else None,
            **self.artifact_metadata(request_body),
        }
        raw_result = SkillRawResult(
            artifacts=[
                SkillArtifact(
                    path=str(output_path),
                    kind="video",
                    mimeType=mime_type,
                    title=f"{self.config.name} video",
                    prompt=prompt,
                    metadata=metadata,
                )
            ]
        )
        result = self.packager.package(
            skill=self.skill_definition(),
            run_id=run_id,
            prompt=prompt,
            params=self.packager_params(payload),
            raw_result=raw_result,
        )
        return self.response_type(cards=result.cards)

    def build_request_body(self, payload: OpenRouterVideoRequest, prompt: str) -> dict[str, Any]:
        raise NotImplementedError

    def artifact_metadata(self, request_body: dict[str, Any]) -> dict[str, Any]:
        return {}

    def packager_params(self, payload: OpenRouterVideoRequest) -> dict[str, Any]:
        return {
            "aspectRatio": payload.aspect_ratio,
            "duration": payload.duration,
            "resolution": self.config.resolution,
        }

    def reference_urls(self, payload: OpenRouterVideoRequest, media_kind: str, *, limit: int) -> list[str]:
        sources: list[str] = []
        context = payload.context if isinstance(payload.context, dict) else {}
        local_references = context.get("localMediaReferences")
        if isinstance(local_references, list):
            for reference in local_references:
                if isinstance(reference, dict) and first_text(reference.get("kind")) == media_kind:
                    sources.append(first_text(reference.get("path"), reference.get("artifactUrl")))

        if not any(sources):
            for snapshot in payload.selected_card_snapshots:
                source = self.reference_source_from_snapshot(snapshot, media_kind)
                if source:
                    sources.append(source)

            for attachment in payload.attachments:
                if not isinstance(attachment, dict) or attachment.get("omitted"):
                    continue
                if first_text(attachment.get("kind")) == media_kind:
                    sources.append(first_text(attachment.get("artifactUrl"), attachment.get("src")))

        urls: list[str] = []
        seen: set[str] = set()
        for source in sources:
            if not source or source in seen:
                continue
            seen.add(source)
            urls.append(self.normalize_reference_url(source, media_kind))
            if len(urls) == limit:
                break
        return urls

    def first_reference(self, payload: OpenRouterVideoRequest, media_kind: str) -> dict[str, Any] | None:
        urls = self.reference_urls(payload, media_kind, limit=1)
        return self.reference_object(urls[0], media_kind) if urls else None

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
            return first_text(metadata.get("artifactUrl"))
        return ""

    def reference_object(self, url: str, media_kind: str) -> dict[str, Any]:
        if media_kind == "image":
            return {"type": "image_url", "image_url": {"url": url}}
        if media_kind == "audio":
            return {"type": "audio_url", "audio_url": {"url": url}}
        self.fail(f"Unsupported OpenRouter video reference kind: {media_kind}")

    def normalize_reference_url(self, source: str, media_kind: str) -> str:
        if source.startswith("data:"):
            self.fail("OpenRouter video references must be local Loki artifacts; inline dataUrl is not an executable media input.")
        artifact_path = self.resolve_artifact_src(source)
        if artifact_path is not None:
            return self.path_to_data_url(artifact_path, media_kind)
        path = Path(source).expanduser().resolve()
        try:
            path.relative_to(self.artifacts_root)
        except ValueError as exc:
            raise self.error_type(f"OpenRouter video reference must be a local Loki artifact, got: {source[:80]}") from exc
        if not path.is_file():
            self.fail(f"OpenRouter video reference path does not exist: {path}")
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
            self.fail(f"Selected artifact is not an image: {path.name}")
        if media_kind == "audio" and not mime_type.startswith("audio/"):
            self.fail(f"Selected artifact is not an audio file: {path.name}")
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
            raise self.error_type(f"OpenRouter API returned HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise self.error_type(f"OpenRouter API request failed: {exc.reason}") from exc

    def api_key(self) -> str:
        key = first_text(os.environ.get("OPENROUTER_API_KEY"))
        if not key:
            self.fail("OpenRouter auth not found. Set OPENROUTER_API_KEY.")
        return key

    def poll_video(self, job_id: str, polling_url: str) -> dict[str, Any]:
        deadline = time.time() + self.poll_timeout_seconds
        poll_path = polling_url or f"/api/v1/videos/{job_id}"
        while time.time() <= deadline:
            result = self.request_json("GET", self.absolute_or_api_path(poll_path))
            status = first_text(result.get("status"))
            if status == "completed":
                return result
            if status in {"failed", "cancelled", "expired"}:
                error = first_text(result.get("error"))
                self.fail(error or f"OpenRouter {self.config.name} video generation {status}.")
            time.sleep(max(self.poll_interval_seconds, 0.25))
        self.fail(f"Timed out waiting for OpenRouter {self.config.name} video after {int(self.poll_timeout_seconds)}s.")

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
        self.fail("OpenRouter video response did not include a downloadable video URL.")

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
            raise self.error_type(f"OpenRouter video download returned HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise self.error_type(f"OpenRouter video download failed: {exc.reason}") from exc

    def output_dir(self, run_id: str) -> Path:
        path = self.artifacts_root / "generations" / self.config.output_folder / run_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def skill_definition(self) -> SkillDefinition:
        return SkillDefinition(
            id=self.config.skill_id,
            name=f"{self.config.name} video",
            description=self.config.description,
            path="backend/" + self.__class__.__module__.replace(".", "/") + ".py",
            visibility="user",
            capabilities=list(self.config.capabilities),
            output=SkillOutputConfig(kind="video"),
        )

    def fail(self, message: str) -> None:
        raise self.error_type(message)
