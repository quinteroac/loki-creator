from datetime import UTC, datetime

from app.models import InstructionRequest, InstructionResponse


class InstructionService:
    def create(self, payload: InstructionRequest) -> InstructionResponse:
        now = datetime.now(UTC)
        instruction_id = f"instruction_{int(now.timestamp() * 1000)}"

        return InstructionResponse(
            id=instruction_id,
            accepted=True,
            created_at=now,
        )
