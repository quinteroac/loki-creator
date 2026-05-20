import os
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse

from app.models import (
    InstructionRequest,
    InstructionResponse,
    ToolDefinition,
    ToolInvocationRequest,
    ToolJob,
    ToolPackage,
)
from app.services import InstructionService, ToolJobService, ToolRegistry

router = APIRouter(prefix="/api")
tool_registry = ToolRegistry()
tool_job_service = ToolJobService(registry=tool_registry)
repo_root = Path(__file__).resolve().parents[3]
artifacts_root = Path(os.environ.get("LOKI_ARTIFACTS_ROOT", repo_root / ".loki")).resolve()


def get_instruction_service() -> InstructionService:
    return InstructionService()


def get_tool_registry() -> ToolRegistry:
    return tool_registry


def get_tool_job_service() -> ToolJobService:
    return tool_job_service


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/instructions", response_model=InstructionResponse)
def create_instruction(
    payload: InstructionRequest,
    service: InstructionService = Depends(get_instruction_service),
) -> InstructionResponse:
    return service.create(payload)


@router.get("/tools", response_model=list[ToolDefinition])
def list_tools(
    include_internal: bool = False,
    registry: ToolRegistry = Depends(get_tool_registry),
) -> list[ToolDefinition]:
    tools = registry.list_tools()

    if include_internal:
        return tools

    return [tool for tool in tools if tool.invocation_visibility == "frontend"]


@router.get("/tools/{tool_id}/export", response_model=ToolPackage)
def export_tool(
    tool_id: str,
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ToolPackage:
    tool = registry.get_tool(tool_id)

    if tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")
    if not tool.exportable:
        raise HTTPException(status_code=400, detail="Built-in tools are not exportable")

    return ToolPackage(
        manifest_version="1",
        tool=tool,
        assets=[],
        secrets_required=tool.permissions.env_vars,
        integrity={},
    )


@router.post("/tools/import", status_code=501)
def import_tool(package: ToolPackage) -> dict[str, str]:
    return {
        "status": "not_implemented",
        "message": "Tool import is reserved for a future version.",
    }


@router.post("/tool-jobs", response_model=ToolJob)
def create_tool_job(
    payload: ToolInvocationRequest,
    background_tasks: BackgroundTasks,
    service: ToolJobService = Depends(get_tool_job_service),
) -> ToolJob:
    job = service.create_job(payload)
    background_tasks.add_task(service.run_job, job.id, payload)
    return job


@router.get("/tool-jobs", response_model=list[ToolJob])
def list_tool_jobs(
    status: str | None = None,
    service: ToolJobService = Depends(get_tool_job_service),
) -> list[ToolJob]:
    """List tool jobs so clients can reconcile async agent/tool results."""
    return service.list_jobs(status=status)


@router.get("/tool-jobs/{job_id}", response_model=ToolJob)
def get_tool_job(
    job_id: str,
    service: ToolJobService = Depends(get_tool_job_service),
) -> ToolJob:
    job = service.get_job(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail="Tool job not found")

    return job


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
