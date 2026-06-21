import os
from io import BytesIO
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from app.models import (
    AudioTimelineRequest,
    AudioTimelineResponse,
    AudioTrimRequest,
    ArchiveArtifactsRequest,
    ArchiveArtifactsResponse,
    CodexImageGenerationRequest,
    CodexImageGenerationResponse,
    ComfyGenerationRequest,
    ComfyGenerationResponse,
    GeminiImageGenerationRequest,
    GeminiImageGenerationResponse,
    GrokGenerationResponse,
    GrokImageGenerationRequest,
    GrokVideoGenerationRequest,
    ImportedArtifact,
    InstructionRequest,
    InstructionResponse,
    ProjectCreateRequest,
    ProjectDocument,
    ProjectAgentMemoryRequest,
    ProjectSaveRequest,
    ProjectSummary,
    SeedanceVideoGenerationRequest,
    SeedanceVideoGenerationResponse,
    SkillDefinition,
    SkillPackagedRunRequest,
    SkillRun,
    SkillRunRequest,
    VideoEditArtifact,
    VideoEffectOption,
    VideoFrameRequest,
    VideoLutOption,
    VideoTimelineRequest,
    VideoTimelineResponse,
    VideoTrimRequest,
)
from app.services import (
    AudioEditorError,
    AudioEditorService,
    ArtifactArchiveService,
    CodexImageGenerationError,
    CodexImageGenerationService,
    ComfyGenerationError,
    ComfyGenerationService,
    GeminiImageGenerationError,
    GeminiImageGenerationService,
    GrokImagineGenerationError,
    GrokImagineGenerationService,
    InstructionService,
    ProjectArtifactMissingError,
    ProjectImportError,
    ProjectInvalidOperationError,
    ProjectNotFoundError,
    ProjectService,
    ProjectStorageError,
    SeedanceVideoGenerationError,
    SeedanceVideoGenerationService,
    SkillRegistry,
    SkillRunService,
    VideoEditorError,
    VideoEditorService,
)

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
    return ProjectService(projects_root, artifacts_root)


def get_artifact_archive_service() -> ArtifactArchiveService:
    return ArtifactArchiveService(artifacts_root)


def get_video_editor_service() -> VideoEditorService:
    return VideoEditorService(artifacts_root)


def get_audio_editor_service() -> AudioEditorService:
    return AudioEditorService(artifacts_root)


def get_seedance_video_generation_service() -> SeedanceVideoGenerationService:
    return SeedanceVideoGenerationService(artifacts_root)


def get_grok_imagine_generation_service() -> GrokImagineGenerationService:
    return GrokImagineGenerationService(artifacts_root)


def get_codex_image_generation_service() -> CodexImageGenerationService:
    return CodexImageGenerationService(artifacts_root)


def get_comfy_generation_service() -> ComfyGenerationService:
    return ComfyGenerationService(artifacts_root)


def get_gemini_image_generation_service() -> GeminiImageGenerationService:
    return GeminiImageGenerationService(artifacts_root)


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


@router.post("/generations/seedance-video", response_model=SeedanceVideoGenerationResponse)
def generate_seedance_video(
    payload: SeedanceVideoGenerationRequest,
    service: SeedanceVideoGenerationService = Depends(get_seedance_video_generation_service),
) -> SeedanceVideoGenerationResponse:
    try:
        return service.generate(payload)
    except SeedanceVideoGenerationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/generations/grok-image", response_model=GrokGenerationResponse)
def generate_grok_image(
    payload: GrokImageGenerationRequest,
    service: GrokImagineGenerationService = Depends(get_grok_imagine_generation_service),
) -> GrokGenerationResponse:
    try:
        return service.generate_image(payload)
    except GrokImagineGenerationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/generations/grok-video", response_model=GrokGenerationResponse)
def generate_grok_video(
    payload: GrokVideoGenerationRequest,
    service: GrokImagineGenerationService = Depends(get_grok_imagine_generation_service),
) -> GrokGenerationResponse:
    try:
        return service.generate_video(payload)
    except GrokImagineGenerationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/generations/codex-image", response_model=CodexImageGenerationResponse)
