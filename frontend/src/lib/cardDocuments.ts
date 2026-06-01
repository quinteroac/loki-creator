import type {
  AgentAttachment,
  CardAspectRatio,
  CardDocument,
  CardKind,
  CanvasNode,
  CanvasNodeFrame,
  SelectedCardMediaAsset,
  SelectedCardPreview,
  SelectedCardSnapshot,
} from "../types";
import type { ImportedArtifact } from "../api/artifacts";

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

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

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

function attachmentCardBody(attachment: AgentAttachment): string {
  const title = escapeHtml(attachment.name);
  const mimeType = escapeHtml(attachment.mimeType);

  if (attachment.omitted) {
    return `<main><strong>${title}</strong><span>${mimeType}</span><p>Attachment omitted: ${escapeHtml(attachment.reason ?? "unavailable")}</p></main>`;
  }

  if (attachment.kind === "image" && attachment.dataUrl) {
    return `<img src="${attachment.dataUrl}" alt="${title}" />`;
  }

  if (attachment.kind === "video" && attachment.dataUrl) {
    return `<video src="${attachment.dataUrl}" controls playsinline preload="metadata"></video>`;
  }

  if (attachment.kind === "audio" && attachment.dataUrl) {
    return `<main><strong>${title}</strong><audio src="${attachment.dataUrl}" controls preload="metadata"></audio></main>`;
  }

  if (attachment.kind === "pdf" && attachment.dataUrl) {
    return `<iframe src="${attachment.dataUrl}" title="${title}"></iframe>`;
  }

  if ((attachment.kind === "text" || attachment.kind === "json") && attachment.text) {
    return `<main class="text-card"><strong>${title}</strong><pre>${escapeHtml(attachment.text)}</pre></main>`;
  }

  if (attachment.dataUrl) {
    return `<main><strong>${title}</strong><span>${mimeType}</span><a href="${attachment.dataUrl}" download="${title}">Open attachment</a></main>`;
  }

  return `<main><strong>${title}</strong><span>${mimeType}</span><p>No preview available.</p></main>`;
}

