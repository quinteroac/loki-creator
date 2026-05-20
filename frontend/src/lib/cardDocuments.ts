import type { CardDocument, CanvasNode, CanvasNodeFrame } from "../types";

export const CARD_DEFAULT_WIDTH = 512;
export const CARD_MIN_WIDTH = 240;
export const CARD_MAX_WIDTH = 720;
export const CARD_ASPECT_HEIGHT_RATIO = 4 / 3;
export const CARD_GAP = 16;
export const CANVAS_PADDING = 24;
const UNTITLED_CARD_TITLE = "Untitled card";
const DISPLAY_SUBTITLE_MAX_LENGTH = 92;
const TECHNICAL_TITLE_PATTERN = /^(?:card|node|job)_[a-z0-9-]{8,}$/i;
const TITLE_COUNTER_PATTERN = /^(.*?)(?:\s+(\d+))?$/;

export function hasPlayableMedia(cardHtml: string): boolean {
  return /<(video|audio)\b/i.test(cardHtml);
}

export function getCardHeight(width: number) {
  return width * CARD_ASPECT_HEIGHT_RATIO;
}

function cleanLabel(value?: string | null): string {
  return value?.trim().replace(/\s+/g, " ") ?? "";
}

function isTechnicalTitle(value: string): boolean {
  return TECHNICAL_TITLE_PATTERN.test(value);
}

function getCardTitleBase(document: CardDocument): string {
  const candidates = [document.metadata?.title, document.name].map(cleanLabel);
  const displayTitle = candidates.find((candidate) => candidate && !isTechnicalTitle(candidate));

  return displayTitle || UNTITLED_CARD_TITLE;
}

function splitTitleCounter(title: string): { base: string; counter: number } {
  const match = title.match(TITLE_COUNTER_PATTERN);
  const base = cleanLabel(match?.[1]) || UNTITLED_CARD_TITLE;
  const counter = Number(match?.[2] ?? 1);

  return {
    base,
    counter: Number.isFinite(counter) && counter > 0 ? counter : 1,
  };
}

function getNextDisplayTitle(baseTitle: string, existingTitles: Map<string, number>): string {
  const { base } = splitTitleCounter(baseTitle);
  const nextCounter = (existingTitles.get(base.toLowerCase()) ?? 0) + 1;

  existingTitles.set(base.toLowerCase(), nextCounter);

  return nextCounter === 1 ? base : `${base} ${nextCounter}`;
}

function collectExistingTitleCounters(documents: CardDocument[]): Map<string, number> {
  const counters = new Map<string, number>();

  documents.forEach((document) => {
    const title = getCardDisplayTitle(document);
    const { base, counter } = splitTitleCounter(title);
    const key = base.toLowerCase();

    counters.set(key, Math.max(counters.get(key) ?? 0, counter));
  });

  return counters;
}

export function getCardDisplayTitle(document: CardDocument): string {
  return getCardTitleBase(document);
}

export function getCardDisplaySubtitle(document: CardDocument): string {
  const subtitle = cleanLabel(document.metadata?.description) || cleanLabel(document.prompt);

  if (subtitle.length <= DISPLAY_SUBTITLE_MAX_LENGTH) return subtitle;

  return `${subtitle.slice(0, DISPLAY_SUBTITLE_MAX_LENGTH - 1).trim()}...`;
}

export function assignUniqueDisplayTitles(
  documents: CardDocument[],
  existingDocuments: CardDocument[],
): CardDocument[] {
  const titleCounters = collectExistingTitleCounters(existingDocuments);

  return documents.map((document) => {
    const displayTitle = getNextDisplayTitle(getCardTitleBase(document), titleCounters);

    return {
      ...document,
      name: displayTitle,
      metadata: {
        ...document.metadata,
        title: displayTitle,
      },
    };
  });
}

export function renameCardDocument(document: CardDocument, title: string): CardDocument {
  const displayTitle = cleanLabel(title) || getCardDisplayTitle(document);

  return {
    ...document,
    name: displayTitle,
    metadata: {
      ...document.metadata,
      title: displayTitle,
    },
  };
}

export function normalizeCardDocument(card: CardDocument): CardDocument {
  const playableMedia = card.metadata?.playableMedia ?? hasPlayableMedia(card.html);

  return {
    ...card,
    metadata: {
      kind: "generic",
      title: card.name,
      description: card.prompt,
      preferredAspectRatio: "1:1",
      playableMedia,
      ...card.metadata,
    },
  };
}

export function clampCanvasNodeFrame(
  frame: CanvasNodeFrame,
  canvasWidth: number,
  canvasHeight: number,
): CanvasNodeFrame {
  const maxWidth = Math.min(CARD_MAX_WIDTH, Math.max(CARD_MIN_WIDTH, canvasWidth - CANVAS_PADDING * 2));
  const width = Math.min(Math.max(frame.width, CARD_MIN_WIDTH), maxWidth);
  const height = getCardHeight(width);
  const maxX = Math.max(0, canvasWidth - width - CANVAS_PADDING);
  const maxY = Math.max(0, canvasHeight - height - CANVAS_PADDING);

  return {
    x: Math.min(Math.max(0, frame.x), maxX),
    y: Math.min(Math.max(0, frame.y), maxY),
    width,
  };
}

export function getInitialCanvasNodeFrame(index: number, canvasWidth: number): CanvasNodeFrame {
  const availableWidth = Math.max(CARD_DEFAULT_WIDTH, canvasWidth - CANVAS_PADDING * 2);
  const columnCount = Math.max(1, Math.floor((availableWidth + CARD_GAP) / (CARD_DEFAULT_WIDTH + CARD_GAP)));
  const column = index % columnCount;
  const row = Math.floor(index / columnCount);

  return {
    x: CANVAS_PADDING + column * (CARD_DEFAULT_WIDTH + CARD_GAP),
    y: CANVAS_PADDING + row * (getCardHeight(CARD_DEFAULT_WIDTH) + CARD_GAP),
    width: CARD_DEFAULT_WIDTH,
  };
}

export function createCanvasNodeForDocument(
  document: CardDocument,
  index: number,
  canvasWidth: number,
): CanvasNode {
  return {
    id: `node_${document.id}`,
    cardDocumentId: document.id,
    frame: getInitialCanvasNodeFrame(index, canvasWidth),
  };
}
