from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.instructions import GeneratedCard


class ProjectCanvasNodeFrame(BaseModel):
    width: int | float
    x: int | float
    y: int | float


class ProjectCanvasNode(BaseModel):
    id: str
    card_document_id: str = Field(alias="cardDocumentId")
    frame: ProjectCanvasNodeFrame

    model_config = ConfigDict(populate_by_name=True)


class ProjectDocument(BaseModel):
    id: str
    name: str
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    card_documents: list[GeneratedCard] = Field(default_factory=list, alias="cardDocuments")
    canvas_nodes: list[ProjectCanvasNode] = Field(default_factory=list, alias="canvasNodes")

    model_config = ConfigDict(populate_by_name=True)


class ProjectSummary(BaseModel):
    id: str
    name: str
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    card_count: int = Field(alias="cardCount")

    model_config = ConfigDict(populate_by_name=True)


class ProjectSaveRequest(BaseModel):
    name: str
    card_documents: list[GeneratedCard] = Field(default_factory=list, alias="cardDocuments")
    canvas_nodes: list[ProjectCanvasNode] = Field(default_factory=list, alias="canvasNodes")

    model_config = ConfigDict(populate_by_name=True)
