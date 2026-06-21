import { memo, useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties, ChangeEvent, ClipboardEvent, FormEvent, KeyboardEvent, MouseEvent, PointerEvent } from "react";
import { layout, prepare } from "@chenglou/pretext";
import { Copy, Download, Info, RotateCcw, Scissors, Trash2 } from "lucide-react";
import {
  downloadCardDocument,
  extractSelectedCardMediaAssets,
  getCardEditableTitle,
  getCardDisplayTitle,
  getCardHeight,
  getCardPreviewAspectRatioCss,
  hasPlayableMedia,
  isDataUrlWithinLimit,
  SELECTED_CARD_PREVIEW_MAX_BYTES,
} from "../lib/cardDocuments";
import { getBboxData, type BboxCardData } from "../lib/bboxCards";
import type { CardDocument, CanvasNode, CanvasNodeFrame, EditedMediaArtifact, SelectedCardPreview } from "../types";
import { AudioTimelineEditor } from "./AudioTimelineEditor";
import { BboxCardEditor } from "./BboxCardEditor";
import { VideoTimelineEditor } from "./VideoTimelineEditor";

type CanvasRenderingContext2DWithHtml = CanvasRenderingContext2D & {
  drawElementImage?: (element: Element, x: number, y: number, width: number, height: number) => void;
};

type HtmlCanvasDrawStatus = "drawn" | "pending" | "unsupported";

type CanvasCardProps = {
  document: CardDocument;
  node: CanvasNode;
  isSelected: boolean;
  onDeleteDocument: (cardDocumentId: string) => void;
  onCreateEditedMediaArtifact: (artifact: EditedMediaArtifact, sourceNodeId: string, placementOffset?: number) => void;
  onCloseMediaEditor: () => void;
  onContextMenuOpenChange: (nodeId: string, isOpen: boolean) => void;
  onOpenMediaEditor: (nodeId: string) => void;
  onRenameDocument: (cardDocumentId: string, title: string) => void;
  onRedoDocument: (cardDocumentId: string) => void;
  onRegisterPreviewCapture: (cardDocumentId: string, capturePreview: () => SelectedCardPreview) => () => void;
  onStatus: (message: string) => void;
  onUpdateBboxData: (cardDocumentId: string, data: BboxCardData) => void;
  onUpdateDocumentPrompt: (cardDocumentId: string, prompt: string) => void;
  onUpdateFrame: (nodeId: string, frame: CanvasNodeFrame) => void;
  onToggleSelect: (nodeId: string) => void;
  isMediaEditorOpen: boolean;
  zoom: number;
};

const CONTEXT_MENU_WIDTH = 176;
const CONTEXT_MENU_ESTIMATED_HEIGHT = 200;
const CONTEXT_MENU_OFFSET = 8;
const NOTE_TITLE_HEIGHT = 52;
const CARD_TEXT_FONT_FAMILY = '"DM Sans", Inter, "Helvetica Neue", Helvetica, Arial, sans-serif';
const NOTE_TEXT_FONT_SIZE = 18;
const NOTE_TEXT_LINE_HEIGHT = NOTE_TEXT_FONT_SIZE * 1.45;
const NOTE_TEXT_HORIZONTAL_PADDING = 44;
const NOTE_TEXT_VERTICAL_PADDING = 28;
const METADATA_HORIZONTAL_PADDING = 44;
const PRETEXT_CACHE_LIMIT = 200;
const pretextPreparedCache = new Map<string, ReturnType<typeof prepare>>();

type TextFit = {
  fontSize: number;
  lineHeight: number;
};

function resizeCanvas(canvas: HTMLCanvasElement) {
  const pixelRatio = window.devicePixelRatio || 1;
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;

  canvas.width = width * pixelRatio;
  canvas.height = height * pixelRatio;

  return { height, pixelRatio, width };
}

function supportsHtmlInCanvas(context: CanvasRenderingContext2DWithHtml | null): boolean {
  return typeof context?.drawElementImage === "function";
}

