import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

type ToolInvocationRequest = {
  prompt: string;
  params?: Record<string, unknown>;
};

const input = await new Response(Bun.stdin.stream()).text();
const payload = JSON.parse(input) as ToolInvocationRequest;
const prompt = payload.prompt;
const text = resolveText(payload);
const cardId = `card_${Date.now()}`;

function resolveText(payload: ToolInvocationRequest) {
  const params = payload.params ?? {};
  for (const key of ["text", "message", "title", "content", "outputText"]) {
    const value = params[key];
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }

  return payload.prompt;
}

function ReactNoteCard({ text }: { text: string }) {
  return (
    <section
      style={{
        display: "grid",
        width: "100%",
        height: "100%",
        placeItems: "center",
        background: "#111111",
        color: "#ffffff",
        fontFamily: "DM Sans, Inter, Arial, sans-serif",
        overflow: "hidden",
      }}
    >
      <article
        style={{
          display: "grid",
          width: "100%",
          height: "100%",
          placeItems: "center",
          padding: 32,
          background: "#202020",
        }}
      >
        <div style={{ display: "grid", gap: 12, maxWidth: "82%", textAlign: "left" }}>
          <span style={{ color: "rgba(255,255,255,.58)", fontSize: 13 }}>User React Tool</span>
          <strong style={{ fontSize: 28, lineHeight: 1.2 }}>{text}</strong>
        </div>
      </article>
    </section>
  );
}

const html = renderToStaticMarkup(<ReactNoteCard text={text} />);

process.stdout.write(
  JSON.stringify({
    cards: [
      {
        id: cardId,
        name: "React Note Card",
        prompt,
        html,
        sourceToolId: "react-note-card",
      },
    ],
  }),
);
