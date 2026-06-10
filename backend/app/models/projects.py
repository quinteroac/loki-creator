from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.instructions import GeneratedCard

ProjectStatus = Literal["active", "archived", "trashed"]


class ProjectCanvasNodeFrame(BaseModel):
    height: int | float | None = None
    width: int | float
    x: int | float
    y: int | float


class ProjectCanvasNode(BaseModel):
    id: str
    card_document_id: str = Field(alias="cardDocumentId")
    frame: ProjectCanvasNodeFrame

    model_config = ConfigDict(populate_by_name=True)


class ProjectDocument(BaseModel):
    schema_version: int = Field(default=2, alias="schemaVersion")
    id: str
    name: str
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    status: ProjectStatus = "active"
    archived_at: datetime | None = Field(default=None, alias="archivedAt")
    trashed_at: datetime | None = Field(default=None, alias="trashedAt")
    imported_at: datetime | None = Field(default=None, alias="importedAt")
    card_documents: list[GeneratedCard] = Field(default_factory=list, alias="cardDocuments")
    canvas_nodes: list[ProjectCanvasNode] = Field(default_factory=list, alias="canvasNodes")

    model_config = ConfigDict(populate_by_name=True)


class ProjectSummary(BaseModel):
    id: str
    name: str
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    status: ProjectStatus = "active"
    archived_at: datetime | None = Field(default=None, alias="archivedAt")
    trashed_at: datetime | None = Field(default=None, alias="trashedAt")
    imported_at: datetime | None = Field(default=None, alias="importedAt")
    card_count: int = Field(alias="cardCount")
    artifact_count: int = Field(alias="artifactCount")

    model_config = ConfigDict(populate_by_name=True)


class ProjectSaveRequest(BaseModel):
    name: str
    card_documents: list[GeneratedCard] = Field(default_factory=list, alias="cardDocuments")
    canvas_nodes: list[ProjectCanvasNode] = Field(default_factory=list, alias="canvasNodes")

    model_config = ConfigDict(populate_by_name=True)


class ProjectCreateRequest(ProjectSaveRequest):
    pass