function drawHtmlInCanvas(canvas: HTMLCanvasElement, htmlElement: HTMLDivElement | null): HtmlCanvasDrawStatus {
  const context = canvas.getContext("2d") as CanvasRenderingContext2DWithHtml | null;

  if (!supportsHtmlInCanvas(context)) return "unsupported";
  if (!htmlElement) return "pending";
  if (!context?.drawElementImage) return "unsupported";

  const { height, pixelRatio, width } = resizeCanvas(canvas);
  context.reset?.();
  context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);

  try {
    context.drawElementImage(htmlElement, 0, 0, width, height);
  } catch (error) {
    if (error instanceof DOMException && error.name === "InvalidStateError") {
      return "pending";
    }

    throw error;
  }

  return "drawn";
}

function normalizeAudioPreviewHtml(cardHtml: string, document: CardDocument): string {
  if (document.metadata?.kind !== "audio") return cardHtml;

  return cardHtml.replace(
    /(<strong\b[^>]*>[\s\S]*?<\/strong>)(\s*<audio\b[\s\S]*?<\/audio>)/i,
    "$2$1",
  );
}

function createIframeSrcDoc(document: CardDocument): string {
  const cardHtml = normalizeAudioPreviewHtml(document.html, document);

  return `<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <style>
      html,
      body {
        width: 100%;
        height: 100%;
        margin: 0;
        overflow: hidden;
        background: #000000;
      }

      * {
        box-sizing: border-box;
      }
    </style>
  </head>
  <body>${cardHtml}</body>
</html>`;
}

function shouldUsePlayableMediaFallback(document: CardDocument): boolean {
  return document.metadata?.playableMedia ?? hasPlayableMedia(document.html);
}

function getAudioPreviewSource(document: CardDocument): string | null {
  if (document.metadata?.kind !== "audio") return null;
  if (document.metadata.artifactUrl) return document.metadata.artifactUrl;

  const audioAsset = extractSelectedCardMediaAssets(document.html).find((asset) => asset.kind === "audio");
  return audioAsset?.dataUrl ?? audioAsset?.src ?? null;
}

function getPreparedText(text: string, fontSize: number, fontWeight: number) {
  const cacheKey = `${fontWeight}|${fontSize}|${text}`;
  const cached = pretextPreparedCache.get(cacheKey);
  if (cached) return cached;

  const prepared = prepare(text, `${fontWeight} ${fontSize}px ${CARD_TEXT_FONT_FAMILY}`, { whiteSpace: "pre-wrap" });
  pretextPreparedCache.set(cacheKey, prepared);
  if (pretextPreparedCache.size > PRETEXT_CACHE_LIMIT) {
    const oldestKey = pretextPreparedCache.keys().next().value;
    if (oldestKey) pretextPreparedCache.delete(oldestKey);
  }
  return prepared;
}

function pretextHeight(text: string, width: number, fontSize: number, lineHeight: number, fontWeight: number) {
  const normalizedWidth = Math.max(1, width);

  try {
    const prepared = getPreparedText(text, fontSize, fontWeight);
    const result = layout(prepared, normalizedWidth, lineHeight);
    return Math.max(lineHeight, result.height);
  } catch {
    return lineHeight;
  }
}

function fitTextBlock(
  text: string,
  width: number,
  maxHeight: number,
  {
    maxFontSize,
    minFontSize,
    weight,
  }: {
    maxFontSize: number;
    minFontSize: number;
    weight: number;
  },
): TextFit {
  const content = text.trim() || "Prompt";
  const availableWidth = Math.max(1, width);
  const availableHeight = Math.max(1, maxHeight);

  for (let fontSize = maxFontSize; fontSize >= minFontSize; fontSize -= 1) {
    const lineHeight = fontSize * 1.45;
    if (pretextHeight(content, availableWidth, fontSize, lineHeight, weight) <= availableHeight) {
      return { fontSize, lineHeight };
    }
  }

  return { fontSize: minFontSize, lineHeight: minFontSize * 1.45 };
}

function fitSingleLineText(
  text: string,
  width: number,
  {
    maxFontSize,
    minFontSize,
    weight,
  }: {
    maxFontSize: number;
    minFontSize: number;
    weight: number;
  },
): TextFit {
  const content = text.trim() || "Titulo";
  const availableWidth = Math.max(1, width);

  for (let fontSize = maxFontSize; fontSize >= minFontSize; fontSize -= 1) {
    const lineHeight = fontSize * 1.3;
    if (pretextHeight(content, availableWidth, fontSize, lineHeight, weight) <= lineHeight + 0.5) {
      return { fontSize, lineHeight };
    }
  }

  return { fontSize: minFontSize, lineHeight: minFontSize * 1.3 };
}

