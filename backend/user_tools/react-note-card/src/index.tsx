import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

type ToolInvocationRequest = {
  prompt: string;
  params?: Record<string, unknown>;
  context?: {
    selectedCardSnapshots?: SelectedCardSnapshot[];
  };
};

type SelectedCardSnapshot = {
  id: string;
  name: string;
  displayTitle: string;
  prompt: string;
  html: string;
  preview?: {
    source: "rendered-preview";
    mimeType?: string;
    dataUrl?: string;
    width?: number;
    height?: number;
    omitted?: boolean;
    reason?: string;
  };
  mediaAssets?: Array<{
    kind: "image" | "video" | "audio" | "iframe" | "source" | "canvas";
    src?: string;
    dataUrl?: string;
    mimeType?: string;
    alt?: string;
    width?: number;
    height?: number;
    omitted?: boolean;
    reason?: string;
  }>;
  sourceToolId?: string | null;
  metadata?: Record<string, unknown> | null;
};

const input = await new Response(Bun.stdin.stream()).text();
const payload = JSON.parse(input) as ToolInvocationRequest;
const prompt = payload.prompt;
const authoredHtml = resolveAuthoredHtml(payload);
const text = resolveText(payload);
const useColorfulLetters = shouldUseColorfulLetters(payload);
const cardId = `card_${Date.now()}`;

function resolveAuthoredHtml(payload: ToolInvocationRequest) {
  const params = payload.params ?? {};
  for (const key of ["html", "cardHtml", "outputHtml"]) {
    const value = params[key];
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }

  return "";
}

function resolveText(payload: ToolInvocationRequest) {
  const params = payload.params ?? {};
  for (const key of ["outputText", "text", "message", "title", "content", "body"]) {
    const value = params[key];
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }

  const selectedText = extractSelectedCardText(payload.context?.selectedCardSnapshots?.[0]);
  if (selectedText) {
    return selectedText;
  }

  return payload.prompt;
}

function extractSelectedCardText(card?: SelectedCardSnapshot) {
  if (!card?.html.trim()) return "";

  const htmlText = card.html
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, "\"")
    .replace(/&#39;/g, "'")
    .replace(/\s+/g, " ")
    .trim();

  if (htmlText) return htmlText;

  const visualAsset = card.mediaAssets?.find((asset) => asset.kind === "image" && !asset.omitted);
  if (visualAsset?.alt?.trim()) return visualAsset.alt.trim();
  if (card.preview && !card.preview.omitted) return card.displayTitle;

  return "";
}

function shouldUseColorfulLetters(payload: ToolInvocationRequest) {
  const params = payload.params ?? {};
  const values = [
    payload.prompt,
    params.toolPrompt,
    params.outputText,
    params.title,
    params.subtitle,
    params.body,
    params.style,
  ];
  const instructionText = values.filter((value): value is string => typeof value === "string").join(" ").toLowerCase();

  return /\bcolor/.test(instructionText) || instructionText.includes("colores") || instructionText.includes("multicolor");
}

function ColorfulText({ text }: { text: string }) {
  const colors = ["#ff5a3d", "#e9429f", "#245cff", "#69d8ff", "#ffffff"];

  return (
    <>
      {Array.from(text).map((character, index) => (
        <span key={`${character}-${index}`} style={{ color: character.trim() ? colors[index % colors.length] : undefined }}>
          {character}
        </span>
      ))}
    </>
  );
}

function ReactNoteCard({ text, colorfulLetters }: { text: string; colorfulLetters: boolean }) {
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
        <div style={{ display: "grid", maxWidth: "82%", textAlign: "left" }}>
          <strong style={{ fontSize: 28, lineHeight: 1.2 }}>
            {colorfulLetters ? <ColorfulText text={text} /> : text}
          </strong>
        </div>
      </article>
    </section>
  );
}

const html = authoredHtml || renderToStaticMarkup(<ReactNoteCard text={text} colorfulLetters={useColorfulLetters} />);

process.stdout.write(
  JSON.stringify({
    cards: [
      {
        id: cardId,
        name: "React Note Card",
        prompt,
        html,
        sourceToolId: "react-note-card",
        metadata: {
          kind: "generic",
          title: "React Note Card",
          description: prompt,
          preferredAspectRatio: "1:1",
        },
      },
    ],
  }),
);
