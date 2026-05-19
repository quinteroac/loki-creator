from fastapi import APIRouter, Depends

from app.models import InstructionRequest, InstructionResponse
from app.services import InstructionService

router = APIRouter(prefix="/api")


def get_instruction_service() -> InstructionService:
    return InstructionService()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/instructions", response_model=InstructionResponse)
def create_instruction(
    payload: InstructionRequest,
    service: InstructionService = Depends(get_instruction_service),
) -> InstructionResponse:
    return service.create(payload)
