from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field


class InstructionRequest(BaseModel):
    instruction: Annotated[str, Field(min_length=1, max_length=4000)]
    tool: Annotated[str, Field(min_length=1, max_length=80)]
    tools: list[Annotated[str, Field(min_length=1, max_length=80)]] = Field(default_factory=list)
    selected_cards: list[str] = Field(default_factory=list, alias="selectedCards")
    selected_element: str | None = Field(default=None, alias="selectedElement")


class InstructionResponse(BaseModel):
    id: str
    accepted: bool
    created_at: datetime
