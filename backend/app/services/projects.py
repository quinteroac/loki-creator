import json
import re
from datetime import UTC, datetime
from pathlib import Path

from app.models import ProjectDocument, ProjectSaveRequest, ProjectSummary


PROJECT_FILENAME = "project.json"


class ProjectNotFoundError(RuntimeError):
    pass


class ProjectService:
    def __init__(self, projects_root: Path) -> None:
        self.projects_root = projects_root

    def list_projects(self) -> list[ProjectSummary]:
        if not self.projects_root.exists():
            return []

        summaries: list[ProjectSummary] = []
        for project_file in self.projects_root.glob(f"*/{PROJECT_FILENAME}"):
            try:
                project = self._read_project(project_file)
            except Exception:
                continue

            summaries.append(
                ProjectSummary(
                    id=project.id,
                    name=project.name,
                    createdAt=project.created_at,
                    updatedAt=project.updated_at,
                    cardCount=len(project.card_documents),
                )
            )

        return sorted(summaries, key=lambda project: project.updated_at, reverse=True)

    def get_project(self, project_id: str) -> ProjectDocument:
        project_file = self._project_file(project_id)
        if not project_file.is_file():
            raise ProjectNotFoundError(f"Project not found: {project_id}")

        return self._read_project(project_file)

    def save_project(self, project_id: str, payload: ProjectSaveRequest) -> ProjectDocument:
        sanitized_id = self.sanitize_project_id(project_id or payload.name)
        project_file = self._project_file(sanitized_id)
        now = datetime.now(UTC)
        created_at = now

        if project_file.is_file():
            try:
                created_at = self._read_project(project_file).created_at
            except Exception:
                created_at = now

        project = ProjectDocument(
            id=sanitized_id,
            name=payload.name.strip() or "Untitled project",
            createdAt=created_at,
            updatedAt=now,
            cardDocuments=payload.card_documents,
            canvasNodes=payload.canvas_nodes,
        )

        project_file.parent.mkdir(parents=True, exist_ok=True)
        project_file.write_text(
            json.dumps(project.model_dump(mode="json", by_alias=True), indent=2),
            encoding="utf-8",
        )
        return project

    def _project_file(self, project_id: str) -> Path:
        return self.projects_root / self.sanitize_project_id(project_id) / PROJECT_FILENAME

    def _read_project(self, project_file: Path) -> ProjectDocument:
        return ProjectDocument.model_validate_json(project_file.read_text(encoding="utf-8"))

    def sanitize_project_id(self, value: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-")
        return slug[:80] or "project"
