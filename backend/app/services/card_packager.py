from __future__ import annotations

import html
import base64
import mimetypes
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from PIL import Image

from app.models import CardMetadata, GeneratedCard, SkillArtifact, SkillDefinition, SkillDiagnostic, SkillRawResult, SkillResult


REPO_ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS_ROOT = Path(os.environ.get("LOKI_ARTIFACTS_ROOT", REPO_ROOT / ".loki")).resolve()


class CardPackagerError(RuntimeError):
    pass


class CardPackagerService:
    def package(
        self,
        *,
        skill: SkillDefinition,
        run_id: str,
        prompt: str,
        params: dict[str, Any],
        raw_result: SkillRawResult,
    ) -> SkillResult:
        cards = list(raw_result.cards)

        for artifact in [*raw_result.artifacts, *raw_result.media]:
            cards.append(self._package_artifact(skill, run_id, prompt, params, artifact))

        if raw_result.html:
            cards.append(self._package_html(skill, run_id, prompt, raw_result.html, raw_result.metadata))

        if raw_result.text:
            cards.append(self._package_text(skill, run_id, prompt, raw_result.text, raw_result.metadata))

        for diagnostic in raw_result.diagnostics:
            cards.append(self._package_diagnostic(skill, run_id, prompt, diagnostic))

        return SkillResult(cards=cards)

    def _package_artifact(
        self,
        skill: SkillDefinition,
        run_id: str,
        prompt: str,
        params: dict[str, Any],
        artifact_value: SkillArtifact | str,
    ) -> GeneratedCard:
        artifact = self._coerce_artifact(artifact_value)

        if artifact.html:
            return self._package_html(skill, run_id, artifact.prompt or prompt, artifact.html, artifact.metadata, title=artifact.title)
        if artifact.text:
            return self._package_text(skill, run_id, artifact.prompt or prompt, artifact.text, artifact.metadata, title=artifact.title)

        source_path = self._materialize_data_url(skill, run_id, artifact) if artifact.data_url else self._resolve_artifact_path(artifact)
        stored_path = self._ensure_artifact_under_loki(skill, run_id, source_path)
        artifact_url = f"/api/artifacts/{stored_path.relative_to(ARTIFACTS_ROOT).as_posix()}"
        mime_type = artifact.mime_type or mimetypes.guess_type(stored_path.name)[0] or "application/octet-stream"
        kind = self._kind_for_artifact(artifact, mime_type, stored_path)
        title = self._first_text(artifact.title, params.get("title"), skill.name)
        card_prompt = self._first_text(artifact.prompt, params.get("skillPrompt"), params.get("prompt"), prompt)
        width, height = self._artifact_dimensions(kind, stored_path, artifact.metadata)
        preferred_aspect_ratio = self._preferred_aspect_ratio(artifact.metadata, params, width, height)
        html_content = self._html_for_artifact(kind, artifact_url, title, mime_type)

        metadata = {
            **artifact.metadata,
            "kind": self._card_metadata_kind(kind),
            "title": title,
            "description": card_prompt,
            "artifactUrl": artifact_url,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "tags": [skill.id, *list(artifact.metadata.get("tags", []))],
            "capabilities": skill.capabilities,
        }
        if width and height:
            metadata["width"] = width
            metadata["height"] = height
        if kind == "image":
            metadata["thumbnailUrl"] = artifact_url
        if preferred_aspect_ratio:
            metadata["preferredAspectRatio"] = preferred_aspect_ratio
        if kind in {"video", "audio", "html"}:
            metadata["playableMedia"] = True

        return GeneratedCard(
            id=f"card_{uuid4().hex}",
            name=title,
            prompt=card_prompt,
            html=html_content,
            sourceSkillId=skill.id,
            sourceActionId="auto-packager",
            metadata=CardMetadata.model_validate(metadata),
        )

    def _coerce_artifact(self, artifact: SkillArtifact | str) -> SkillArtifact:
        if isinstance(artifact, SkillArtifact):
            return artifact
        return SkillArtifact(path=str(artifact))

    def _resolve_artifact_path(self, artifact: SkillArtifact) -> Path:
        path_value = artifact.path or artifact.url
        if not path_value:
            raise CardPackagerError("Artifact result is missing path or url")
        if path_value.startswith(("http://", "https://", "data:")):
            raise CardPackagerError("Remote and data URL artifacts must be materialized by the skill action")

        path = Path(path_value).expanduser()
        if not path.is_absolute():
            path = (REPO_ROOT / path).resolve()
        return path.resolve()

    def _materialize_data_url(self, skill: SkillDefinition, run_id: str, artifact: SkillArtifact) -> Path:
        data_url = artifact.data_url or ""
        header, separator, encoded = data_url.partition(",")
        if separator != "," or not header.startswith("data:") or ";base64" not in header:
            raise CardPackagerError("Artifact dataUrl must be a base64 data URL")

        mime_type = header[5:].split(";", 1)[0] or artifact.mime_type or "application/octet-stream"
        extension = mimetypes.guess_extension(mime_type) or ".bin"
        destination_dir = ARTIFACTS_ROOT / "skills" / skill.id / run_id / "artifacts"
        destination_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid4().hex}{extension}"
        destination = destination_dir / filename
        destination.write_bytes(base64.b64decode(encoded))
        artifact.mime_type = artifact.mime_type or mime_type
        return destination

    def _ensure_artifact_under_loki(self, skill: SkillDefinition, run_id: str, source_path: Path) -> Path:
        if not source_path.is_file():
            raise CardPackagerError(f"Artifact file does not exist: {source_path}")

        try:
            source_path.relative_to(ARTIFACTS_ROOT)
            return source_path
        except ValueError:
            pass

        destination_dir = ARTIFACTS_ROOT / "skills" / skill.id / run_id / "artifacts"
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / source_path.name
        if destination.exists():
            destination = destination.with_name(f"{destination.stem}-{uuid4().hex[:8]}{destination.suffix}")
        shutil.copy2(source_path, destination)
        return destination

    def _kind_for_artifact(self, artifact: SkillArtifact, mime_type: str, path: Path) -> str:
        if artifact.kind and artifact.kind != "artifact":
            return "diagnostic" if artifact.kind == "json" else artifact.kind
        if mime_type.startswith("image/"):
            return "image"
        if mime_type.startswith("video/"):
            return "video"
        if mime_type.startswith("audio/"):
            return "audio"
        if mime_type in {"text/html", "application/xhtml+xml"} or path.suffix.lower() in {".html", ".htm"}:
            return "html"
        if mime_type.startswith("text/") or path.suffix.lower() in {".json", ".md", ".txt", ".log"}:
            return "diagnostic"
        return "artifact"

    def _card_metadata_kind(self, kind: str) -> str:
        if kind in {"image", "video", "audio", "diagnostic", "artifact", "interactive"}:
            return kind
        if kind == "text":
            return "diagnostic"
        if kind == "html":
            return "interactive"
        return "artifact"

    def _artifact_dimensions(self, kind: str, path: Path, metadata: dict[str, Any]) -> tuple[int | None, int | None]:
        metadata_width = self._positive_int(metadata.get("width"))
        metadata_height = self._positive_int(metadata.get("height"))
        if metadata_width and metadata_height:
            return metadata_width, metadata_height

        if kind != "image":
            return None, None

        try:
            with Image.open(path) as image:
                return image.size
        except Exception:
            return None, None

    def _positive_int(self, value: Any) -> int | None:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None

        return parsed if parsed > 0 else None

    def _preferred_aspect_ratio(
        self,
        metadata: dict[str, Any],
        params: dict[str, Any],
        width: int | None = None,
        height: int | None = None,
    ) -> str | None:
        value = self._first_text(
            metadata.get("preferredAspectRatio"),
            metadata.get("aspectRatio"),
            params.get("aspectRatio"),
        )
        if value in {"1:1", "4:3", "16:9", "9:16"}:
            return value
        if width and height:
            return "auto"
        return value if value == "auto" else None

    def _html_for_artifact(self, kind: str, artifact_url: str, title: str, mime_type: str) -> str:
        escaped_url = html.escape(artifact_url, quote=True)
        escaped_title = html.escape(title)
        if kind == "image":
            body = f'<img src="{escaped_url}" alt="{escaped_title}" />'
        elif kind == "video":
            body = f'<video src="{escaped_url}" controls playsinline preload="metadata"></video>'
        elif kind == "audio":
            body = f'<main class="audio"><strong>{escaped_title}</strong><audio src="{escaped_url}" controls preload="metadata"></audio></main>'
        elif kind == "html":
            body = f'<iframe src="{escaped_url}" title="{escaped_title}"></iframe>'
        else:
            body = f'<main class="file"><strong>{escaped_title}</strong><span>{html.escape(mime_type)}</span><a href="{escaped_url}">Open artifact</a></main>'

        return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <style>
      html, body {{ width: 100%; height: 100%; margin: 0; background: #111111; color: #f7f4ef; font-family: "DM Sans", Inter, sans-serif; }}
      body {{ display: grid; place-items: center; overflow: hidden; }}
      img, video, iframe {{ display: block; width: 100%; height: 100%; border: 0; object-fit: contain; background: #111111; }}
      main {{ box-sizing: border-box; width: 100%; height: 100%; display: grid; place-items: center; gap: 16px; padding: 24px; text-align: center; }}
      audio {{ width: min(360px, 90%); }}
      a {{ color: #7aa7ff; }}
    </style>
  </head>
  <body>{body}</body>
</html>"""

    def _package_html(
        self,
        skill: SkillDefinition,
        run_id: str,
        prompt: str,
        html_content: str,
        metadata: dict[str, Any],
        *,
        title: str | None = None,
    ) -> GeneratedCard:
        card_title = self._first_text(title, metadata.get("title"), skill.name)
        return GeneratedCard(
            id=f"card_{uuid4().hex}",
            name=card_title,
            prompt=prompt,
            html=html_content,
            sourceSkillId=skill.id,
            sourceActionId="auto-packager",
            metadata=CardMetadata.model_validate(
                {
                    **metadata,
                    "kind": metadata.get("kind") or "interactive",
                    "title": card_title,
                    "description": prompt,
                    "createdAt": datetime.now(timezone.utc).isoformat(),
                    "tags": [skill.id, *list(metadata.get("tags", []))],
                    "capabilities": skill.capabilities,
                }
            ),
        )

    def _package_text(
        self,
        skill: SkillDefinition,
        run_id: str,
        prompt: str,
        text: str,
        metadata: dict[str, Any],
        *,
        title: str | None = None,
    ) -> GeneratedCard:
        escaped_text = html.escape(text)
        card_title = self._first_text(title, metadata.get("title"), skill.name)
        content = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <style>
      html, body {{ width: 100%; height: 100%; margin: 0; background: #202020; color: #f7f4ef; font-family: "DM Sans", Inter, sans-serif; }}
      body {{ box-sizing: border-box; padding: 24px; overflow: auto; }}
      pre {{ margin: 0; white-space: pre-wrap; word-break: break-word; font: 14px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace; }}
    </style>
  </head>
  <body><pre>{escaped_text}</pre></body>
</html>"""
        return GeneratedCard(
            id=f"card_{uuid4().hex}",
            name=card_title,
            prompt=prompt,
            html=content,
            sourceSkillId=skill.id,
            sourceActionId="auto-packager",
            metadata=CardMetadata.model_validate(
                {
                    **metadata,
                    "kind": metadata.get("kind") or "diagnostic",
                    "title": card_title,
                    "description": prompt,
                    "createdAt": datetime.now(timezone.utc).isoformat(),
                    "tags": [skill.id, *list(metadata.get("tags", []))],
                    "capabilities": skill.capabilities,
                }
            ),
        )

    def _package_diagnostic(
        self,
        skill: SkillDefinition,
        run_id: str,
        prompt: str,
        diagnostic_value: SkillDiagnostic | str,
    ) -> GeneratedCard:
        if isinstance(diagnostic_value, SkillDiagnostic):
            diagnostic = diagnostic_value
        else:
            diagnostic = SkillDiagnostic(message=str(diagnostic_value))

        title = self._first_text(diagnostic.title, f"{skill.name} diagnostic")
        return self._package_text(
            skill,
            run_id,
            prompt,
            diagnostic.message,
            {"kind": "diagnostic", "level": diagnostic.level, **diagnostic.metadata},
            title=title,
        )

    def _first_text(self, *values: object) -> str:
        for value in values:
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""
