from datetime import UTC, datetime

from app.models import GeneratedCard, InstructionRequest, InstructionResponse
from app.services.card_factory import HtmlCardFactory


class InstructionService:
    def __init__(self, card_factory: HtmlCardFactory | None = None) -> None:
        self._card_factory = card_factory or HtmlCardFactory()

    def create(self, payload: InstructionRequest) -> InstructionResponse:
        now = datetime.now(UTC)
        instruction_id = f"instruction_{int(now.timestamp() * 1000)}"
        generated_card = self._card_factory.create(
            prompt=payload.instruction,
            source_skill_id=payload.skill,
        )

        return InstructionResponse(
            id=instruction_id,
            accepted=True,
            created_at=now,
            generated_card=generated_card,
        )
