from datetime import UTC, datetime
from html import escape

from app.models import CardMetadata, GeneratedCard


class HtmlCardFactory:
    def create(
        self,
        *,
        prompt: str,
        source_skill_id: str | None = None,
        source_action_id: str | None = None,
        name: str = "Canvas card",
        output_text: str | None = None,
        metadata: CardMetadata | dict | None = None,
    ) -> GeneratedCard:
        now = datetime.now(UTC)
        card_id = f"card_{int(now.timestamp() * 1000)}"
        escaped_output = escape(output_text or prompt)
        card_metadata = CardMetadata.model_validate(metadata or {})
        card_metadata = card_metadata.model_copy(
            update={
                "kind": card_metadata.kind or "generic",
                "title": card_metadata.title or name,
                "description": card_metadata.description or prompt,
                "preferred_aspect_ratio": card_metadata.preferred_aspect_ratio or "1:1",
                "playable_media": card_metadata.playable_media if card_metadata.playable_media is not None else False,
            }
        )
        html = f"""<section style="display:grid;width:100%;height:100%;place-items:center;background:#111111;color:#ffffff;font-family:DM Sans,Inter,Arial,sans-serif;">
  <div style="width:68%;min-height:52%;display:grid;place-items:center;border-radius:28px;background:linear-gradient(135deg,#245cff,#e9429f);text-align:center;padding:24px;">
    <strong style="display:block;color:rgba(255,255,255,.92);font-size:24px;line-height:1.35;">{escaped_output}</strong>
  </div>
</section>"""

        return GeneratedCard(
            id=card_id,
            name=name,
            prompt=prompt,
            html=html,
            source_skill_id=source_skill_id,
            source_action_id=source_action_id,
            metadata=card_metadata,
        )
