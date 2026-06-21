from __future__ import annotations

import io
import json
import re
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote
from uuid import uuid4
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from app.models import ProjectCreateRequest, ProjectDocument, ProjectSaveRequest, ProjectStatus, ProjectSummary


PROJECT_FILENAME = "project.json"
PROJECT_SCHEMA_VERSION = 2
PROJECT_EXPORT_FORMAT = "loki-project"
PROJECT_EXPORT_SCHEMA_VERSION = 1
PROJECT_STATUS_FILTERS = {"active", "archived", "trashed", "all"}
ARTIFACT_URL_PREFIX = "/api/artifacts/"
ARTIFACT_URL_PATTERN = re.compile(r"/api/artifacts/[^\s\"'<>)]*")


class ProjectError(RuntimeError):
    pass


class ProjectNotFoundError(ProjectError):
    pass


class ProjectStorageError(ProjectError):
    pass


class ProjectInvalidOperationError(ProjectError):
    pass


class ProjectArtifactMissingError(ProjectError):
    def __init__(self, missing_artifact_urls: list[str]) -> None:
        self.missing_artifact_urls = missing_artifact_urls
        super().__init__(
            "Missing project artifacts: "
            + ", ".join(missing_artifact_urls[:6])
            + ("..." if len(missing_artifact_urls) > 6 else "")
        )


class ProjectImportError(ProjectError):
    pass


@dataclass(frozen=True)
class ProjectExport:
    data: bytes
    filename: str


