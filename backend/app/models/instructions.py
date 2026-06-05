from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class InstructionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    instruction: Annotated[str, Field(min_length=1, max_length=4000)]
    skill: Annotated[str, Field(min_length=1, max_length=80)]
    skills: list[Annotated[str, Field(min_length=1, max_length=80)]] = Field(default_factory=list)
    selected_cards: list[str] = Field(default_factory=list, alias="selectedCards")
    selected_element: str | None = Field(default=None, alias="selectedElement")


CardKind = Literal["generic", "image", "video", "audio", "diagnostic", "artifact", "interactive", "note"]
CardAspectRatio = Literal["1:1", "4:3", "16:9", "9:16", "auto"]


class CardMetadata(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    kind: CardKind | None = None
    title: str | None = None
    description: str | None = None
    thumbnail_url: str | None = Field(default=None, alias="thumbnailUrl")
    artifact_url: str | None = Field(default=None, alias="artifactUrl")
    created_at: str | None = Field(default=None, alias="createdAt")
    width: int | None = None
    height: int | None = None
    tags: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    preferred_aspect_ratio: CardAspectRatio | None = Field(default=None, alias="preferredAspectRatio")
    playable_media: bool | None = Field(default=None, alias="playableMedia")


class GeneratedCard(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    prompt: str
    html: str
    source_skill_id: str | None = Field(default=None, alias="sourceSkillId")
    source_action_id: str | None = Field(default=None, alias="sourceActionId")
    metadata: CardMetadata | None = None


class InstructionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    accepted: bool
    created_at: datetime
    generated_card: GeneratedCard | None = Field(default=None, alias="generatedCard")