function attachmentCardHtml(attachment: AgentAttachment): string {
  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <style>
      html, body { width: 100%; height: 100%; margin: 0; background: #111111; color: #ffffff; font-family: "DM Sans", Inter, sans-serif; }
      body { display: grid; place-items: center; overflow: hidden; }
      img, video, iframe { display: block; width: 100%; height: 100%; border: 0; object-fit: contain; background: #111111; }
      main { box-sizing: border-box; width: 100%; height: 100%; display: grid; place-items: center; gap: 12px; padding: 24px; text-align: center; }
      strong { max-width: 100%; overflow-wrap: anywhere; font-size: 18px; line-height: 1.4; }
      span, p, a { margin: 0; color: #b5bac3; font-size: 13px; line-height: 1.5; }
      a { color: #69d8ff; }
      audio { width: min(360px, 90%); }
      .text-card { place-items: stretch; text-align: left; }
      pre { box-sizing: border-box; width: 100%; height: 100%; min-height: 0; margin: 0; overflow: auto; white-space: pre-wrap; word-break: break-word; font: 13px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace; }
    </style>
  </head>
  <body>${attachmentCardBody(attachment)}</body>
</html>`;
}

function attachmentCardKind(attachment: AgentAttachment): CardKind {
  if (attachment.omitted) return "diagnostic";
  if (attachment.kind === "pdf" || attachment.kind === "text" || attachment.kind === "json") return "interactive";
  if (attachment.kind === "artifact") return "artifact";
  return attachment.kind;
}

function attachmentPreferredAspectRatio(attachment: AgentAttachment): CardAspectRatio {
  if (attachment.kind === "video") return "16:9";
  if (attachment.kind === "text" || attachment.kind === "json" || attachment.kind === "pdf") return "4:3";
  return "1:1";
}

function importedArtifactKind(artifact: ImportedArtifact): CardKind {
  if (artifact.mimeType.startsWith("image/")) return "image";
  if (artifact.mimeType.startsWith("video/")) return "video";
  if (artifact.mimeType.startsWith("audio/")) return "audio";
  if (artifact.mimeType === "application/pdf" || artifact.mimeType.startsWith("text/")) return "interactive";

  return "artifact";
}

function importedArtifactPreferredAspectRatio(artifact: ImportedArtifact): CardAspectRatio {
  if (artifact.mimeType.startsWith("video/")) return "16:9";
  if (artifact.mimeType === "application/pdf" || artifact.mimeType.startsWith("text/")) return "4:3";

  return "1:1";
}

function importedArtifactBody(artifact: ImportedArtifact): string {
  const title = escapeHtml(artifact.name);
  const source = escapeHtml(artifact.artifactUrl);
  const mimeType = escapeHtml(artifact.mimeType);

  if (artifact.mimeType.startsWith("image/")) {
    return `<img src="${source}" alt="${title}" />`;
  }

  if (artifact.mimeType.startsWith("video/")) {
    return `<video src="${source}" controls playsinline preload="metadata"></video>`;
  }

  if (artifact.mimeType.startsWith("audio/")) {
    return `<main><strong>${title}</strong><audio src="${source}" controls preload="metadata"></audio></main>`;
  }

  if (artifact.mimeType === "application/pdf") {
    return `<iframe src="${source}" title="${title}"></iframe>`;
  }

  if (artifact.mimeType.startsWith("text/")) {
    return `<iframe src="${source}" title="${title}"></iframe>`;
  }

  return `<main><strong>${title}</strong><span>${mimeType}</span><a href="${source}">Open attachment</a></main>`;
}

function importedArtifactHtml(artifact: ImportedArtifact): string {
  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <style>
      html, body { width: 100%; height: 100%; margin: 0; background: #111111; color: #ffffff; font-family: "DM Sans", Inter, sans-serif; }
      body { display: grid; place-items: center; overflow: hidden; }
      img, video, iframe { display: block; width: 100%; height: 100%; border: 0; object-fit: contain; background: #111111; }
      main { box-sizing: border-box; width: 100%; height: 100%; display: grid; place-items: center; gap: 12px; padding: 24px; text-align: center; }
      strong { max-width: 100%; overflow-wrap: anywhere; font-size: 18px; line-height: 1.4; }
      span, p, a { margin: 0; color: #b5bac3; font-size: 13px; line-height: 1.5; }
      a { color: #69d8ff; }
      audio { width: min(360px, 90%); }
    </style>
  </head>
  <body>${importedArtifactBody(artifact)}</body>
</html>`;
}

function getFilePreviewObjectUrl(file: File): string {
  return URL.createObjectURL(file);
}

function readImageDimensions(dataUrl: string): Promise<{ height: number; width: number } | null> {
  return new Promise((resolve) => {
    const image = new Image();

    image.onload = () => resolve({ height: image.naturalHeight, width: image.naturalWidth });
    image.onerror = () => resolve(null);
    image.src = dataUrl;
  });
}

function readVideoDimensions(dataUrl: string): Promise<{ height: number; width: number } | null> {
  return new Promise((resolve) => {
    const video = document.createElement("video");

    video.preload = "metadata";
    video.onloadedmetadata = () => {
      video.removeAttribute("src");
      video.load();
      resolve({ height: video.videoHeight, width: video.videoWidth });
    };
    video.onerror = () => resolve(null);
    video.src = dataUrl;
  });
}

async function getAttachmentDimensions(attachment: AgentAttachment): Promise<{ height: number; width: number } | null> {
  if (!attachment.dataUrl || attachment.omitted) return null;
  if (attachment.kind === "image") return readImageDimensions(attachment.dataUrl);
  if (attachment.kind === "video") return readVideoDimensions(attachment.dataUrl);

  return null;
}

export async function getFileDimensions(file: File): Promise<{ height: number; width: number } | null> {
  if (!file.type.startsWith("image/") && !file.type.startsWith("video/")) return null;

  const objectUrl = getFilePreviewObjectUrl(file);
  try {
    return file.type.startsWith("image/") ? await readImageDimensions(objectUrl) : await readVideoDimensions(objectUrl);
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

export function createCardDocumentForImportedArtifact(
  artifact: ImportedArtifact,
  dimensions: { height: number; width: number } | null,
): CardDocument {
  const kind = importedArtifactKind(artifact);

  return {
    id: `card_import_${crypto.randomUUID?.().replaceAll("-", "") ?? Date.now().toString(36)}`,
    name: artifact.name,
    prompt: `Imported file: ${artifact.name}`,
    html: importedArtifactHtml(artifact),
    sourceSkillId: "attachment",
    sourceActionId: "file-import",
    metadata: {
      kind,
      title: artifact.name,
      description: `${artifact.mimeType} imported file`,
      artifactUrl: artifact.artifactUrl,
      thumbnailUrl: kind === "image" ? artifact.artifactUrl : undefined,
      createdAt: new Date().toISOString(),
      tags: ["attachment", "import"],
      capabilities: ["attachment"],
      preferredAspectRatio: importedArtifactPreferredAspectRatio(artifact),
      playableMedia: ["video", "audio", "interactive"].includes(kind),
      ...(dimensions ?? {}),
    },
  };
}

export async function createCardDocumentForAttachment(attachment: AgentAttachment): Promise<CardDocument> {
  const kind = attachmentCardKind(attachment);
  const dimensions = await getAttachmentDimensions(attachment);

  return {
    id: `card_${attachment.id}`,
    name: attachment.name,
    prompt: `Attached file: ${attachment.name}`,
    html: attachmentCardHtml(attachment),
    sourceSkillId: "attachment",
    sourceActionId: "file-picker",
    metadata: {
      kind,
      title: attachment.name,
      description: `${attachment.kind} attachment (${attachment.mimeType})`,
      createdAt: new Date().toISOString(),
      tags: ["attachment", attachment.kind],
      capabilities: ["attachment"],
      preferredAspectRatio: attachmentPreferredAspectRatio(attachment),
      playableMedia: ["video", "audio", "pdf"].includes(attachment.kind),
      ...(dimensions ?? {}),
    },
  };
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
