from datetime import UTC, datetime
from typing import Annotated

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


app = FastAPI(title="Loki Creator API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/instructions", response_model=InstructionResponse)
def create_instruction(payload: InstructionRequest) -> InstructionResponse:
    now = datetime.now(UTC)
    instruction_id = f"instruction_{int(now.timestamp() * 1000)}"

    return InstructionResponse(
        id=instruction_id,
        accepted=True,
        created_at=now,
    )
