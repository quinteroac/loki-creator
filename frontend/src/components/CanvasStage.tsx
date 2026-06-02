import { useRef, useState } from "react";
import type { CSSProperties, ChangeEvent, MouseEvent, PointerEvent, WheelEvent } from "react";
import { ZoomIn, ZoomOut } from "lucide-react";
import {
  CARD_DEFAULT_WIDTH,
  CANVAS_PADDING,
  clampCanvasNodeFrame,
  getCardEditableTitle,
  getCardDisplayTitle,
  getCardHeight,
} from "../lib/cardDocuments";
import { CanvasCard } from "./CanvasCard";
import type { CardDocument, CanvasNode, CanvasNodeFrame, SelectedCardPreview } from "../types";

type CanvasStageProps = {
  documentsById: Record<string, CardDocument>;
  nodes: CanvasNode[];
  selectedIds: string[];
  onDeleteDocument: (cardDocumentId: string) => void;
  onRenameDocument: (cardDocumentId: string, title: string) => void;
  onUpdateDocumentPrompt: (cardDocumentId: string, prompt: string) => void;
  onRedoDocument: (cardDocumentId: string) => void;
  onRegisterPreviewCapture: (cardDocumentId: string, capturePreview: () => SelectedCardPreview) => () => void;
  onToggleNode: (nodeId: string) => void;
  onUpdateNodeFrame: (nodeId: string, frame: CanvasNodeFrame) => void;
};

const DEFAULT_CANVAS_ZOOM = 1.3;
const CANVAS_ZOOM_STEP = 0.1;
const CANVAS_ZOOM_MIN = 0.3;
const CANVAS_ZOOM_MAX = 2;
const CANVAS_LEFT_MOUSE_BUTTON = 0;
const CANVAS_MIDDLE_MOUSE_BUTTON = 1;
const CANVAS_WHEEL_INTERACTIVE_SELECTOR = [
  ".canvas-zoom-controls",
  ".popover",
  ".selected-card-editor",
  "input",
  "select",
  "textarea",
  "[contenteditable='true']",
].join(",");
const CANVAS_PAN_BLOCKING_SELECTOR = [
  ".canvas-zoom-controls",
  ".popover",
  ".selected-card-editor",
  "input",
  "select",
  "textarea",
  "[contenteditable='true']",
].join(",");
const CANVAS_LEFT_PAN_BLOCKING_SELECTOR = [".canvas-card", "button", CANVAS_PAN_BLOCKING_SELECTOR].join(",");

function clampCanvasZoom(value: number) {
  return Math.min(Math.max(value, CANVAS_ZOOM_MIN), CANVAS_ZOOM_MAX);
}

function shouldIgnoreCanvasWheel(target: EventTarget | null) {
  return target instanceof Element && Boolean(target.closest(CANVAS_WHEEL_INTERACTIVE_SELECTOR));
}

function shouldIgnoreCanvasPan(target: EventTarget | null, button: number) {
  if (!(target instanceof Element)) return false;

  const blockingSelector =
    button === CANVAS_MIDDLE_MOUSE_BUTTON ? CANVAS_PAN_BLOCKING_SELECTOR : CANVAS_LEFT_PAN_BLOCKING_SELECTOR;

  return Boolean(target.closest(blockingSelector));
}

