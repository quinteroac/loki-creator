import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { MouseEvent, PointerEvent, WheelEvent } from "react";
import { Crosshair, StickyNote, ZoomIn, ZoomOut } from "lucide-react";
import {
  CARD_DEFAULT_WIDTH,
  CANVAS_PADDING,
  NOTE_DEFAULT_HEIGHT,
  NOTE_DEFAULT_WIDTH,
  clampCanvasNodeFrame,
  getCardHeight,
} from "../lib/cardDocuments";
import {
  getCanvasViewportBounds,
  getVirtualizedCanvasNodes,
  type CanvasViewportBounds,
} from "../lib/canvasVirtualization";
import { CanvasCard } from "./CanvasCard";
import type { BboxCardData } from "../lib/bboxCards";
import type { CardDocument, CanvasNode, CanvasNodeFrame, EditedMediaArtifact, SelectedCardPreview } from "../types";

type CanvasStageProps = {
  documentsById: Record<string, CardDocument>;
  nodes: CanvasNode[];
  selectedIds: string[];
  onViewportAnchorChange: (anchor: CanvasFocalPoint | null) => void;
  onCreateBbox: (frame: CanvasNodeFrame) => void;
  onCreateNote: (frame: CanvasNodeFrame) => void;
  onCreateEditedMediaArtifact: (artifact: EditedMediaArtifact, sourceNodeId: string, placementOffset?: number) => void;
  onDeleteDocument: (cardDocumentId: string) => void;
  onRenameDocument: (cardDocumentId: string, title: string) => void;
  onUpdateDocumentPrompt: (cardDocumentId: string, prompt: string) => void;
  onRedoDocument: (cardDocumentId: string) => void;
  onRegisterPreviewCapture: (cardDocumentId: string, capturePreview: () => SelectedCardPreview) => () => void;
  onStatus: (message: string) => void;
  onToggleNode: (nodeId: string) => void;
  onUpdateBboxData: (cardDocumentId: string, data: BboxCardData) => void;
  onUpdateNodeFrame: (nodeId: string, frame: CanvasNodeFrame) => void;
};

const DEFAULT_CANVAS_ZOOM = 1.3;
const CANVAS_ZOOM_STEP = 0.1;
const CANVAS_ZOOM_MIN = 0.3;
const CANVAS_ZOOM_MAX = 4;
const CANVAS_CONTEXT_MENU_WIDTH = 184;
const CANVAS_CONTEXT_MENU_HEIGHT = 104;
const CANVAS_CONTEXT_MENU_OFFSET = 8;
const CANVAS_VIRTUALIZATION_OVERSCAN = 480;
const CANVAS_LEFT_MOUSE_BUTTON = 0;
const CANVAS_MIDDLE_MOUSE_BUTTON = 1;
const CANVAS_WHEEL_INTERACTIVE_SELECTOR = [
  ".canvas-zoom-controls",
  ".context-menu",
  ".popover",
  ".audio-timeline-editor",
  ".video-timeline-editor",
  ".canvas-card-metadata-note",
  "input",
  "select",
  "textarea",
  "[contenteditable='true']",
].join(",");
const CANVAS_PAN_BLOCKING_SELECTOR = [
  ".canvas-zoom-controls",
  ".context-menu",
  ".popover",
  ".audio-timeline-editor",
  ".video-timeline-editor",
  ".canvas-card-metadata-note",
  "input",
  "select",
  "textarea",
  "[contenteditable='true']",
].join(",");
const CANVAS_LEFT_PAN_BLOCKING_SELECTOR = [".canvas-card", "button", CANVAS_PAN_BLOCKING_SELECTOR].join(",");
const CANVAS_CONTEXT_MENU_BLOCKING_SELECTOR = [
  ".canvas-card",
  ".canvas-zoom-controls",
  ".context-menu",
  ".popover",
  ".audio-timeline-editor",
  ".video-timeline-editor",
  ".canvas-card-metadata-note",
  "input",
  "select",
  "textarea",
  "[contenteditable='true']",
].join(",");

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

function shouldIgnoreCanvasContextMenu(target: EventTarget | null) {
  return target instanceof Element && Boolean(target.closest(CANVAS_CONTEXT_MENU_BLOCKING_SELECTOR));
}

type CanvasFocalPoint = {
  x: number;
  y: number;
};

type CanvasViewport = {
  zoom: number;
  pan: CanvasFocalPoint;
};

type CanvasSize = {
  width: number;
  height: number;
};

