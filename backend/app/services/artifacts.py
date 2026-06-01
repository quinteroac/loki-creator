from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.models.artifacts import ArchivedArtifact, ImportedArtifact


class ArtifactArchiveService:
    def __init__(self, artifacts_root: Path) -> None:
        self.artifacts_root = artifacts_root.resolve()
        self.deleted_root = self.artifacts_root / "deleted"

    def archive_artifact_urls(self, artifact_urls: list[str]) -> list[ArchivedArtifact]:
        archived: list[ArchivedArtifact] = []
        seen: set[str] = set()

        for artifact_url in artifact_urls:
            if artifact_url in seen:
                continue
            seen.add(artifact_url)
            archived.append(self.archive_artifact_url(artifact_url))

        return archived

    def archive_artifact_url(self, artifact_url: str) -> ArchivedArtifact:
        artifact = self._resolve_artifact_url(artifact_url)
        if artifact is None:
            return ArchivedArtifact(artifactUrl=artifact_url, status="ignored")

        if not artifact.is_file():
            return ArchivedArtifact(artifactUrl=artifact_url, status="missing")

        relative_path = artifact.relative_to(self.artifacts_root)
        destination = self._unique_destination(self.deleted_root / relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(artifact), destination)

        return ArchivedArtifact(
            artifactUrl=artifact_url,
            deletedPath=destination.relative_to(self.artifacts_root).as_posix(),
            status="archived",
        )

    def import_upload(self, upload: UploadFile) -> ImportedArtifact:
        filename = self._safe_filename(upload.filename or "attachment")
        destination = self._unique_destination(self.artifacts_root / "imports" / f"{uuid4().hex}-{filename}")
        destination.parent.mkdir(parents=True, exist_ok=True)

        with destination.open("wb") as output:
            shutil.copyfileobj(upload.file, output)

        return ImportedArtifact(
            artifactUrl=f"/api/artifacts/{destination.relative_to(self.artifacts_root).as_posix()}",
            name=upload.filename or filename,
            mimeType=upload.content_type or "application/octet-stream",
            size=destination.stat().st_size,
        )

    def _resolve_artifact_url(self, artifact_url: str) -> Path | None:
        if not artifact_url.startswith("/api/artifacts/"):
            return None

        artifact = (self.artifacts_root / artifact_url.removeprefix("/api/artifacts/")).resolve()
        try:
            artifact.relative_to(self.artifacts_root)
        except ValueError:
            return None

        try:
            artifact.relative_to(self.deleted_root)
            return None
        except ValueError:
            return artifact

    def _unique_destination(self, destination: Path) -> Path:
        if not destination.exists():
            return destination

        return destination.with_name(f"{destination.stem}-{uuid4().hex[:8]}{destination.suffix}")

    def _safe_filename(self, filename: str) -> str:
        safe = "".join(character if character.isalnum() or character in {".", "-", "_"} else "-" for character in filename)
        safe = safe.strip(".-_")
        return safe[:120] or "attachment"
