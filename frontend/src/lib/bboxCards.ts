import type { CardAspectRatio, CardDocument, CardKind } from "../types";

export type IdeogramAspectRatio = "1:1" | "3:2" | "4:3" | "16:9" | "21:9" | "2:3" | "3:4" | "9:16";

export type BboxSource = {
  artifactUrl?: string;
  cardId: string;
  height?: number;
  kind: Extract<CardKind, "image" | "video">;
  title: string;
  width?: number;
};

export type NormalizedBbox = {
  height: number;
  id: string;
  ideogramBbox: [number, number, number, number];
  label: string;
  prompt: string;
  width: number;
  x: number;
  y: number;
};

export type BboxCardData = {
  boxes: NormalizedBbox[];
  canvas: {
    aspectRatio: IdeogramAspectRatio;
    height: number;
    width: number;
  };
  source: BboxSource | null;
  version: 1;
};

export const IDEOGRAM_ASPECT_DIMENSIONS: Record<IdeogramAspectRatio, { height: number; width: number }> = {
  "1:1": { width: 1024, height: 1024 },
  "3:2": { width: 1248, height: 832 },
  "4:3": { width: 1152, height: 864 },
  "16:9": { width: 1360, height: 768 },
  "21:9": { width: 1344, height: 576 },
  "2:3": { width: 832, height: 1248 },
  "3:4": { width: 864, height: 1152 },
  "9:16": { width: 768, height: 1360 },
};

const BBOX_MIN_SIZE = 0.01;

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function clamp(value: number, min = 0, max = 1): number {
  return Math.min(Math.max(value, min), max);
}

function isIdeogramAspectRatio(value: unknown): value is IdeogramAspectRatio {
  return typeof value === "string" && value in IDEOGRAM_ASPECT_DIMENSIONS;
}

function positiveInteger(value: unknown): number | null {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue) || numericValue <= 0) return null;

  return Math.round(numericValue);
}

export function createClientBboxId(): string {
  return `bbox_${globalThis.crypto?.randomUUID?.().replaceAll("-", "") ?? Date.now().toString(36)}`;
}

export function ideogramBboxFromNormalized(box: Pick<NormalizedBbox, "height" | "width" | "x" | "y">): [number, number, number, number] {
  const xMin = Math.round(clamp(box.x) * 1000);
  const yMin = Math.round(clamp(box.y) * 1000);
  const xMax = Math.round(clamp(box.x + box.width) * 1000);
  const yMax = Math.round(clamp(box.y + box.height) * 1000);

  return [yMin, xMin, yMax, xMax];
}

export function clampNormalizedBbox(box: Omit<NormalizedBbox, "ideogramBbox">): NormalizedBbox {
  const safeX = Number.isFinite(box.x) ? box.x : 0;
  const safeY = Number.isFinite(box.y) ? box.y : 0;
  const safeWidth = Number.isFinite(box.width) ? box.width : BBOX_MIN_SIZE;
  const safeHeight = Number.isFinite(box.height) ? box.height : BBOX_MIN_SIZE;
  const x = clamp(safeX);
  const y = clamp(safeY);
  const width = Math.min(Math.max(safeWidth, BBOX_MIN_SIZE), 1 - x);
  const height = Math.min(Math.max(safeHeight, BBOX_MIN_SIZE), 1 - y);
  const clampedBox = {
    ...box,
    height,
    width,
    x,
    y,
  };

  return {
    ...clampedBox,
    ideogramBbox: ideogramBboxFromNormalized(clampedBox),
  };
}