export const CanvasStage = memo(function CanvasStage({
  documentsById,
  nodes,
  selectedIds,
  onViewportAnchorChange,
  onCreateBbox,
  onCreateNote,
  onCreateEditedMediaArtifact,
  onDeleteDocument,
  onRenameDocument,
  onUpdateDocumentPrompt,
  onRedoDocument,
  onRegisterPreviewCapture,
  onStatus,
  onToggleNode,
  onUpdateBboxData,
  onUpdateNodeFrame,
}: CanvasStageProps) {
  const canvasRef = useRef<HTMLDivElement | null>(null);
  const cardLayerRef = useRef<HTMLDivElement | null>(null);
  const viewportRef = useRef<CanvasViewport>({
    zoom: DEFAULT_CANVAS_ZOOM,
    pan: { x: 0, y: 0 },
  });
  const panAnimationFrameRef = useRef(0);
  const pendingPanRef = useRef<CanvasFocalPoint | null>(null);
  const panStateRef = useRef<{
    pointerId: number;
    startClientX: number;
    startClientY: number;
    startX: number;
    startY: number;
  } | null>(null);
  const [viewport, setViewport] = useState<CanvasViewport>({
    zoom: DEFAULT_CANVAS_ZOOM,
    pan: { x: 0, y: 0 },
  });
  const [canvasSize, setCanvasSize] = useState<CanvasSize>({ width: 0, height: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [contextMenu, setContextMenu] = useState<{
    logicalX: number;
    logicalY: number;
    screenX: number;
    screenY: number;
  } | null>(null);
  const [editingNodeId, setEditingNodeId] = useState<string | null>(null);
  const [openCardMenuNodeIds, setOpenCardMenuNodeIds] = useState<Set<string>>(new Set());
  const selectedIdSet = useMemo(() => new Set(selectedIds), [selectedIds]);
  const nodesById = useMemo(() => new Map(nodes.map((node) => [node.id, node])), [nodes]);
  const { pan, zoom } = viewport;
  const zoomPercentage = Math.round(zoom * 100);
  const forcedNodeIds = useMemo(() => {
    const ids = new Set(openCardMenuNodeIds);
    if (editingNodeId) {
      ids.add(editingNodeId);
    }
    return ids;
  }, [editingNodeId, openCardMenuNodeIds]);
  const viewportBounds: CanvasViewportBounds = useMemo(
    () =>
      getCanvasViewportBounds({
        height: canvasSize.height,
        overscan: CANVAS_VIRTUALIZATION_OVERSCAN,
        pan,
        width: canvasSize.width,
        zoom,
      }),
    [canvasSize.height, canvasSize.width, pan, zoom],
  );
  const virtualizedNodes = useMemo(
    () =>
      canvasSize.width > 0 && canvasSize.height > 0
        ? getVirtualizedCanvasNodes({
          bounds: viewportBounds,
          documentsById,
          forcedNodeIds,
          nodes,
          selectedCardIds: selectedIdSet,
        })
        : nodes.map((node) => ({ node, reason: "visible" as const })),
    [canvasSize.height, canvasSize.width, documentsById, forcedNodeIds, nodes, selectedIdSet, viewportBounds],
  );

  useEffect(() => {
    viewportRef.current = viewport;
  }, [viewport]);

  useEffect(() => {
    if (canvasSize.width <= 0 || canvasSize.height <= 0) {
      onViewportAnchorChange(null);
      return;
    }

    onViewportAnchorChange({
      x: viewportBounds.left + (viewportBounds.right - viewportBounds.left) / 2,
      y: viewportBounds.top + (viewportBounds.bottom - viewportBounds.top) / 2,
    });
  }, [canvasSize.height, canvasSize.width, onViewportAnchorChange, viewportBounds]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;

    function updateCanvasSize() {
      setCanvasSize({
        width: canvas?.clientWidth ?? 0,
        height: canvas?.clientHeight ?? 0,
      });
    }

    updateCanvasSize();
    const resizeObserver = new ResizeObserver(updateCanvasSize);
    resizeObserver.observe(canvas);

    return () => resizeObserver.disconnect();
  }, []);

  useEffect(() => {
    return () => {
      window.cancelAnimationFrame(panAnimationFrameRef.current);
    };
  }, []);

  useEffect(() => {
    if (!contextMenu) return undefined;

    function closeContextMenu(event: globalThis.MouseEvent) {
      if (event.target instanceof Element && event.target.closest(".canvas-context-menu")) return;
      setContextMenu(null);
    }

    function closeContextMenuWithKeyboard(event: globalThis.KeyboardEvent) {
      if (event.key === "Escape") {
        setContextMenu(null);
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
  }, [contextMenu]);

  useEffect(() => {
    if (!editingNodeId || nodes.some((node) => node.id === editingNodeId)) return;
    setEditingNodeId(null);
  }, [editingNodeId, nodes]);

  const updateNodeFrame = useCallback((nodeId: string, frame: CanvasNodeFrame) => {
    const layer = cardLayerRef.current;
    const node = nodesById.get(nodeId);
    const document = node ? documentsById[node.cardDocumentId] : undefined;
    const currentViewport = viewportRef.current;
    const panOverflowX = Math.max(0, -currentViewport.pan.x);
    const panOverflowY = Math.max(0, -currentViewport.pan.y);
    const canvasWidth = layer
      ? (layer.clientWidth + panOverflowX) / currentViewport.zoom
      : CARD_DEFAULT_WIDTH + CANVAS_PADDING * 2;
    const canvasHeight = layer
      ? (layer.clientHeight + panOverflowY) / currentViewport.zoom
      : getCardHeight(CARD_DEFAULT_WIDTH, document, frame) + CANVAS_PADDING * 2;

    onUpdateNodeFrame(nodeId, clampCanvasNodeFrame(frame, canvasWidth, canvasHeight, document));
  }, [documentsById, nodesById, onUpdateNodeFrame]);

  const changeZoom = useCallback((delta: number, focalPoint?: CanvasFocalPoint) => {
    setViewport((currentViewport) => {
      const nextZoom = clampCanvasZoom(Number((currentViewport.zoom + delta).toFixed(2)));
      if (!focalPoint || nextZoom === currentViewport.zoom) {
        return { ...currentViewport, zoom: nextZoom };
      }

      const logicalX = (focalPoint.x - currentViewport.pan.x) / currentViewport.zoom;
      const logicalY = (focalPoint.y - currentViewport.pan.y) / currentViewport.zoom;

      return {
        zoom: nextZoom,
        pan: {
          x: focalPoint.x - logicalX * nextZoom,
          y: focalPoint.y - logicalY * nextZoom,
        },
      };
    });
  }, []);

  const zoomIn = useCallback(() => {
    changeZoom(CANVAS_ZOOM_STEP);
  }, [changeZoom]);

  const zoomOut = useCallback(() => {
    changeZoom(-CANVAS_ZOOM_STEP);
  }, [changeZoom]);

  function handleCanvasWheel(event: WheelEvent<HTMLDivElement>) {
    if (event.deltaY === 0 || shouldIgnoreCanvasWheel(event.target)) return;

    event.preventDefault();
    const bounds = event.currentTarget.getBoundingClientRect();
    changeZoom(event.deltaY < 0 ? CANVAS_ZOOM_STEP : -CANVAS_ZOOM_STEP, {
      x: event.clientX - bounds.left,
      y: event.clientY - bounds.top,
    });
  }

  function handleCanvasAuxClick(event: MouseEvent<HTMLDivElement>) {
    if (event.button === CANVAS_MIDDLE_MOUSE_BUTTON) {
      event.preventDefault();
    }
  }

  function handleCanvasContextMenu(event: MouseEvent<HTMLDivElement>) {
    if (shouldIgnoreCanvasContextMenu(event.target)) return;

    event.preventDefault();
    event.stopPropagation();
    const bounds = event.currentTarget.getBoundingClientRect();
    const localX = event.clientX - bounds.left;
    const localY = event.clientY - bounds.top;
    const logicalX = Math.max(0, (localX - pan.x) / zoom);
    const logicalY = Math.max(0, (localY - pan.y) / zoom);
    const maxScreenX = Math.max(CANVAS_CONTEXT_MENU_OFFSET, bounds.width - CANVAS_CONTEXT_MENU_WIDTH - CANVAS_CONTEXT_MENU_OFFSET);
    const maxScreenY = Math.max(CANVAS_CONTEXT_MENU_OFFSET, bounds.height - CANVAS_CONTEXT_MENU_HEIGHT - CANVAS_CONTEXT_MENU_OFFSET);

    setContextMenu({
      logicalX,
      logicalY,
      screenX: Math.min(Math.max(CANVAS_CONTEXT_MENU_OFFSET, localX), maxScreenX),
      screenY: Math.min(Math.max(CANVAS_CONTEXT_MENU_OFFSET, localY), maxScreenY),
    });
  }

  function handleCanvasPointerDown(event: PointerEvent<HTMLDivElement>) {
    if (contextMenu && event.button === CANVAS_LEFT_MOUSE_BUTTON && !shouldIgnoreCanvasContextMenu(event.target)) {
      event.preventDefault();
      setContextMenu(null);
      return;
    }

    const canPanWithButton =
      event.button === CANVAS_LEFT_MOUSE_BUTTON || event.button === CANVAS_MIDDLE_MOUSE_BUTTON;
    if (!canPanWithButton || shouldIgnoreCanvasPan(event.target, event.button)) return;

    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    const currentViewport = viewportRef.current;
    panStateRef.current = {
      pointerId: event.pointerId,
      startClientX: event.clientX,
      startClientY: event.clientY,
      startX: currentViewport.pan.x,
      startY: currentViewport.pan.y,
    };
    setIsPanning(true);
  }

  function schedulePan(nextPan: CanvasFocalPoint) {
    pendingPanRef.current = nextPan;
    if (panAnimationFrameRef.current) return;

    panAnimationFrameRef.current = window.requestAnimationFrame(() => {
      panAnimationFrameRef.current = 0;
      const pendingPan = pendingPanRef.current;
      if (!pendingPan) return;

      pendingPanRef.current = null;
      setViewport((currentViewport) => ({
        ...currentViewport,
        pan: pendingPan,
      }));
    });
  }

  function handleCanvasPointerMove(event: PointerEvent<HTMLDivElement>) {
    const panState = panStateRef.current;
    if (!panState || panState.pointerId !== event.pointerId) return;

    schedulePan({
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

  const handleCardContextMenuOpenChange = useCallback((nodeId: string, isOpen: boolean) => {
    setOpenCardMenuNodeIds((currentIds) => {
      if (isOpen && currentIds.has(nodeId)) return currentIds;
      if (!isOpen && !currentIds.has(nodeId)) return currentIds;

      const nextIds = new Set(currentIds);
      if (isOpen) {
        nextIds.add(nodeId);
      } else {
        nextIds.delete(nodeId);
      }
      return nextIds;
    });
  }, []);

  const closeMediaEditor = useCallback(() => setEditingNodeId(null), []);
  const openMediaEditor = useCallback((nodeId: string) => setEditingNodeId(nodeId), []);

  function createNoteFromContextMenu() {
    if (!contextMenu) return;

    onCreateNote({
      height: NOTE_DEFAULT_HEIGHT,
      width: NOTE_DEFAULT_WIDTH,
      x: contextMenu.logicalX,
      y: contextMenu.logicalY,
    });
    setContextMenu(null);
  }

  function createBboxFromContextMenu() {
    if (!contextMenu) return;

    onCreateBbox({
      height: NOTE_DEFAULT_HEIGHT,
      width: NOTE_DEFAULT_WIDTH,
      x: contextMenu.logicalX,
      y: contextMenu.logicalY,
    });
    setContextMenu(null);
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
        onContextMenu={handleCanvasContextMenu}
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
          {virtualizedNodes.map(({ node }) => {
            const document = documentsById[node.cardDocumentId];
            if (!document) return null;

            return (
              <CanvasCard
                document={document}
                node={node}
                isSelected={selectedIdSet.has(node.cardDocumentId)}
                isMediaEditorOpen={editingNodeId === node.id}
                key={node.id}
                onCloseMediaEditor={closeMediaEditor}
                onContextMenuOpenChange={handleCardContextMenuOpenChange}
                onCreateEditedMediaArtifact={onCreateEditedMediaArtifact}
                onDeleteDocument={onDeleteDocument}
                onOpenMediaEditor={openMediaEditor}
                onRenameDocument={onRenameDocument}
                onRedoDocument={onRedoDocument}
                onRegisterPreviewCapture={onRegisterPreviewCapture}
                onStatus={onStatus}
                onUpdateDocumentPrompt={onUpdateDocumentPrompt}
                onUpdateBboxData={onUpdateBboxData}
                onUpdateFrame={updateNodeFrame}
                onToggleSelect={onToggleNode}
                zoom={zoom}
              />
            );
          })}
        </div>
        {contextMenu && (
          <div
            className="context-menu canvas-context-menu"
            data-popover
            role="menu"
            aria-label="Canvas actions"
            style={{
              left: `${contextMenu.screenX}px`,
              top: `${contextMenu.screenY}px`,
            }}
            onClick={(event) => event.stopPropagation()}
            onContextMenu={(event) => {
              event.preventDefault();
              event.stopPropagation();
            }}
          >
            <button className="context-menu-item" type="button" role="menuitem" onClick={createNoteFromContextMenu}>
              <StickyNote size={16} aria-hidden="true" />
              <span>Create note</span>
            </button>
            <button className="context-menu-item" type="button" role="menuitem" onClick={createBboxFromContextMenu}>
              <Crosshair size={16} aria-hidden="true" />
              <span>Create bbox</span>
            </button>
          </div>
        )}
      </div>
    </section>
  );
});
