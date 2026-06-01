import type {
  CardDocument,
  CardKind,
  CanvasNode,
  CanvasNodeFrame,
  SelectedCardMediaAsset,
  SelectedCardPreview,
  SelectedCardSnapshot,
} from "../types";

export const CARD_DEFAULT_WIDTH = 512;
export const CARD_MIN_WIDTH = 240;
export const CARD_MAX_WIDTH = 720;
export const CARD_ASPECT_HEIGHT_RATIO = 4 / 3;
export const CARD_GAP = 16;
export const CANVAS_PADDING = 24;
export const SELECTED_CARD_PREVIEW_MAX_BYTES = 2 * 1024 * 1024;
export const SELECTED_CARD_ASSET_MAX_BYTES = 5 * 1024 * 1024;
export const SELECTED_CARD_TOTAL_ASSET_MAX_BYTES = 10 * 1024 * 1024;
const API_URL = import.meta.env.VITE_API_URL ?? "";
const UNTITLED_CARD_TITLE = "Untitled card";
const DISPLAY_SUBTITLE_MAX_LENGTH = 92;
const TECHNICAL_TITLE_PATTERN = /^(?:card|node|job)_[a-z0-9-]{8,}$/i;
const TITLE_COUNTER_PATTERN = /^(.*?)(?:\s+(\d+))?$/;
const CARD_CHROME_HEIGHT = 0;
const CARD_TALLEST_PREVIEW_ASPECT_RATIO = 9 / 16;
const DOWNLOAD_EXTENSION_BY_KIND: Partial<Record<CardKind, string>> = {
  audio: "wav",
  diagnostic: "txt",
  generic: "html",
  image: "png",
  interactive: "html",
  video: "mp4",
};

export type CardPreviewCapture = () => SelectedCardPreview | Promise<SelectedCardPreview>;

export function hasPlayableMedia(cardHtml: string): boolean {
  return /<(video|audio)\b/i.test(cardHtml);
}

function getMetadataAspectRatio(document?: CardDocument): number | null {
  const width = document?.metadata?.width;
  const height = document?.metadata?.height;

  return width && height && width > 0 && height > 0 ? width / height : null;
}

export function getCardPreviewAspectRatioValue(document?: CardDocument): number {
  const metadataAspectRatio = getMetadataAspectRatio(document);
  if (metadataAspectRatio) return metadataAspectRatio;

  switch (document?.metadata?.preferredAspectRatio) {
    case "4:3":
      return 4 / 3;
    case "16:9":
      return 16 / 9;
    case "9:16":
      return 9 / 16;
    case "auto":
    case "1:1":
    default:
      return 1;
  }
}

export function getCardPreviewAspectRatioCss(document?: CardDocument): string {
  const metadataAspectRatio = getMetadataAspectRatio(document);
  if (metadataAspectRatio) return `${metadataAspectRatio}`;

  switch (document?.metadata?.preferredAspectRatio) {
    case "4:3":
      return "4 / 3";
    case "16:9":
      return "16 / 9";
    case "9:16":
      return "9 / 16";
    case "auto":
      return "auto";
    case "1:1":
    default:
      return "1 / 1";
  }
}

export function getCardHeight(width: number, document?: CardDocument) {
  const contentWidth = Math.max(0, width);
  const previewHeight = contentWidth / getCardPreviewAspectRatioValue(document);

  return previewHeight + CARD_CHROME_HEIGHT;
}

export function getCardLayoutRowHeight(width: number) {
  const contentWidth = Math.max(0, width);

  return contentWidth / CARD_TALLEST_PREVIEW_ASPECT_RATIO + CARD_CHROME_HEIGHT;
}

function cleanLabel(value?: string | null): string {
  return value?.trim().replace(/\s+/g, " ") ?? "";
}

