import html
import json
import sys
from uuid import uuid4


def build_card_html(prompt: str) -> str:
    escaped_prompt = html.escape(prompt or "Animated HTML study")

    return f"""<section class="loki-html-animation-card" style="position:absolute;inset:0;width:100%;height:100%;max-width:100%;max-height:100%;overflow:hidden;contain:layout paint size;isolation:isolate;background:#000000;color:#ffffff;font-family:DM Sans,Inter,Helvetica Neue,Arial,sans-serif;">
  <style>
    @keyframes loki-html-animation-orbit {{
      0% {{ transform: rotate(0deg) translateX(86px) rotate(0deg); }}
      100% {{ transform: rotate(360deg) translateX(86px) rotate(-360deg); }}
    }}

    @keyframes loki-html-animation-drift {{
      0%, 100% {{ transform: translate3d(-10px, 8px, 0) scale(1); opacity: .56; }}
      50% {{ transform: translate3d(18px, -12px, 0) scale(1.08); opacity: .9; }}
    }}

    @keyframes loki-html-animation-pulse {{
      0%, 100% {{ transform: scale(.92); opacity: .64; }}
      50% {{ transform: scale(1.08); opacity: 1; }}
    }}

    .loki-html-animation-card .halo {{
      position:absolute;
      inset:18%;
      border:1px solid #242424;
      border-radius:9999px;
      animation:loki-html-animation-pulse 3.8s ease-in-out infinite;
    }}

    .loki-html-animation-card .orb {{
      position:absolute;
      top:50%;
      left:50%;
      width:28px;
      height:28px;
      margin:-14px;
      border-radius:9999px;
      background:#ff5a3d;
      box-shadow:0 0 24px #ff5a3d;
      animation:loki-html-animation-orbit 4.2s linear infinite;
    }}

    .loki-html-animation-card .orb:nth-of-type(3) {{
      width:20px;
      height:20px;
      background:#245cff;
      box-shadow:0 0 26px #245cff;
      animation-duration:5.6s;
      animation-direction:reverse;
    }}

    .loki-html-animation-card .orb:nth-of-type(4) {{
      width:16px;
      height:16px;
      background:#e9429f;
      box-shadow:0 0 24px #e9429f;
      animation-duration:6.8s;
    }}

    .loki-html-animation-card .field {{
      position:absolute;
      inset:0;
      background:
        radial-gradient(circle at 24% 24%, #69d8ff 0 0.5px, transparent 1.5px),
        radial-gradient(circle at 72% 64%, #7a4dff 0 0.5px, transparent 1.5px);
      background-size:26px 26px,34px 34px;
      opacity:.34;
      animation:loki-html-animation-drift 6s ease-in-out infinite;
    }}
  </style>

  <div class="field" aria-hidden="true"></div>
  <div class="halo" aria-hidden="true"></div>
  <div class="orb" aria-hidden="true"></div>
  <div class="orb" aria-hidden="true"></div>
  <div class="orb" aria-hidden="true"></div>

  <div style="position:absolute;inset:auto 24px 24px;display:grid;gap:8px;">
    <strong style="font-size:24px;font-weight:700;line-height:1.25;letter-spacing:0;">HTML Animation</strong>
    <span style="max-width:34ch;color:#b5bac3;font-size:13px;line-height:1.7;">{escaped_prompt}</span>
  </div>
</section>"""


def main() -> None:
    payload = json.load(sys.stdin)
    prompt = str(payload.get("prompt", "")).strip()

    result = {
        "cards": [
            {
                "id": f"card_{uuid4().hex}",
                "name": "HTML Animation",
                "prompt": prompt,
                "html": build_card_html(prompt),
                "sourceToolId": "html-animation",
                "metadata": {
                    "kind": "interactive",
                    "title": "HTML Animation",
                    "description": prompt,
                    "preferredAspectRatio": "1:1",
                    "tags": ["html", "animation"],
                },
            }
        ]
    }

    print(json.dumps(result))


if __name__ == "__main__":
    main()