export function CanvasStage({
  documentsById,
  nodes,
  selectedIds,
  onDeleteDocument,
  onRenameDocument,
  onUpdateDocumentPrompt,
  onRedoDocument,
  onRegisterPreviewCapture,
  onToggleNode,
  onUpdateNodeFrame,
}: CanvasStageProps) {
  const canvasRef = useRef<HTMLDivElement | null>(null);
  const cardLayerRef = useRef<HTMLDivElement | null>(null);
  const panStateRef = useRef<{
    pointerId: number;
    startClientX: number;
    startClientY: number;
    startX: number;
    startY: number;
  } | null>(null);
  const [zoom, setZoom] = useState(DEFAULT_CANVAS_ZOOM);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const selectedIdSet = new Set(selectedIds);
  const zoomPercentage = Math.round(zoom * 100);
  const selectedEditorItems = nodes
    .filter((node) => selectedIdSet.has(node.cardDocumentId))
    .map((node) => {
      const document = documentsById[node.cardDocumentId];
      if (!document) return null;

      return {
        document,
        node,
        style: {
          "--selected-card-editor-left": `${pan.x + node.frame.x * zoom}px`,
          "--selected-card-editor-top": `${pan.y + (node.frame.y + getCardHeight(node.frame.width, document)) * zoom + 12}px`,
          "--selected-card-editor-width": `${Math.min(Math.max(node.frame.width * zoom, 360), 720)}px`,
        } as CSSProperties,
      };
    })
    .filter((item): item is { document: CardDocument; node: CanvasNode; style: CSSProperties } => item !== null);

  function updateNodeFrame(nodeId: string, frame: CanvasNodeFrame) {
    const layer = cardLayerRef.current;
    const node = nodes.find((candidate) => candidate.id === nodeId);
    const document = node ? documentsById[node.cardDocumentId] : undefined;
    const panOverflowX = Math.max(0, -pan.x);
    const panOverflowY = Math.max(0, -pan.y);
    const canvasWidth = layer ? (layer.clientWidth + panOverflowX) / zoom : CARD_DEFAULT_WIDTH + CANVAS_PADDING * 2;
    const canvasHeight = layer
      ? (layer.clientHeight + panOverflowY) / zoom
      : getCardHeight(CARD_DEFAULT_WIDTH, document) + CANVAS_PADDING * 2;

    onUpdateNodeFrame(nodeId, clampCanvasNodeFrame(frame, canvasWidth, canvasHeight, document));
  }

  function changeZoom(delta: number) {
    setZoom((currentZoom) => clampCanvasZoom(Number((currentZoom + delta).toFixed(2))));
  }

  function zoomIn() {
    changeZoom(CANVAS_ZOOM_STEP);
  }

  function zoomOut() {
    changeZoom(-CANVAS_ZOOM_STEP);
  }

  function handleCanvasWheel(event: WheelEvent<HTMLDivElement>) {
    if (event.deltaY === 0 || shouldIgnoreCanvasWheel(event.target)) return;

    event.preventDefault();
    changeZoom(event.deltaY < 0 ? CANVAS_ZOOM_STEP : -CANVAS_ZOOM_STEP);
  }

  function handleCanvasAuxClick(event: MouseEvent<HTMLDivElement>) {
    if (event.button === CANVAS_MIDDLE_MOUSE_BUTTON) {
      event.preventDefault();
    }
  }

  function handleCanvasPointerDown(event: PointerEvent<HTMLDivElement>) {
    const canPanWithButton =
      event.button === CANVAS_LEFT_MOUSE_BUTTON || event.button === CANVAS_MIDDLE_MOUSE_BUTTON;
    if (!canPanWithButton || shouldIgnoreCanvasPan(event.target, event.button)) return;

    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    panStateRef.current = {
      pointerId: event.pointerId,
      startClientX: event.clientX,
      startClientY: event.clientY,
      startX: pan.x,
      startY: pan.y,
    };
    setIsPanning(true);
  }

  function handleCanvasPointerMove(event: PointerEvent<HTMLDivElement>) {
    const panState = panStateRef.current;
    if (!panState || panState.pointerId !== event.pointerId) return;

    setPan({
      x: panState.startX + event.clientX - panState.startClientX,
      y: panState.startY + event.clientY - panState.startClientY,
    });
  }

  function stopCanvasPan(event: PointerEvent<HTMLDivElement>) {
    const panState = panStateRef.current;
    if (!panState || panState.pointerId !== event.pointerId) return;

    panStateRef.current = null;
    setIsPanning(false);

    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }

  function handleSelectedNameChange(cardDocumentId: string, event: ChangeEvent<HTMLInputElement>) {
    onRenameDocument(cardDocumentId, event.target.value);
  }

  function handleSelectedPromptChange(cardDocumentId: string, event: ChangeEvent<HTMLTextAreaElement>) {
    onUpdateDocumentPrompt(cardDocumentId, event.target.value);
  }

  return (
    <section className="canvas-shell" aria-label="Creative canvas">
      <div
        className={`canvas ${isPanning ? "panning" : ""}`}
        id="creativeCanvas"
        ref={canvasRef}
        tabIndex={0}
        onAuxClick={handleCanvasAuxClick}
        onPointerCancel={stopCanvasPan}
        onPointerDown={handleCanvasPointerDown}
        onPointerMove={handleCanvasPointerMove}
        onPointerUp={stopCanvasPan}
        onWheel={handleCanvasWheel}
      >
        <div
          className="canvas-zoom-controls"
          aria-label="Canvas zoom controls"
        >
          <button
            className="canvas-zoom-button"
            type="button"
            aria-label="Zoom out"
            onClick={zoomOut}
            disabled={zoom <= CANVAS_ZOOM_MIN}
          >
            <ZoomOut size={16} aria-hidden="true" />
          </button>
          <span className="canvas-zoom-value" aria-live="polite">{zoomPercentage}%</span>
          <button
            className="canvas-zoom-button"
            type="button"
            aria-label="Zoom in"
            onClick={zoomIn}
            disabled={zoom >= CANVAS_ZOOM_MAX}
          >
            <ZoomIn size={16} aria-hidden="true" />
          </button>
        </div>
        <div
          className="canvas-card-layer"
          ref={cardLayerRef}
          style={{ transform: `translate3d(${pan.x}px, ${pan.y}px, 0) scale(${zoom})` }}
        >
          {nodes.map((node) => {
            const document = documentsById[node.cardDocumentId];
            if (!document) return null;

            return (
              <CanvasCard
                document={document}
                node={node}
                isSelected={selectedIdSet.has(node.cardDocumentId)}
                key={node.id}
                onDeleteDocument={onDeleteDocument}
                onRedoDocument={onRedoDocument}
                onRegisterPreviewCapture={onRegisterPreviewCapture}
                onUpdateFrame={updateNodeFrame}
                onToggleSelect={onToggleNode}
                zoom={zoom}
              />
            );
          })}
        </div>
        {selectedEditorItems.map(({ document, node, style }) => (
          <aside className="selected-card-editor" style={style} aria-label="Selected card details" key={node.id}>
            <label>
              <span>Name</span>
              <input
                value={getCardEditableTitle(document)}
                onChange={(event) => handleSelectedNameChange(document.id, event)}
                aria-label={`${getCardDisplayTitle(document)} name`}
              />
            </label>
            <label>
              <span>Prompt</span>
              <textarea
                value={document.prompt}
                onChange={(event) => handleSelectedPromptChange(document.id, event)}
                aria-label={`${getCardDisplayTitle(document)} prompt`}
                rows={2}
              />
            </label>
          </aside>
        ))}
      </div>
    </section>
  );
}