def generate_codex_image(
    payload: CodexImageGenerationRequest,
    service: CodexImageGenerationService = Depends(get_codex_image_generation_service),
) -> CodexImageGenerationResponse:
    try:
        return service.generate(payload)
    except CodexImageGenerationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/generations/comfy", response_model=ComfyGenerationResponse)
def generate_comfy(
    payload: ComfyGenerationRequest,
    service: ComfyGenerationService = Depends(get_comfy_generation_service),
) -> ComfyGenerationResponse:
    try:
        return service.generate(payload)
    except ComfyGenerationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/generations/gemini-image", response_model=GeminiImageGenerationResponse)
def generate_gemini_image(
    payload: GeminiImageGenerationRequest,
    service: GeminiImageGenerationService = Depends(get_gemini_image_generation_service),
) -> GeminiImageGenerationResponse:
    try:
        return service.generate(payload)
    except GeminiImageGenerationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/projects", response_model=list[ProjectSummary])
def list_projects(
    status: Literal["active", "archived", "trashed", "all"] = "active",
    service: ProjectService = Depends(get_project_service),
) -> list[ProjectSummary]:
    try:
        return service.list_projects(status=status)
    except ProjectStorageError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/projects", response_model=ProjectDocument)
def create_project(
    payload: ProjectCreateRequest,
    service: ProjectService = Depends(get_project_service),
) -> ProjectDocument:
    return service.create_project(payload)


