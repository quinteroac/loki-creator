from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class InstructionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    instruction: Annotated[str, Field(min_length=1, max_length=4000)]
    tool: Annotated[str, Field(min_length=1, max_length=80)]
    tools: list[Annotated[str, Field(min_length=1, max_length=80)]] = Field(default_factory=list)
    selected_cards: list[str] = Field(default_factory=list, alias="selectedCards")
    selected_element: str | None = Field(default=None, alias="selectedElement")


class GeneratedCard(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    prompt: str
    html: str
    source_tool_id: str | None = Field(default=None, alias="sourceToolId")


class InstructionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    accepted: bool
    created_at: datetime
    generated_card: GeneratedCard | None = Field(default=None, alias="generatedCard")