function sanitizeFilename(value: string): string {
  return cleanLabel(value)
    .replace(/[<>:"/\\|?*\u0000-\u001f]/g, "-")
    .replace(/\.+$/g, "")
    .slice(0, 80) || UNTITLED_CARD_TITLE;
}

function getExtensionFromUrl(src: string): string | undefined {
  const pathname = src.startsWith("data:") ? "" : src.split("?", 1)[0].split("#", 1)[0];
  const extension = pathname.match(/\.([a-z0-9]{1,8})$/i)?.[1];

  return extension?.toLowerCase();
}

function getExtensionFromMimeType(mimeType?: string): string | undefined {
  if (!mimeType) return undefined;

  const knownTypes: Record<string, string> = {
    "application/json": "json",
    "application/pdf": "pdf",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "text/html": "html",
    "text/plain": "txt",
    "video/mp4": "mp4",
    "video/webm": "webm",
  };

  return knownTypes[mimeType] ?? mimeType.split("/", 2)[1]?.split("+", 1)[0];
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

export function getCardEditableTitle(document: CardDocument): string {
  return document.metadata?.title ?? document.name;
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
  const displayTitle = title.trim() ? title : getCardDisplayTitle(document);

  return {
    ...document,
    name: displayTitle,
    metadata: {
      ...document.metadata,
      title: displayTitle,
    },
  };
}

function estimateDataUrlBytes(dataUrl: string): number {
  const base64 = dataUrl.split(",", 2)[1] ?? "";

  return Math.ceil((base64.length * 3) / 4);
}

export function isDataUrlWithinLimit(dataUrl: string, maxBytes: number): boolean {
  return estimateDataUrlBytes(dataUrl) <= maxBytes;
}

function readNumberAttribute(element: Element, attributeName: string): number | undefined {
  const value = Number(element.getAttribute(attributeName));

  return Number.isFinite(value) && value > 0 ? value : undefined;
}

function readMimeType(element: Element, src: string): string | undefined {
  const declaredType = element.getAttribute("type")?.trim();
  if (declaredType) return declaredType;

  const dataUrlMatch = src.match(/^data:([^;,]+)/);
  return dataUrlMatch?.[1];
}

function createMediaAsset(
  element: Element,
  kind: SelectedCardMediaAsset["kind"],
  assetBudget: { totalBytes: number },
): SelectedCardMediaAsset {
  const src = element.getAttribute("src")?.trim() || element.getAttribute("href")?.trim() || undefined;
  const alt = element.getAttribute("alt")?.trim() || undefined;
  const width = readNumberAttribute(element, "width");
  const height = readNumberAttribute(element, "height");

  if (!src) {
    return {
      kind,
      alt,
      width,
      height,
      omitted: true,
      reason: "missing-source",
    };
  }

  const baseAsset = {
    kind,
    src,
    mimeType: readMimeType(element, src),
    alt,
    width,
    height,
  };

  if (!src.startsWith("data:")) {
    return baseAsset;
  }

  const dataUrlBytes = estimateDataUrlBytes(src);
  const exceedsAssetLimit = dataUrlBytes > SELECTED_CARD_ASSET_MAX_BYTES;
  const exceedsTotalLimit = assetBudget.totalBytes + dataUrlBytes > SELECTED_CARD_TOTAL_ASSET_MAX_BYTES;

  if (exceedsAssetLimit || exceedsTotalLimit) {
    return {
      ...baseAsset,
      omitted: true,
      reason: "size-limit",
    };
  }

  assetBudget.totalBytes += dataUrlBytes;

  return {
    ...baseAsset,
    dataUrl: src,
  };
}

export function extractSelectedCardMediaAssets(cardHtml: string): SelectedCardMediaAsset[] {
  const parser = new DOMParser();
  const parsedDocument = parser.parseFromString(cardHtml, "text/html");
  const assetBudget = { totalBytes: 0 };
  const selectors: Array<[string, SelectedCardMediaAsset["kind"]]> = [
    ["img", "image"],
    ["video", "video"],
    ["audio", "audio"],
    ["iframe", "iframe"],
    ["source", "source"],
    ["canvas", "canvas"],
  ];

  return selectors.flatMap(([selector, kind]) =>
    Array.from(parsedDocument.querySelectorAll(selector)).map((element) =>
      createMediaAsset(element, kind, assetBudget),
    ),
  );
}

export function getCardArtifactUrls(document: CardDocument): string[] {
  const candidates = [
    document.metadata?.artifactUrl,
    document.metadata?.thumbnailUrl,
    ...extractSelectedCardMediaAssets(document.html).flatMap((asset) => [asset.src, asset.dataUrl]),
  ];

  return candidates.filter((candidate, index): candidate is string =>
    Boolean(candidate?.startsWith("/api/artifacts/")) && candidates.indexOf(candidate) === index,
  );
}

function blobToDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();

    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(reader.error ?? new Error("Could not read artifact"));
    reader.readAsDataURL(blob);
  });
}