export function normalizeBboxData(value: unknown): BboxCardData {
  const raw = typeof value === "object" && value !== null ? value as Record<string, unknown> : {};
  const rawCanvas = typeof raw.canvas === "object" && raw.canvas !== null ? raw.canvas as Record<string, unknown> : {};
  const aspectRatio = isIdeogramAspectRatio(rawCanvas.aspectRatio) ? rawCanvas.aspectRatio : "1:1";
  const presetDimensions = IDEOGRAM_ASPECT_DIMENSIONS[aspectRatio];
  const width = positiveInteger(rawCanvas.width) ?? presetDimensions.width;
  const height = positiveInteger(rawCanvas.height) ?? presetDimensions.height;
  const rawSource = typeof raw.source === "object" && raw.source !== null ? raw.source as Record<string, unknown> : null;
  const sourceKind: BboxSource["kind"] | null =
    rawSource?.kind === "image" || rawSource?.kind === "video" ? rawSource.kind : null;
  const source = rawSource && sourceKind && typeof rawSource.cardId === "string" && typeof rawSource.title === "string"
    ? {
      cardId: rawSource.cardId,
      title: rawSource.title,
      kind: sourceKind,
      artifactUrl: typeof rawSource.artifactUrl === "string" ? rawSource.artifactUrl : undefined,
      width: positiveInteger(rawSource.width) ?? undefined,
      height: positiveInteger(rawSource.height) ?? undefined,
    }
    : null;
  const boxes = Array.isArray(raw.boxes)
    ? raw.boxes.flatMap((rawBox, index) => {
      if (typeof rawBox !== "object" || rawBox === null) return [];
      const box = rawBox as Record<string, unknown>;
      const normalizedBox = clampNormalizedBbox({
        id: typeof box.id === "string" && box.id ? box.id : `bbox_${index + 1}`,
        label: typeof box.label === "string" && box.label ? box.label : `Box ${index + 1}`,
        prompt: typeof box.prompt === "string" ? box.prompt : "",
        x: Number(box.x),
        y: Number(box.y),
        width: Number(box.width),
        height: Number(box.height),
      });

      return Number.isFinite(normalizedBox.x) && Number.isFinite(normalizedBox.y) ? [normalizedBox] : [];
    })
    : [];

  return {
    version: 1,
    canvas: { width, height, aspectRatio },
    source,
    boxes,
  };
}

export function withBboxCanvas(data: BboxCardData, canvas: BboxCardData["canvas"]): BboxCardData {
  return normalizeBboxData({
    ...data,
    canvas,
  });
}

export function withBboxBoxes(data: BboxCardData, boxes: Array<Omit<NormalizedBbox, "ideogramBbox"> | NormalizedBbox>): BboxCardData {
  return normalizeBboxData({
    ...data,
    boxes,
  });
}

export function getBboxData(document: CardDocument): BboxCardData {
  return normalizeBboxData(document.metadata?.bboxData);
}

export function isBboxSourceDocument(document?: CardDocument): document is CardDocument {
  return document?.metadata?.kind === "image" || document?.metadata?.kind === "video";
}

export function bboxCardHtml(data: BboxCardData, title: string): string {
  const escapedTitle = escapeHtml(title);
  const media = data.source?.artifactUrl
    ? data.source.kind === "video"
      ? `<video src="${escapeHtml(data.source.artifactUrl)}" muted playsinline preload="metadata"></video>`
      : `<img src="${escapeHtml(data.source.artifactUrl)}" alt="${escapeHtml(data.source.title)}" />`
    : "";
  const boxes = data.boxes.map((box) => {
    const style = `left:${box.x * 100}%;top:${box.y * 100}%;width:${box.width * 100}%;height:${box.height * 100}%;`;
    const promptAttributes = box.prompt
      ? ` title="${escapeHtml(box.prompt)}" data-prompt="${escapeHtml(box.prompt)}"`
      : ` data-prompt=""`;
    return `<span class="bbox" style="${style}"${promptAttributes}><small>${escapeHtml(box.label)}</small></span>`;
  }).join("");

  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <style>
      html, body { width: 100%; height: 100%; margin: 0; background: #ffffff; color: #111111; font-family: "DM Sans", Inter, sans-serif; }
      body { position: relative; overflow: hidden; }
      img, video { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: contain; background: #ffffff; }
      .bbox { position: absolute; box-sizing: border-box; border: 2px solid #245cff; background: rgba(36, 92, 255, 0.16); }
      .bbox small { position: absolute; top: 0; left: 0; max-width: 100%; padding: 3px 6px; overflow: hidden; color: #ffffff; background: #245cff; font-size: 12px; font-weight: 700; line-height: 1.2; text-overflow: ellipsis; white-space: nowrap; }
      .title { position: absolute; left: 10px; bottom: 10px; padding: 4px 8px; color: #ffffff; background: rgba(17, 17, 17, 0.72); border-radius: 9999px; font-size: 12px; font-weight: 700; }
    </style>
  </head>
  <body>${media}${boxes}<span class="title">${escapedTitle}</span></body>
</html>`;
}

export function bboxDescription(data: BboxCardData): string {
  const source = data.source ? `${data.source.kind} ${data.source.title}` : "white canvas";
  const promptedBoxes = data.boxes.filter((box) => box.prompt.trim()).length;
  const promptSummary = promptedBoxes ? `, ${promptedBoxes} with prompt${promptedBoxes === 1 ? "" : "s"}` : "";
  return `${data.boxes.length} bbox${data.boxes.length === 1 ? "" : "es"}${promptSummary} on ${source}`;
}
