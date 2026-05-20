from datetime import UTC, datetime
from html import escape

from app.models import GeneratedCard


class HtmlCardFactory:
    def create(
        self,
        *,
        prompt: str,
        source_tool_id: str | None = None,
        name: str = "Canvas card",
        output_text: str | None = None,
    ) -> GeneratedCard:
        now = datetime.now(UTC)
        card_id = f"card_{int(now.timestamp() * 1000)}"
        escaped_output = escape(output_text or prompt)
        html = f"""<section style="display:grid;width:100%;height:100%;place-items:center;background:#111111;color:#ffffff;font-family:DM Sans,Inter,Arial,sans-serif;">
  <div style="width:68%;min-height:52%;display:grid;place-items:center;border-radius:28px;background:linear-gradient(135deg,#245cff,#e9429f);text-align:center;padding:24px;">
    <div>
      <strong style="display:block;font-size:20px;line-height:1.4;">Canvas Output</strong>
      <span style="display:block;margin-top:8px;color:rgba(255,255,255,.82);font-size:18px;line-height:1.5;">{escaped_output}</span>
    </div>
  </div>
</section>"""

        return GeneratedCard(
            id=card_id,
            name=name,
            prompt=prompt,
            html=html,
            source_tool_id=source_tool_id,
        )
