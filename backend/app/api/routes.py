import os
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse

from app.models import (
    InstructionRequest,
    InstructionResponse,
    ProjectDocument,
    ProjectSaveRequest,
    ProjectSummary,
    SkillDefinition,
    SkillRun,
    SkillRunRequest,
)
from app.services import InstructionService, ProjectNotFoundError, ProjectService, SkillRegistry, SkillRunService

router = APIRouter(prefix="/api")
skill_registry = SkillRegistry()
skill_run_service = SkillRunService(registry=skill_registry)
repo_root = Path(__file__).resolve().parents[3]
artifacts_root = Path(os.environ.get("LOKI_ARTIFACTS_ROOT", repo_root / ".loki")).resolve()
projects_root = artifacts_root / "projects"


def get_instruction_service() -> InstructionService:
    return InstructionService()


def get_skill_registry() -> SkillRegistry:
    return skill_registry


def get_skill_run_service() -> SkillRunService:
    return skill_run_service


def get_project_service() -> ProjectService:
    return ProjectService(projects_root)


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/instructions", response_model=InstructionResponse)
def create_instruction(
    payload: InstructionRequest,
    service: InstructionService = Depends(get_instruction_service),
) -> InstructionResponse:
    return service.create(payload)


@router.get("/skills", response_model=list[SkillDefinition])
def list_skills(
    registry: SkillRegistry = Depends(get_skill_registry),
) -> list[SkillDefinition]:
    return registry.list_skills()


@router.get("/projects", response_model=list[ProjectSummary])
def list_projects(
    service: ProjectService = Depends(get_project_service),
) -> list[ProjectSummary]:
    return service.list_projects()


@router.get("/projects/{project_id}", response_model=ProjectDocument)
def get_project(
    project_id: str,
    service: ProjectService = Depends(get_project_service),
) -> ProjectDocument:
    try:
        return service.get_project(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.put("/projects/{project_id}", response_model=ProjectDocument)
def save_project(
    project_id: str,
    payload: ProjectSaveRequest,
    service: ProjectService = Depends(get_project_service),
) -> ProjectDocument:
    return service.save_project(project_id, payload)


@router.post("/skill-runs", response_model=SkillRun)
def create_skill_run(
    payload: SkillRunRequest,
    background_tasks: BackgroundTasks,
    service: SkillRunService = Depends(get_skill_run_service),
) -> SkillRun:
    run = service.create_run(payload)
    background_tasks.add_task(service.run_skill, run.id, payload)
    return run


@router.get("/skill-runs", response_model=list[SkillRun])
def list_skill_runs(
    status: str | None = None,
    service: SkillRunService = Depends(get_skill_run_service),
) -> list[SkillRun]:
    return service.list_runs(status=status)


@router.get("/skill-runs/{run_id}", response_model=SkillRun)
def get_skill_run(
    run_id: str,
    service: SkillRunService = Depends(get_skill_run_service),
) -> SkillRun:
    run = service.get_run(run_id)

    if run is None:
        raise HTTPException(status_code=404, detail="Skill run not found")

    return run


@router.get("/artifacts/{artifact_path:path}")
def get_artifact(artifact_path: str) -> FileResponse:
    artifact = (artifacts_root / artifact_path).resolve()

    try:
        artifact.relative_to(artifacts_root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Artifact not found") from exc

    if not artifact.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found")

    return FileResponse(artifact)