@router.get("/projects/{project_id}", response_model=ProjectDocument)
def get_project(
    project_id: str,
    service: ProjectService = Depends(get_project_service),
) -> ProjectDocument:
    try:
        return service.get_project(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except ProjectStorageError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.put("/projects/{project_id}", response_model=ProjectDocument)
def save_project(
    project_id: str,
    payload: ProjectSaveRequest,
    service: ProjectService = Depends(get_project_service),
) -> ProjectDocument:
    try:
        return service.save_project(project_id, payload)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except ProjectInvalidOperationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ProjectStorageError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/projects/{project_id}/agent-memory/{agent_id}")
def get_project_agent_memory(
    project_id: str,
    agent_id: str,
    service: ProjectService = Depends(get_project_service),
) -> dict[str, object]:
    try:
        return {"memory": service.get_agent_memory(project_id, agent_id)}
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except ProjectStorageError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.put("/projects/{project_id}/agent-memory/{agent_id}")
def save_project_agent_memory(
    project_id: str,
    agent_id: str,
    payload: ProjectAgentMemoryRequest,
    service: ProjectService = Depends(get_project_service),
) -> dict[str, object]:
    try:
        return {"memory": service.save_agent_memory(project_id, agent_id, payload.memory)}
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except ProjectInvalidOperationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ProjectStorageError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/projects/{project_id}/archive", response_model=ProjectDocument)
def archive_project(
    project_id: str,
    service: ProjectService = Depends(get_project_service),
) -> ProjectDocument:
    try:
        return service.archive_project(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except ProjectInvalidOperationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/projects/{project_id}/trash", response_model=ProjectDocument)
def trash_project(
    project_id: str,
    service: ProjectService = Depends(get_project_service),
) -> ProjectDocument:
    try:
        return service.trash_project(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.post("/projects/{project_id}/restore", response_model=ProjectDocument)
def restore_project(
    project_id: str,
    service: ProjectService = Depends(get_project_service),
) -> ProjectDocument:
    try:
        return service.restore_project(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.delete("/projects/{project_id}")
def delete_project(
    project_id: str,
    service: ProjectService = Depends(get_project_service),
) -> dict[str, str]:
    try:
        service.delete_project(project_id)
        return {"status": "deleted"}
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except ProjectInvalidOperationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/projects/{project_id}/duplicate", response_model=ProjectDocument)
def duplicate_project(
    project_id: str,
    service: ProjectService = Depends(get_project_service),
) -> ProjectDocument:
    try:
        return service.duplicate_project(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.get("/projects/{project_id}/export")
def export_project(
    project_id: str,
    service: ProjectService = Depends(get_project_service),
) -> StreamingResponse:
    try:
        project_export = service.export_project(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except ProjectArtifactMissingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ProjectInvalidOperationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return StreamingResponse(
        BytesIO(project_export.data),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{project_export.filename}"'},
    )


@router.post("/projects/import", response_model=ProjectDocument)
def import_project(
    file: UploadFile = File(...),
    service: ProjectService = Depends(get_project_service),
) -> ProjectDocument:
    try:
        return service.import_project(file.file.read())
    except ProjectImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/skill-runs", response_model=SkillRun)
def create_skill_run(
    payload: SkillRunRequest,
    background_tasks: BackgroundTasks,
    service: SkillRunService = Depends(get_skill_run_service),
) -> SkillRun:
    run = service.create_run(payload)
    background_tasks.add_task(service.run_skill, run.id, payload)
    return run


@router.post("/skill-runs/package", response_model=SkillRun)
def create_packaged_skill_run(
    payload: SkillPackagedRunRequest,
    service: SkillRunService = Depends(get_skill_run_service),
) -> SkillRun:
    return service.create_packaged_run(payload)


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


@router.post("/skill-runs/{run_id}/cancel", response_model=SkillRun)
def cancel_skill_run(
    run_id: str,
    service: SkillRunService = Depends(get_skill_run_service),
) -> SkillRun:
    run = service.cancel_run(run_id)

    if run is None:
        raise HTTPException(status_code=404, detail="Skill run not found")

    return run


@router.post("/artifacts/archive", response_model=ArchiveArtifactsResponse)
def archive_artifacts(
    payload: ArchiveArtifactsRequest,
    service: ArtifactArchiveService = Depends(get_artifact_archive_service),
) -> ArchiveArtifactsResponse:
    return ArchiveArtifactsResponse(artifacts=service.archive_artifact_urls(payload.artifact_urls))


@router.post("/artifacts/import", response_model=ImportedArtifact)
def import_artifact(
    file: UploadFile = File(...),
    service: ArtifactArchiveService = Depends(get_artifact_archive_service),
) -> ImportedArtifact:
    return service.import_upload(file)


@router.post("/artifacts/video/timeline", response_model=VideoTimelineResponse)
def create_video_timeline(
    payload: VideoTimelineRequest,
    service: VideoEditorService = Depends(get_video_editor_service),
) -> VideoTimelineResponse:
    try:
        return service.timeline(payload.artifact_url, payload.max_thumbnails, payload.lut_id, payload.effect_id)
    except VideoEditorError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/artifacts/video/luts", response_model=list[VideoLutOption])
def list_video_luts(
    service: VideoEditorService = Depends(get_video_editor_service),
) -> list[VideoLutOption]:
    return service.list_luts()


@router.get("/artifacts/video/effects", response_model=list[VideoEffectOption])
def list_video_effects(
    service: VideoEditorService = Depends(get_video_editor_service),
) -> list[VideoEffectOption]:
    return service.list_effects()


@router.post("/artifacts/video/frame", response_model=VideoEditArtifact)
def export_video_frame(
    payload: VideoFrameRequest,
    service: VideoEditorService = Depends(get_video_editor_service),
) -> VideoEditArtifact:
    try:
        return service.export_frame(payload.artifact_url, payload.time_seconds, payload.lut_id, payload.effect_id)
    except VideoEditorError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/artifacts/video/trim", response_model=VideoEditArtifact)
def trim_video_artifact(
    payload: VideoTrimRequest,
    service: VideoEditorService = Depends(get_video_editor_service),
) -> VideoEditArtifact:
    try:
        return service.trim(payload.artifact_url, payload.start_seconds, payload.end_seconds, payload.lut_id, payload.effect_id)
    except VideoEditorError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/artifacts/audio/timeline", response_model=AudioTimelineResponse)
def create_audio_timeline(
    payload: AudioTimelineRequest,
    service: AudioEditorService = Depends(get_audio_editor_service),
) -> AudioTimelineResponse:
    try:
        return service.timeline(payload.artifact_url, payload.max_peaks)
    except AudioEditorError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/artifacts/audio/trim", response_model=VideoEditArtifact)
def trim_audio_artifact(
    payload: AudioTrimRequest,
    service: AudioEditorService = Depends(get_audio_editor_service),
) -> VideoEditArtifact:
    try:
        return service.trim(payload.artifact_url, payload.start_seconds, payload.end_seconds)
    except AudioEditorError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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