function createOmittedPreview(
  reason: Extract<SelectedCardPreview, { omitted: true }>["reason"],
  canvas?: HTMLCanvasElement | null,
): SelectedCardPreview {
  return {
    source: "rendered-preview",
    omitted: true,
    reason,
    width: canvas?.clientWidth,
    height: canvas?.clientHeight,
  };
}

export const CanvasCard = memo(function CanvasCard({
  document,
  node,
  isSelected,
  onDeleteDocument,
  onCreateEditedMediaArtifact,
  onCloseMediaEditor,
  onContextMenuOpenChange,
  onOpenMediaEditor,
  onRenameDocument,
  onRedoDocument,
  onRegisterPreviewCapture,
  onStatus,
  onUpdateBboxData,
  onUpdateDocumentPrompt,
  onToggleSelect,
  onUpdateFrame,
  isMediaEditorOpen,
  zoom,
}: CanvasCardProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const htmlRef = useRef<HTMLDivElement | null>(null);
  const noteTitleRef = useRef<HTMLInputElement | null>(null);
  const noteTextRef = useRef<HTMLDivElement | null>(null);
  const lastRequestedNoteHeightRef = useRef<number | null>(null);
  const contextMenuRef = useRef<HTMLDivElement | null>(null);
  const previewReadyRef = useRef(false);
  const dragStateRef = useRef<{
    pointerId: number;
    startClientX: number;
    startClientY: number;
    startX: number;
    startY: number;
    startHeight: number;
    startWidth: number;
    didDrag: boolean;
    mode: "drag" | "resize";
  } | null>(null);
  const suppressNextClickRef = useRef(false);
  const [useIframeFallback, setUseIframeFallback] = useState(() => shouldUsePlayableMediaFallback(document));
  const [isDragging, setIsDragging] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [isMetadataVisible, setIsMetadataVisible] = useState(false);
  const [contextMenuPosition, setContextMenuPosition] = useState<{ x: number; y: number } | null>(null);
  const accessibleTitle = getCardDisplayTitle(document);
  const editableTitle = getCardEditableTitle(document);
  const isNote = document.metadata?.kind === "note";
  const isBbox = document.metadata?.kind === "bbox";
  const isAudio = document.metadata?.kind === "audio";
  const isVideoDirectorPromptCard = document.metadata?.videoDirectorPromptOnly === true;
  const canShowMetadataToggle = isSelected && !isNote && !isBbox;
  const videoArtifactUrl = typeof document.metadata?.artifactUrl === "string" && document.metadata.kind === "video"
    ? document.metadata.artifactUrl
    : "";
  const editableAudioArtifactUrl = typeof document.metadata?.artifactUrl === "string" && document.metadata.kind === "audio"
    ? document.metadata.artifactUrl
    : "";
  const canEditVideo = Boolean(videoArtifactUrl);
  const canEditAudio = Boolean(editableAudioArtifactUrl);
  const canEditMedia = canEditVideo || canEditAudio;
  const audioPreviewSource = useMemo(() => getAudioPreviewSource(document), [document]);
  const usesNativeAudioPreview = Boolean(audioPreviewSource);
  const frame = node.frame;
  const frameHeight = getCardHeight(frame.width, document, frame);
  const metadataPanelHeight = isMetadataVisible
    ? isAudio
      ? Math.min(Math.max(frameHeight * 0.3, 84), Math.max(72, frameHeight * 0.38))
      : Math.min(Math.max(frameHeight * 0.22, 132), 204)
    : 0;
  const metadataTextMetrics = useMemo(() => {
    if (!isMetadataVisible) {
      return {
        prompt: { fontSize: 16, lineHeight: 23.2 },
        title: { fontSize: 18, lineHeight: 23.4 },
      };
    }

    const contentWidth = Math.max(1, frame.width - METADATA_HORIZONTAL_PADDING);
    const titleRowHeight = isAudio ? 42 : 48;
    const promptVerticalPadding = isAudio ? 12 : 20;
    const promptHeight = metadataPanelHeight - titleRowHeight - promptVerticalPadding;

    return {
      prompt: fitTextBlock(document.prompt, contentWidth, promptHeight, {
        maxFontSize: isAudio ? 15 : 16,
        minFontSize: 11,
        weight: 500,
      }),
      title: fitSingleLineText(editableTitle, contentWidth, {
        maxFontSize: isAudio ? 16 : 18,
        minFontSize: 12,
        weight: 700,
      }),
    };
  }, [document.prompt, editableTitle, frame.width, isAudio, isMetadataVisible, metadataPanelHeight]);
  const metadataPanelStyle = useMemo(
    () =>
      ({
        "--metadata-prompt-font-size": `${metadataTextMetrics.prompt.fontSize}px`,
        "--metadata-prompt-line-height": `${metadataTextMetrics.prompt.lineHeight}px`,
        "--metadata-title-font-size": `${metadataTextMetrics.title.fontSize}px`,
        "--metadata-title-line-height": `${metadataTextMetrics.title.lineHeight}px`,
        height: `${metadataPanelHeight}px`,
      }) as CSSProperties,
    [metadataPanelHeight, metadataTextMetrics],
  );

  useEffect(() => {
    if (isNote && isSelected && !document.prompt.trim()) {
      noteTitleRef.current?.focus();
      noteTitleRef.current?.select();
    }
  }, [document.id, document.prompt, isNote, isSelected]);

  useEffect(() => {
    setIsMetadataVisible(false);
  }, [document.id]);

  useEffect(() => {
    if (!isSelected) {
      setIsMetadataVisible(false);
    }
  }, [isSelected]);

  useEffect(() => {
    const textElement = noteTextRef.current;
    if (!isNote || !textElement || window.document.activeElement === textElement) return;
    if (textElement.textContent !== document.prompt) {
      textElement.textContent = document.prompt;
    }
  }, [document.prompt, isNote]);

  useEffect(() => {
    if (!isNote) return;

    const noteTextWidth = Math.max(1, frame.width - NOTE_TEXT_HORIZONTAL_PADDING);
    const textHeight = document.prompt.trim()
      ? pretextHeight(document.prompt, noteTextWidth, NOTE_TEXT_FONT_SIZE, NOTE_TEXT_LINE_HEIGHT, 500)
      : 0;
    const neededHeight = Math.ceil(NOTE_TITLE_HEIGHT + NOTE_TEXT_VERTICAL_PADDING + textHeight);
    if (neededHeight <= frameHeight + 1) {
      lastRequestedNoteHeightRef.current = null;
      return;
    }

    if (lastRequestedNoteHeightRef.current === neededHeight) return;
    lastRequestedNoteHeightRef.current = neededHeight;
    onUpdateFrame(node.id, {
      ...frame,
      height: neededHeight,
    });
  }, [document.prompt, frame, frameHeight, isNote, node.id, onUpdateFrame]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const htmlElement = htmlRef.current;
    const shouldUseIframe = shouldUsePlayableMediaFallback(document);

    if (shouldUseIframe) {
      previewReadyRef.current = false;
      setUseIframeFallback(true);
      return undefined;
    }

    if (!canvas) return undefined;
    const activeCanvas = canvas;
    let animationFrameId = 0;
    let retryCount = 0;

    function scheduleRender() {
      window.cancelAnimationFrame(animationFrameId);
      animationFrameId = window.requestAnimationFrame(render);
    }

    function render() {
      const drawStatus = drawHtmlInCanvas(activeCanvas, htmlElement);

      if (drawStatus === "drawn") {
        retryCount = 0;
        previewReadyRef.current = true;
        setUseIframeFallback(false);
        return;
      }

      if (drawStatus === "unsupported") {
        previewReadyRef.current = false;
        setUseIframeFallback(true);
        return;
      }

      previewReadyRef.current = false;
      retryCount += 1;
      if (retryCount <= 8) {
        scheduleRender();
      }
    }

    scheduleRender();
    activeCanvas.addEventListener("paint", scheduleRender);
    window.addEventListener("resize", scheduleRender);

    return () => {
      window.cancelAnimationFrame(animationFrameId);
      activeCanvas.removeEventListener("paint", scheduleRender);
      window.removeEventListener("resize", scheduleRender);
    };
  }, [document]);

  useEffect(() => {
    return onRegisterPreviewCapture(document.id, () => {
      const canvas = canvasRef.current;

      if (useIframeFallback) return createOmittedPreview("iframe-fallback", canvas);
      if (!canvas || canvas.width === 0 || canvas.height === 0 || !previewReadyRef.current) {
        return createOmittedPreview("capture-unavailable", canvas);
      }

      try {
        const dataUrl = canvas.toDataURL("image/png");
        if (!isDataUrlWithinLimit(dataUrl, SELECTED_CARD_PREVIEW_MAX_BYTES)) {
          return createOmittedPreview("size-limit", canvas);
        }

        return {
          source: "rendered-preview",
          mimeType: "image/png",
          dataUrl,
          width: canvas.clientWidth,
          height: canvas.clientHeight,
        };
      } catch {
        return createOmittedPreview("tainted-canvas", canvas);
      }
    });
  }, [document.id, onRegisterPreviewCapture, useIframeFallback]);

  useEffect(() => {
    if (!contextMenuPosition) return undefined;

    function closeContextMenu(event: globalThis.MouseEvent) {
      if (contextMenuRef.current?.contains(event.target as Node)) return;
      setContextMenuPosition(null);
    }

    function closeContextMenuWithKeyboard(event: globalThis.KeyboardEvent) {
      if (event.key === "Escape") {
        setContextMenuPosition(null);
      }
    }

    window.document.addEventListener("mousedown", closeContextMenu);
    window.document.addEventListener("contextmenu", closeContextMenu);
    window.document.addEventListener("keydown", closeContextMenuWithKeyboard);

    return () => {
      window.document.removeEventListener("mousedown", closeContextMenu);
      window.document.removeEventListener("contextmenu", closeContextMenu);
      window.document.removeEventListener("keydown", closeContextMenuWithKeyboard);
    };
  }, [contextMenuPosition]);

  useEffect(() => {
    onContextMenuOpenChange(node.id, Boolean(contextMenuPosition));
  }, [contextMenuPosition, node.id, onContextMenuOpenChange]);

  function handlePointerDown(event: PointerEvent<HTMLElement>) {
    if (event.button !== 0) return;

    event.currentTarget.setPointerCapture(event.pointerId);
    dragStateRef.current = {
      pointerId: event.pointerId,
      startClientX: event.clientX,
      startClientY: event.clientY,
      startX: frame.x,
      startY: frame.y,
      startHeight: frameHeight,
      startWidth: frame.width,
      didDrag: false,
      mode: "drag",
    };
    setIsDragging(true);
  }

  function handleResizePointerDown(event: PointerEvent<HTMLButtonElement>) {
    if (event.button !== 0) return;

    event.stopPropagation();
    event.currentTarget.setPointerCapture(event.pointerId);
    dragStateRef.current = {
      pointerId: event.pointerId,
      startClientX: event.clientX,
      startClientY: event.clientY,
      startX: frame.x,
      startY: frame.y,
      startHeight: frameHeight,
      startWidth: frame.width,
      didDrag: false,
      mode: "resize",
    };
    setIsDragging(true);
  }

  function handlePointerMove(event: PointerEvent<HTMLElement>) {
    const dragState = dragStateRef.current;
    if (!dragState || dragState.pointerId !== event.pointerId) return;

    const screenDeltaX = event.clientX - dragState.startClientX;
    const screenDeltaY = event.clientY - dragState.startClientY;
    const deltaX = screenDeltaX / zoom;
    const deltaY = screenDeltaY / zoom;
    const hasMoved = Math.abs(screenDeltaX) > 3 || Math.abs(screenDeltaY) > 3;
    dragState.didDrag ||= hasMoved;

    if (hasMoved && dragState.mode === "drag") {
      onUpdateFrame(node.id, {
        height: isNote || isBbox ? dragState.startHeight : undefined,
        width: dragState.startWidth,
        x: Math.max(0, dragState.startX + deltaX),
        y: Math.max(0, dragState.startY + deltaY),
      });
    }

    if (hasMoved && dragState.mode === "resize") {
      onUpdateFrame(node.id, {
        height: isNote || isBbox ? dragState.startHeight + deltaY : undefined,
        width: isNote || isBbox ? dragState.startWidth + deltaX : dragState.startWidth + Math.max(deltaX, deltaY * 0.75),
        x: dragState.startX,
        y: dragState.startY,
      });
    }
  }

  function handlePointerUp(event: PointerEvent<HTMLElement>) {
    const dragState = dragStateRef.current;
    if (!dragState || dragState.pointerId !== event.pointerId) return;

    dragStateRef.current = null;
    setIsDragging(false);
    event.currentTarget.releasePointerCapture(event.pointerId);

    suppressNextClickRef.current = dragState.didDrag;
  }

  function handlePointerCancel(event: PointerEvent<HTMLElement>) {
    const dragState = dragStateRef.current;
    if (!dragState || dragState.pointerId !== event.pointerId) return;

    dragStateRef.current = null;
    setIsDragging(false);
  }

  function handleClick(event: MouseEvent<HTMLElement>) {
    if (suppressNextClickRef.current) {
      suppressNextClickRef.current = false;
      event.preventDefault();
      return;
    }

    onToggleSelect(node.id);
  }

  function handlePreviewKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (event.key !== "Enter" && event.key !== " ") return;

    event.preventDefault();
    onToggleSelect(node.id);
  }

  function handleNoteFocus() {
    if (!isSelected) {
      onToggleSelect(node.id);
    }
  }

  function handleBboxDataChange(data: BboxCardData) {
    onUpdateBboxData(document.id, data);
  }

  function handleBboxDocumentSizeChange(width: number, height: number) {
    onUpdateFrame(node.id, {
      ...frame,
      height: frame.width * (height / width),
    });
  }

  function handleNoteTitleChange(event: ChangeEvent<HTMLInputElement>) {
    onRenameDocument(document.id, event.target.value);
  }

  function handleNoteTextInput(event: FormEvent<HTMLDivElement>) {
    onUpdateDocumentPrompt(document.id, event.currentTarget.textContent ?? "");
  }

  function handleCardPromptChange(event: ChangeEvent<HTMLTextAreaElement>) {
    onUpdateDocumentPrompt(document.id, event.target.value);
  }

  function handleMetadataToggle(event: MouseEvent<HTMLButtonElement>) {
    event.preventDefault();
    event.stopPropagation();
    setIsMetadataVisible((currentValue) => !currentValue);
  }

  async function handleCopyPrompt(event: MouseEvent<HTMLButtonElement>) {
    event.preventDefault();
    event.stopPropagation();

    try {
      await navigator.clipboard.writeText(document.prompt);
      onStatus("Prompt copied.");
    } catch (error) {
      onStatus(error instanceof Error ? error.message : "Could not copy prompt.");
    }
  }

  function handleNoteTextPaste(event: ClipboardEvent<HTMLDivElement>) {
    event.preventDefault();
    const text = event.clipboardData.getData("text/plain");
    window.document.execCommand("insertText", false, text);
  }

  function handleContextMenu(event: MouseEvent<HTMLElement>) {
    event.preventDefault();
    event.stopPropagation();

    const bounds = event.currentTarget.getBoundingClientRect();
    const menu = contextMenuRef.current;
    const menuWidth = menu?.offsetWidth || CONTEXT_MENU_WIDTH;
    const menuHeight = menu?.offsetHeight || CONTEXT_MENU_ESTIMATED_HEIGHT;
    const logicalWidth = bounds.width / zoom;
    const logicalHeight = bounds.height / zoom;
    const maxX = Math.max(CONTEXT_MENU_OFFSET, logicalWidth - menuWidth - CONTEXT_MENU_OFFSET);
    const maxY = Math.max(CONTEXT_MENU_OFFSET, logicalHeight - menuHeight - CONTEXT_MENU_OFFSET);
    const preferredX = (event.clientX - bounds.left) / zoom + CONTEXT_MENU_OFFSET;
    const preferredY = (event.clientY - bounds.top) / zoom + CONTEXT_MENU_OFFSET;

    setContextMenuPosition({
      x: Math.min(Math.max(CONTEXT_MENU_OFFSET, preferredX), maxX),
      y: Math.min(Math.max(CONTEXT_MENU_OFFSET, preferredY), maxY),
    });
  }

  function stopCardInteraction(event: MouseEvent<HTMLElement> | PointerEvent<HTMLElement>) {
    event.stopPropagation();
  }

  async function handleDownload() {
    setIsDownloading(true);

    try {
      await downloadCardDocument(document);
      setContextMenuPosition(null);
    } finally {
      setIsDownloading(false);
    }
  }

  function handleRedo() {
    onRedoDocument(document.id);
    setContextMenuPosition(null);
  }

  function handleEditMedia() {
    onOpenMediaEditor(node.id);
    setContextMenuPosition(null);
  }

  function handleDelete() {
    onDeleteDocument(document.id);
    setContextMenuPosition(null);
  }

  return (
    <article
      className={`canvas-card ${isSelected ? "selected" : ""} ${isDragging ? "dragging" : ""} ${isMediaEditorOpen ? "media-editor-open" : ""}`}
      onClick={handleClick}
      onContextMenu={handleContextMenu}
      onPointerCancel={handlePointerCancel}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      style={{
        transform: `translate3d(${frame.x}px, ${frame.y}px, 0)`,
        width: `${frame.width}px`,
      }}
    >
      {isNote ? (
        <div
          className="canvas-card-preview canvas-note-card"
          role="group"
          aria-label={accessibleTitle}
          style={{ height: `${frameHeight}px` }}
        >
          <input
            ref={noteTitleRef}
            className="canvas-note-title"
            value={editableTitle}
            placeholder="Title"
            aria-label={`${accessibleTitle} title`}
            onChange={handleNoteTitleChange}
            onClick={stopCardInteraction}
            onContextMenu={stopCardInteraction}
            onFocus={handleNoteFocus}
            onPointerDown={stopCardInteraction}
          />
          <span className="canvas-note-drag-handle" aria-hidden="true" />
          <div
            ref={noteTextRef}
            className="canvas-note-text"
            contentEditable
            data-placeholder="Write a note..."
            aria-label={`${accessibleTitle} text`}
            onClick={stopCardInteraction}
            onContextMenu={stopCardInteraction}
            onFocus={handleNoteFocus}
            onInput={handleNoteTextInput}
            onPaste={handleNoteTextPaste}
            onPointerDown={stopCardInteraction}
            role="textbox"
            aria-multiline="true"
            suppressContentEditableWarning
          />
        </div>
      ) : isBbox ? (
        <BboxCardEditor
          data={getBboxData(document)}
          height={frameHeight}
          onChange={handleBboxDataChange}
          onDocumentSizeChange={handleBboxDocumentSizeChange}
          onFocusCard={handleNoteFocus}
          title={accessibleTitle}
        />
      ) : usesNativeAudioPreview ? (
        <div
          className="canvas-card-preview has-playable-media canvas-card-audio-preview"
          role="button"
          aria-label={`Select ${accessibleTitle}`}
          aria-pressed={isSelected}
          tabIndex={0}
          onKeyDown={handlePreviewKeyDown}
          style={{ aspectRatio: getCardPreviewAspectRatioCss(document) }}
        >
          <div className="canvas-card-audio-preview-content">
            <audio
              src={audioPreviewSource ?? undefined}
              controls
              preload="metadata"
              onClick={stopCardInteraction}
              onContextMenu={stopCardInteraction}
              onPointerDown={stopCardInteraction}
            />
            <strong>{accessibleTitle}</strong>
          </div>
        </div>
      ) : (
        <button
          className={`canvas-card-preview ${shouldUsePlayableMediaFallback(document) ? "has-playable-media" : ""}`}
          type="button"
          aria-label={`Select ${accessibleTitle}`}
          aria-pressed={isSelected}
          style={{ aspectRatio: getCardPreviewAspectRatioCss(document) }}
        >
          {useIframeFallback && (
            <iframe
              title={accessibleTitle}
              srcDoc={createIframeSrcDoc(document)}
              sandbox="allow-same-origin"
              loading="lazy"
            />
          )}
          <canvas className={useIframeFallback ? "html-canvas-hidden" : undefined} ref={canvasRef} layoutsubtree="">
            <div
              className="html-canvas-source"
              ref={htmlRef}
              dangerouslySetInnerHTML={{ __html: document.html }}
            />
          </canvas>
          {isSelected && shouldUsePlayableMediaFallback(document) && (
            <span className="canvas-card-interaction-strip" aria-hidden="true" />
          )}
        </button>
      )}
      {canShowMetadataToggle && (
        <button
          className={`canvas-card-info-toggle ${isMetadataVisible ? "active" : ""}`}
          type="button"
          aria-label={`${isMetadataVisible ? "Hide" : "Show"} ${accessibleTitle} title and prompt`}
          aria-pressed={isMetadataVisible}
          title={`${isMetadataVisible ? "Hide" : "Show"} title and prompt`}
          onClick={handleMetadataToggle}
          onContextMenu={stopCardInteraction}
          onPointerDown={stopCardInteraction}
        >
          <Info size={15} aria-hidden="true" />
        </button>
      )}
      {isVideoDirectorPromptCard && (
        <button
          className="canvas-card-copy-prompt"
          type="button"
          aria-label={`Copy ${accessibleTitle} prompt`}
          title="Copy prompt"
          onClick={handleCopyPrompt}
          onContextMenu={stopCardInteraction}
          onPointerDown={stopCardInteraction}
        >
          <Copy size={15} aria-hidden="true" />
        </button>
      )}
      {isMetadataVisible && !isNote && !isBbox && (
        <aside
          className={`canvas-card-metadata-note ${isAudio ? "audio-card-metadata-note" : ""}`}
          aria-label={`${accessibleTitle} details`}
          style={metadataPanelStyle}
          onClick={stopCardInteraction}
          onContextMenu={stopCardInteraction}
          onPointerDown={stopCardInteraction}
        >
          <input
            className="canvas-card-metadata-title"
            value={editableTitle}
            onChange={handleNoteTitleChange}
            aria-label={`${accessibleTitle} title`}
            placeholder="Title"
          />
          <textarea
            className="canvas-card-metadata-prompt"
            value={document.prompt}
            onChange={handleCardPromptChange}
            aria-label={`${accessibleTitle} prompt`}
            placeholder="Prompt"
            rows={4}
          />
        </aside>
      )}
      {isSelected && (
        <>
          <span className="canvas-card-handle canvas-card-handle-top-left" aria-hidden="true" />
          <span className="canvas-card-handle canvas-card-handle-top-right" aria-hidden="true" />
          <span className="canvas-card-handle canvas-card-handle-bottom-left" aria-hidden="true" />
        </>
      )}
      <button
        className="canvas-card-resize"
        type="button"
        aria-label={`Resize ${accessibleTitle}`}
        onPointerDown={handleResizePointerDown}
      />
      {isMediaEditorOpen && canEditVideo && (
        <VideoTimelineEditor
          artifactUrl={videoArtifactUrl}
          title={accessibleTitle}
          onClose={onCloseMediaEditor}
          onCreateArtifact={(artifact, placementOffset) => onCreateEditedMediaArtifact(artifact, node.id, placementOffset)}
          onStatus={onStatus}
        />
      )}
      {isMediaEditorOpen && canEditAudio && (
        <AudioTimelineEditor
          artifactUrl={editableAudioArtifactUrl}
          title={accessibleTitle}
          onClose={onCloseMediaEditor}
          onCreateArtifact={(artifact) => onCreateEditedMediaArtifact(artifact, node.id)}
          onStatus={onStatus}
        />
      )}
      {contextMenuPosition && (
        <div
          className="context-menu canvas-card-context-menu"
          ref={contextMenuRef}
          data-popover
          role="menu"
          aria-label={`${accessibleTitle} actions`}
          style={{
            left: `${contextMenuPosition.x}px`,
            top: `${contextMenuPosition.y}px`,
          }}
          onClick={stopCardInteraction}
          onContextMenu={(event) => {
            event.preventDefault();
            event.stopPropagation();
          }}
          onPointerDown={stopCardInteraction}
        >
          {canEditMedia && (
            <button className="context-menu-item" type="button" role="menuitem" onClick={handleEditMedia}>
              <Scissors size={16} aria-hidden="true" />
              <span>Editar</span>
            </button>
          )}
          <button className="context-menu-item" type="button" role="menuitem" onClick={handleRedo}>
            <RotateCcw size={16} aria-hidden="true" />
            <span>Rehacer</span>
          </button>
          <button
            className="context-menu-item"
            type="button"
            role="menuitem"
            onClick={handleDownload}
            disabled={isDownloading}
          >
            <Download size={16} aria-hidden="true" />
            <span>{isDownloading ? "Descargando..." : "Descargar"}</span>
          </button>
          <button className="context-menu-item danger" type="button" role="menuitem" onClick={handleDelete}>
            <Trash2 size={16} aria-hidden="true" />
            <span>Eliminar</span>
          </button>
        </div>
      )}
    </article>
  );
});