class ProjectService:
    def __init__(self, projects_root: Path, artifacts_root: Path) -> None:
        self.projects_root = projects_root
        self.artifacts_root = artifacts_root

    def list_projects(self, status: str = "active") -> list[ProjectSummary]:
        if status not in PROJECT_STATUS_FILTERS:
            raise ProjectInvalidOperationError(f"Unsupported project status filter: {status}")
        if not self.projects_root.exists():
            return []

        summaries: list[ProjectSummary] = []
        for project_dir in sorted(self.projects_root.iterdir()):
            if not project_dir.is_dir():
                continue

            project_file = project_dir / PROJECT_FILENAME
            if not project_file.exists():
                continue

            project = self._read_project(project_file)
            if status != "all" and project.status != status:
                continue

            summaries.append(self._project_summary(project))

        return sorted(summaries, key=lambda project: project.updated_at, reverse=True)

    def get_project(self, project_id: str) -> ProjectDocument:
        return self._read_existing_project(project_id)

    def create_project(self, payload: ProjectCreateRequest) -> ProjectDocument:
        now = datetime.now(UTC)
        project_id = self._unique_project_id(payload.name)
        project = ProjectDocument(
            schemaVersion=PROJECT_SCHEMA_VERSION,
            id=project_id,
            name=payload.name.strip() or "Untitled project",
            createdAt=now,
            updatedAt=now,
            status="active",
            cardDocuments=payload.card_documents,
            canvasNodes=payload.canvas_nodes,
            agentMemory=payload.agent_memory or {},
        )

        self._write_project(project)
        return project

    def save_project(self, project_id: str, payload: ProjectSaveRequest) -> ProjectDocument:
        existing = self._read_existing_project(project_id)
        if existing.status == "trashed":
            raise ProjectInvalidOperationError("Trashed projects must be restored before saving.")

        project = ProjectDocument(
            schemaVersion=PROJECT_SCHEMA_VERSION,
            id=existing.id,
            name=payload.name.strip() or "Untitled project",
            createdAt=existing.created_at,
            updatedAt=datetime.now(UTC),
            status=existing.status,
            archivedAt=existing.archived_at,
            trashedAt=existing.trashed_at,
            importedAt=existing.imported_at,
            cardDocuments=payload.card_documents,
            canvasNodes=payload.canvas_nodes,
            agentMemory=payload.agent_memory if payload.agent_memory is not None else existing.agent_memory,
        )

        self._write_project(project)
        return project

    def archive_project(self, project_id: str) -> ProjectDocument:
        project = self._read_existing_project(project_id)
        if project.status == "trashed":
            raise ProjectInvalidOperationError("Trashed projects must be restored before archiving.")

        now = datetime.now(UTC)
        return self._with_status(project, "archived", now, archived_at=project.archived_at or now, trashed_at=None)

    def trash_project(self, project_id: str) -> ProjectDocument:
        project = self._read_existing_project(project_id)
        now = datetime.now(UTC)
        return self._with_status(project, "trashed", now, archived_at=project.archived_at, trashed_at=project.trashed_at or now)

    def restore_project(self, project_id: str) -> ProjectDocument:
        project = self._read_existing_project(project_id)
        return self._with_status(project, "active", datetime.now(UTC), archived_at=None, trashed_at=None)

    def delete_project(self, project_id: str) -> None:
        project = self._read_existing_project(project_id)
        if project.status != "trashed":
            raise ProjectInvalidOperationError("Only trashed projects can be permanently deleted.")

        shutil.rmtree(self._project_file(project.id).parent)

    def duplicate_project(self, project_id: str) -> ProjectDocument:
        project = self._read_existing_project(project_id)
        now = datetime.now(UTC)
        duplicate = ProjectDocument(
            schemaVersion=PROJECT_SCHEMA_VERSION,
            id=self._unique_project_id(f"{project.name} Copy"),
            name=f"{project.name} Copy",
            createdAt=now,
            updatedAt=now,
            status="active",
            cardDocuments=project.card_documents,
            canvasNodes=project.canvas_nodes,
            agentMemory=project.agent_memory,
        )

        self._write_project(duplicate)
        return duplicate

    def export_project(self, project_id: str) -> ProjectExport:
        project = self._read_existing_project(project_id)
        artifact_urls = self._collect_project_artifact_urls(project)
        artifact_entries = self._export_artifact_entries(artifact_urls)
        project_payload = project.model_dump(mode="json", by_alias=True)
        manifest = {
            "format": PROJECT_EXPORT_FORMAT,
            "schemaVersion": PROJECT_EXPORT_SCHEMA_VERSION,
            "exportedAt": datetime.now(UTC).isoformat(),
            "projectId": project.id,
            "projectName": project.name,
            "artifacts": [
                {
                    "sourceUrl": source_url,
                    "archivePath": archive_path,
                }
                for source_url, archive_path, _ in artifact_entries
            ],
        }

        buffer = io.BytesIO()
        with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, indent=2))
            archive.writestr("project/project.json", json.dumps(project_payload, indent=2))
            for _, archive_path, artifact_path in artifact_entries:
                archive.write(artifact_path, archive_path)

        filename = f"{self._download_filename(project.name)}.loki-project.zip"
        return ProjectExport(data=buffer.getvalue(), filename=filename)

    def import_project(self, archive_bytes: bytes) -> ProjectDocument:
        try:
            with ZipFile(io.BytesIO(archive_bytes)) as archive:
                self._validate_zip_members(archive)
                manifest = self._read_json_member(archive, "manifest.json")
                project_payload = self._read_json_member(archive, "project/project.json")
                if manifest.get("format") != PROJECT_EXPORT_FORMAT:
                    raise ProjectImportError("Unsupported project archive format.")

                source_url_rewrites = self._import_artifacts(archive, manifest)
        except BadZipFile as exc:
            raise ProjectImportError("Project import must be a valid .loki-project.zip file.") from exc

        rewritten_payload = self._rewrite_strings(project_payload, source_url_rewrites)
        now = datetime.now(UTC)
        project_name = str(rewritten_payload.get("name") or "Imported project")
        project_id = self._unique_project_id(project_name)
        rewritten_payload.update(
            {
                "schemaVersion": PROJECT_SCHEMA_VERSION,
                "id": project_id,
                "name": project_name.strip() or "Imported project",
                "createdAt": now.isoformat(),
                "updatedAt": now.isoformat(),
                "status": "active",
                "archivedAt": None,
                "trashedAt": None,
                "importedAt": now.isoformat(),
            }
        )

        project = ProjectDocument.model_validate(rewritten_payload)
        self._write_project(project)
        return project

    def get_agent_memory(self, project_id: str, agent_id: str) -> dict[str, Any]:
        project = self._read_existing_project(project_id)
        value = project.agent_memory.get(agent_id)
        return value if isinstance(value, dict) else {}

    def save_agent_memory(self, project_id: str, agent_id: str, memory: dict[str, Any]) -> dict[str, Any]:
        project = self._read_existing_project(project_id)
        if project.status == "trashed":
            raise ProjectInvalidOperationError("Trashed projects must be restored before saving agent memory.")

        updated_memory = {**project.agent_memory, agent_id: memory}
        updated = ProjectDocument(
            schemaVersion=PROJECT_SCHEMA_VERSION,
            id=project.id,
            name=project.name,
            createdAt=project.created_at,
            updatedAt=datetime.now(UTC),
            status=project.status,
            archivedAt=project.archived_at,
            trashedAt=project.trashed_at,
            importedAt=project.imported_at,
            cardDocuments=project.card_documents,
            canvasNodes=project.canvas_nodes,
            agentMemory=updated_memory,
        )
        self._write_project(updated)
        return memory

    def artifact_count(self, project: ProjectDocument) -> int:
        return len(self._collect_project_artifact_urls(project))

    def _with_status(
        self,
        project: ProjectDocument,
        status: ProjectStatus,
        updated_at: datetime,
        *,
        archived_at: datetime | None,
        trashed_at: datetime | None,
    ) -> ProjectDocument:
        updated = ProjectDocument(
            schemaVersion=PROJECT_SCHEMA_VERSION,
            id=project.id,
            name=project.name,
            createdAt=project.created_at,
            updatedAt=updated_at,
            status=status,
            archivedAt=archived_at,
            trashedAt=trashed_at,
            importedAt=project.imported_at,
            cardDocuments=project.card_documents,
            canvasNodes=project.canvas_nodes,
            agentMemory=project.agent_memory,
        )
        self._write_project(updated)
        return updated

    def _project_summary(self, project: ProjectDocument) -> ProjectSummary:
        return ProjectSummary(
            id=project.id,
            name=project.name,
            createdAt=project.created_at,
            updatedAt=project.updated_at,
            status=project.status,
            archivedAt=project.archived_at,
            trashedAt=project.trashed_at,
            importedAt=project.imported_at,
            cardCount=len(project.card_documents),
            artifactCount=self.artifact_count(project),
        )

    def _project_file(self, project_id: str) -> Path:
        return self.projects_root / self.sanitize_project_id(project_id) / PROJECT_FILENAME

    def _read_existing_project(self, project_id: str) -> ProjectDocument:
        project_file = self._project_file(project_id)
        if not project_file.is_file():
            raise ProjectNotFoundError(f"Project not found: {project_id}")

        return self._read_project(project_file)

    def _read_project(self, project_file: Path) -> ProjectDocument:
        try:
            payload = json.loads(project_file.read_text(encoding="utf-8"))
            payload.setdefault("schemaVersion", PROJECT_SCHEMA_VERSION)
            payload.setdefault("status", "active")
            payload.setdefault("archivedAt", None)
            payload.setdefault("trashedAt", None)
            payload.setdefault("importedAt", None)
            payload.setdefault("agentMemory", {})
            return ProjectDocument.model_validate(payload)
        except Exception as exc:
            raise ProjectStorageError(f"Could not read project file: {project_file}") from exc

    def _write_project(self, project: ProjectDocument) -> None:
        project_file = self._project_file(project.id)
        project_file.parent.mkdir(parents=True, exist_ok=True)
        temporary_file = project_file.with_name(f".{PROJECT_FILENAME}.{uuid4().hex}.tmp")
        try:
            temporary_file.write_text(
                json.dumps(project.model_dump(mode="json", by_alias=True), indent=2),
                encoding="utf-8",
            )
            temporary_file.replace(project_file)
        finally:
            if temporary_file.exists():
                temporary_file.unlink()

    def _unique_project_id(self, name: str) -> str:
        base = self.sanitize_project_id(name)
        candidate = base
        counter = 2
        while self._project_file(candidate).exists():
            suffix = f"-{counter}"
            candidate = f"{base[:80 - len(suffix)]}{suffix}"
            counter += 1

        return candidate

    def sanitize_project_id(self, value: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-")
        return slug[:80] or "project"

    def _download_filename(self, name: str) -> str:
        filename = re.sub(r"[^a-zA-Z0-9._-]+", "-", name.strip()).strip(".-")
        return filename[:80] or "project"

    def _collect_project_artifact_urls(self, project: ProjectDocument) -> list[str]:
        urls: list[str] = []
        payload = project.model_dump(mode="json", by_alias=True)

        def collect(value: Any) -> None:
            if isinstance(value, str):
                for match in ARTIFACT_URL_PATTERN.findall(value):
                    artifact_url = match.rstrip(".,;")
                    if artifact_url not in urls:
                        urls.append(artifact_url)
                return

            if isinstance(value, dict):
                for child in value.values():
                    collect(child)
                return

            if isinstance(value, list):
                for child in value:
                    collect(child)

        collect(payload)
        return urls

    def _export_artifact_entries(self, artifact_urls: list[str]) -> list[tuple[str, str, Path]]:
        entries: list[tuple[str, str, Path]] = []
        missing_artifact_urls: list[str] = []

        for artifact_url in artifact_urls:
            artifact_path = self._artifact_path_from_url(artifact_url)
            if not artifact_path.is_file():
                missing_artifact_urls.append(artifact_url)
                continue

            relative_artifact_path = artifact_path.relative_to(self.artifacts_root).as_posix()
            entries.append((artifact_url, f"artifacts/{relative_artifact_path}", artifact_path))

        if missing_artifact_urls:
            raise ProjectArtifactMissingError(missing_artifact_urls)

        return entries

    def _artifact_path_from_url(self, artifact_url: str) -> Path:
        if not artifact_url.startswith(ARTIFACT_URL_PREFIX):
            raise ProjectInvalidOperationError("Project artifacts must use local artifact URLs.")

        relative_url = artifact_url.removeprefix(ARTIFACT_URL_PREFIX).split("?", 1)[0].split("#", 1)[0]
        relative_path = Path(unquote(relative_url))
        artifact_path = (self.artifacts_root / relative_path).resolve()
        try:
            artifact_path.relative_to(self.artifacts_root.resolve())
        except ValueError as exc:
            raise ProjectInvalidOperationError("Project artifact URL is outside the artifacts directory.") from exc

        return artifact_path

    def _validate_zip_members(self, archive: ZipFile) -> None:
        names = archive.namelist()
        if "manifest.json" not in names or "project/project.json" not in names:
            raise ProjectImportError("Project archive is missing manifest.json or project/project.json.")

        for name in names:
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts:
                raise ProjectImportError("Project archive contains an unsafe path.")

    def _read_json_member(self, archive: ZipFile, name: str) -> dict[str, Any]:
        try:
            with archive.open(name) as member:
                payload = json.loads(member.read().decode("utf-8"))
        except KeyError as exc:
            raise ProjectImportError(f"Project archive is missing {name}.") from exc
        except json.JSONDecodeError as exc:
            raise ProjectImportError(f"Project archive contains invalid JSON in {name}.") from exc

        if not isinstance(payload, dict):
            raise ProjectImportError(f"Project archive member {name} must be a JSON object.")

        return payload

    def _import_artifacts(self, archive: ZipFile, manifest: dict[str, Any]) -> dict[str, str]:
        artifacts = manifest.get("artifacts", [])
        if not isinstance(artifacts, list):
            raise ProjectImportError("Project archive manifest artifacts must be a list.")

        placeholder_project_id = f"import-{uuid4().hex}"
        rewrites: dict[str, str] = {}
        staged_files: list[tuple[str, bytes]] = []

        for artifact in artifacts:
            if not isinstance(artifact, dict):
                raise ProjectImportError("Project archive manifest artifacts must be objects.")

            source_url = artifact.get("sourceUrl")
            archive_path = artifact.get("archivePath")
            if not isinstance(source_url, str) or not isinstance(archive_path, str):
                raise ProjectImportError("Project archive artifact entries require sourceUrl and archivePath.")
            if not archive_path.startswith("artifacts/"):
                raise ProjectImportError("Project archive artifact paths must live under artifacts/.")

            try:
                data = archive.read(archive_path)
            except KeyError as exc:
                raise ProjectImportError(f"Project archive is missing artifact {archive_path}.") from exc

            relative_artifact_path = archive_path.removeprefix("artifacts/").lstrip("/")
            staged_files.append((relative_artifact_path, data))
            rewrites[source_url] = f"{ARTIFACT_URL_PREFIX}project-imports/{placeholder_project_id}/{relative_artifact_path}"

        project_id = self._unique_project_id(str(manifest.get("projectName") or "Imported project"))
        import_root = self.artifacts_root / "project-imports" / project_id
        rewritten_urls = {
            source_url: imported_url.replace(placeholder_project_id, project_id)
            for source_url, imported_url in rewrites.items()
        }

        for relative_artifact_path, data in staged_files:
            destination = (import_root / relative_artifact_path).resolve()
            try:
                destination.relative_to(import_root.resolve())
            except ValueError as exc:
                raise ProjectImportError("Project archive contains an unsafe artifact path.") from exc

            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)

        return rewritten_urls

    def _rewrite_strings(self, value: Any, rewrites: dict[str, str]) -> Any:
        if isinstance(value, str):
            rewritten = value
            for source, destination in rewrites.items():
                rewritten = rewritten.replace(source, destination)
            return rewritten

        if isinstance(value, dict):
            return {key: self._rewrite_strings(child, rewrites) for key, child in value.items()}

        if isinstance(value, list):
            return [self._rewrite_strings(child, rewrites) for child in value]

        return value
