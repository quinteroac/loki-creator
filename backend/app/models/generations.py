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