function artifactFetchCandidates(src: string): string[] {
  if (src.startsWith("data:")) return [];
  if (src.startsWith("http://") || src.startsWith("https://")) return [src];
  if (!src.startsWith("/api/artifacts/")) return [];

  return [
    API_URL ? `${API_URL}${src}` : "",
    src,
    `http://127.0.0.1:8001${src}`,
  ].filter((candidate, index, candidates) => Boolean(candidate) && candidates.indexOf(candidate) === index);
}

async function fetchArtifactDataUrl(src: string): Promise<{ dataUrl: string; mimeType?: string } | null> {
  for (const candidate of artifactFetchCandidates(src)) {
    try {
      const response = await fetch(candidate);
      if (!response.ok) continue;

      const blob = await response.blob();
      const dataUrl = await blobToDataUrl(blob);

      return {
        dataUrl,
        mimeType: blob.type || undefined,
      };
    } catch {
      // Try the next candidate; artifact URLs may be served by either Vite proxy or backend origin.
    }
  }

  return null;
}

function getPrimaryDownloadSource(document: CardDocument): { mimeType?: string; src: string } | null {
  if (document.metadata?.artifactUrl) {
    return { src: document.metadata.artifactUrl };
  }

  const mediaAsset = extractSelectedCardMediaAssets(document.html).find((asset) => asset.src || asset.dataUrl);
  const source = mediaAsset?.dataUrl ?? mediaAsset?.src;

  return source ? { src: source, mimeType: mediaAsset?.mimeType } : null;
}

function triggerBrowserDownload(href: string, filename: string) {
  const link = document.createElement("a");

  link.href = href;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
}

function revokeObjectUrlAfterDownload(objectUrl: string) {
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
}

export async function downloadCardDocument(document: CardDocument): Promise<void> {
  const downloadSource = getPrimaryDownloadSource(document);
  const extension =
    (downloadSource ? getExtensionFromUrl(downloadSource.src) || getExtensionFromMimeType(downloadSource.mimeType) : undefined) ||
    DOWNLOAD_EXTENSION_BY_KIND[document.metadata?.kind ?? "generic"] ||
    "html";
  const filename = `${sanitizeFilename(getCardDisplayTitle(document))}.${extension}`;

  if (!downloadSource) {
    const blob = new Blob([document.html], { type: "text/html" });
    const objectUrl = URL.createObjectURL(blob);

    triggerBrowserDownload(objectUrl, filename);
    revokeObjectUrlAfterDownload(objectUrl);
    return;
  }

  if (downloadSource.src.startsWith("data:")) {
    triggerBrowserDownload(downloadSource.src, filename);
    return;
  }

  const candidates = artifactFetchCandidates(downloadSource.src);
  for (const candidate of candidates) {
    try {
      const response = await fetch(candidate);
      if (!response.ok) continue;

      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);

      triggerBrowserDownload(objectUrl, filename);
      revokeObjectUrlAfterDownload(objectUrl);
      return;
    } catch {
      // Try the next candidate; artifact URLs may be served by either Vite proxy or backend origin.
    }
  }

  triggerBrowserDownload(downloadSource.src, filename);
}

