from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.instructions import GeneratedCard


class SeedanceVideoGenerationRequest(BaseModel):
    prompt: str
    aspect_ratio: Literal["16:9", "9:16"] = Field(alias="aspectRatio")
    duration: Literal[4, 5, 7, 10, 15]
    selected_card_snapshots: list[dict[str, Any]] = Field(default_factory=list, alias="selectedCardSnapshots")
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class SeedanceVideoGenerationResponse(BaseModel):
    cards: list[GeneratedCard] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class GrokImageGenerationRequest(BaseModel):
    prompt: str
    aspect_ratio: Literal["1:1", "4:3", "16:9", "9:16"] = Field(alias="aspectRatio")
    resolution: Literal["1k", "2k"] = "1k"
    selected_card_snapshots: list[dict[str, Any]] = Field(default_factory=list, alias="selectedCardSnapshots")
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class GrokVideoGenerationRequest(BaseModel):
    prompt: str
    aspect_ratio: Literal["16:9", "9:16", "1:1", "4:3"] = Field(alias="aspectRatio")
    resolution: Literal["720p", "480p"] = "720p"
    duration: Literal[5, 10, 15]
    selected_card_snapshots: list[dict[str, Any]] = Field(default_factory=list, alias="selectedCardSnapshots")
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class GrokGenerationResponse(BaseModel):
    cards: list[GeneratedCard] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)
