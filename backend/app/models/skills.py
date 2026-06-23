from datetime import datetime
from typing import Any, Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.instructions import GeneratedCard


SkillOrigin = Literal["built-in", "user"]
SkillVisibility = Literal["user", "internal"]
SkillRunStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]
SkillArgumentType = Literal["choice", "text"]
SkillArgumentAskWhen = Literal["always", "missing"]
SkillOutputKind = Literal["auto", "image", "video", "audio", "html", "text", "diagnostic", "artifact"]
SkillArtifactKind = Literal["image", "video", "audio", "html", "text", "json", "artifact", "diagnostic"]


class SkillCardAction(BaseModel):
    type: Literal["cli-local"] = "cli-local"
    command: list[str] = Field(default_factory=list)
    timeout_seconds: int = Field(default=0, alias="timeoutSeconds")

    model_config = ConfigDict(populate_by_name=True)


class SkillOutputConfig(BaseModel):
    packager: Literal["auto"] = "auto"
    kind: SkillOutputKind = "auto"

    model_config = ConfigDict(populate_by_name=True)


class SkillRuntimeConfig(BaseModel):
    models_dir: str | None = Field(default=None, alias="modelsDir")

    model_config = ConfigDict(populate_by_name=True)


class SkillArgumentOption(BaseModel):
    value: str
    label: str | None = None
    description: str | None = None


class SkillArgumentDefinition(BaseModel):
    id: str
    label: str
    description: str = ""
    type: SkillArgumentType = "text"
    required: bool = False
    ask_when: SkillArgumentAskWhen = Field(default="missing", alias="askWhen")
    depends_on: dict[str, str] = Field(default_factory=dict, alias="dependsOn")
    options: list[SkillArgumentOption] = Field(default_factory=list)
    order: int = 0

    model_config = ConfigDict(populate_by_name=True)


class SkillDefinition(BaseModel):
    id: str
    name: str
    description: str
    path: str
    origin: SkillOrigin = "built-in"
    visibility: SkillVisibility = "internal"
    capabilities: list[str] = Field(default_factory=list)
    action: SkillCardAction | None = None
    output: SkillOutputConfig = Field(default_factory=SkillOutputConfig)
    runtime: SkillRuntimeConfig = Field(default_factory=SkillRuntimeConfig)
    arguments: list[SkillArgumentDefinition] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class SkillRunRequest(BaseModel):
    skill_id: str = Field(alias="skillId")
    prompt: Annotated[str, Field(min_length=1, max_length=4000)]
    context: dict[str, Any] = Field(default_factory=dict)
    selected_cards: list[str] = Field(default_factory=list, alias="selectedCards")
    selected_card_snapshots: list[dict[str, Any]] = Field(default_factory=list, alias="selectedCardSnapshots")
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class SkillResult(BaseModel):
    cards: list[GeneratedCard] = Field(default_factory=list)


class SkillArtifact(BaseModel):
    path: str | None = None
    url: str | None = None
    data_url: str | None = Field(default=None, alias="dataUrl")
    kind: SkillArtifactKind | None = None
    mime_type: str | None = Field(default=None, alias="mimeType")
    title: str | None = None
    prompt: str | None = None
    html: str | None = None
    text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class SkillDiagnostic(BaseModel):
    level: Literal["info", "warning", "error"] = "info"
    title: str | None = None
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class SkillRawResult(BaseModel):
    cards: list[GeneratedCard] = Field(default_factory=list)
    artifacts: list[SkillArtifact | str] = Field(default_factory=list)
    media: list[SkillArtifact | str] = Field(default_factory=list)
    html: str | None = None
    text: str | None = None
    diagnostics: list[SkillDiagnostic | str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class SkillPackagedRunRequest(SkillRunRequest):
    raw_result: SkillRawResult = Field(alias="rawResult")

    model_config = ConfigDict(populate_by_name=True)


class SkillRun(BaseModel):
    id: str
    skill_id: str = Field(alias="skillId")
    status: SkillRunStatus
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    result: SkillResult | None = None
    error: str | None = None

    model_config = ConfigDict(populate_by_name=True)