async function hydrateMediaAssets(
  assets: SelectedCardMediaAsset[],
  initialTotalBytes = 0,
): Promise<SelectedCardMediaAsset[]> {
  const assetBudget = { totalBytes: initialTotalBytes };
  const hydratedAssets: SelectedCardMediaAsset[] = [];

  for (const asset of assets) {
    if (asset.dataUrl || asset.omitted || !asset.src || !["image", "video", "audio"].includes(asset.kind)) {
      hydratedAssets.push(asset);
      continue;
    }

    const fetched = await fetchArtifactDataUrl(asset.src);
    if (!fetched) {
      hydratedAssets.push({
        ...asset,
        omitted: true,
        reason: "fetch-error",
      });
      continue;
    }

    const dataUrlBytes = estimateDataUrlBytes(fetched.dataUrl);
    const exceedsAssetLimit = dataUrlBytes > SELECTED_CARD_ASSET_MAX_BYTES;
    const exceedsTotalLimit = assetBudget.totalBytes + dataUrlBytes > SELECTED_CARD_TOTAL_ASSET_MAX_BYTES;
    if (exceedsAssetLimit || exceedsTotalLimit) {
      hydratedAssets.push({
        ...asset,
        mimeType: asset.mimeType ?? fetched.mimeType,
        omitted: true,
        reason: "size-limit",
      });
      continue;
    }

    assetBudget.totalBytes += dataUrlBytes;
    hydratedAssets.push({
      ...asset,
      mimeType: asset.mimeType ?? fetched.mimeType,
      dataUrl: fetched.dataUrl,
    });
  }

  return hydratedAssets;
}

function createUnavailablePreview(reason: Extract<SelectedCardPreview, { omitted: true }>["reason"]): SelectedCardPreview {
  return {
    source: "rendered-preview",
    omitted: true,
    reason,
  };
}

export async function createSelectedCardSnapshots(
  documents: CardDocument[],
  selectedCardIds: string[],
  previewCaptures: Map<string, CardPreviewCapture> = new Map(),
): Promise<SelectedCardSnapshot[]> {
  const documentsById = new Map(documents.map((document) => [document.id, document]));
  const snapshots: SelectedCardSnapshot[] = [];

  for (const cardId of selectedCardIds) {
    const document = documentsById.get(cardId);
    if (!document) continue;

    const capturePreview = previewCaptures.get(cardId);
    let preview: SelectedCardPreview = createUnavailablePreview("capture-unavailable");

    if (capturePreview) {
      try {
        preview = await capturePreview();
      } catch {
        preview = createUnavailablePreview("capture-unavailable");
      }
    }

    snapshots.push({
      id: document.id,
      name: document.name,
      displayTitle: getCardDisplayTitle(document),
      prompt: document.prompt,
      html: document.html,
      preview,
      mediaAssets: await hydrateMediaAssets(extractSelectedCardMediaAssets(document.html)),
      sourceSkillId: document.sourceSkillId,
      sourceActionId: document.sourceActionId,
      metadata: document.metadata,
    });
  }

  return snapshots;
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
  document?: CardDocument,
): CanvasNodeFrame {
  const maxWidth = Math.min(CARD_MAX_WIDTH, Math.max(CARD_MIN_WIDTH, canvasWidth - CANVAS_PADDING * 2));
  const width = Math.min(Math.max(frame.width, CARD_MIN_WIDTH), maxWidth);
  const height = getCardHeight(width, document);
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
    y: CANVAS_PADDING + row * (getCardLayoutRowHeight(CARD_DEFAULT_WIDTH) + CARD_GAP),
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
