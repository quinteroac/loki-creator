from datetime import datetime
from typing import Any, Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.instructions import GeneratedCard


SkillOrigin = Literal["built-in", "user"]
SkillRunStatus = Literal["queued", "running", "succeeded", "failed"]
SkillArgumentType = Literal["choice", "text"]
SkillArgumentAskWhen = Literal["always", "missing"]


class SkillCardAction(BaseModel):
    type: Literal["cli-local"] = "cli-local"
    command: list[str] = Field(default_factory=list)
    timeout_seconds: int = Field(default=30, alias="timeoutSeconds")

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
    options: list[SkillArgumentOption] = Field(default_factory=list)
    order: int = 0

    model_config = ConfigDict(populate_by_name=True)


class SkillDefinition(BaseModel):
    id: str
    name: str
    description: str
    path: str
    origin: SkillOrigin = "built-in"
    capabilities: list[str] = Field(default_factory=list)
    card_action: SkillCardAction | None = Field(default=None, alias="cardAction")
    arguments: list[SkillArgumentDefinition] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class SkillRunRequest(BaseModel):
    skill_id: str = Field(alias="skillId")
    prompt: Annotated[str, Field(min_length=1, max_length=4000)]
    context: dict[str, Any] = Field(default_factory=dict)
    selected_cards: list[str] = Field(default_factory=list, alias="selectedCards")
    selected_card_snapshots: list[dict[str, Any]] = Field(default_factory=list, alias="selectedCardSnapshots")
    params: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class SkillResult(BaseModel):
    cards: list[GeneratedCard] = Field(default_factory=list)


class SkillRun(BaseModel):
    id: str
    skill_id: str = Field(alias="skillId")
    status: SkillRunStatus
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    result: SkillResult | None = None
    error: str | None = None

    model_config = ConfigDict(populate_by_name=True)
