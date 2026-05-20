import { useEffect, useRef, useState } from "react";
import type { MouseEvent, PointerEvent } from "react";
import type { GeneratedCard } from "../types";

type CanvasRenderingContext2DWithHtml = CanvasRenderingContext2D & {
  drawElementImage?: (element: Element, x: number, y: number, width: number, height: number) => void;
};

type HtmlCanvasDrawStatus = "drawn" | "pending" | "unsupported";

type CanvasCardProps = {
  card: GeneratedCard;
  frame: CanvasCardFrame;
  isSelected: boolean;
  onUpdateFrame: (cardId: string, frame: CanvasCardFrame) => void;
  onToggleSelect: (cardId: string) => void;
};

export type CanvasCardFrame = {
  width: number;
  x: number;
  y: number;
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

function createIframeSrcDoc(cardHtml: string): string {
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

export function CanvasCard({ card, frame, isSelected, onToggleSelect, onUpdateFrame }: CanvasCardProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const htmlRef = useRef<HTMLDivElement | null>(null);
  const dragStateRef = useRef<{
    pointerId: number;
    startClientX: number;
    startClientY: number;
    startX: number;
    startY: number;
    startWidth: number;
    didDrag: boolean;
    mode: "drag" | "resize";
  } | null>(null);
  const suppressNextClickRef = useRef(false);
  const [useIframeFallback, setUseIframeFallback] = useState(false);
  const [isDragging, setIsDragging] = useState(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    const htmlElement = htmlRef.current;

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
        setUseIframeFallback(false);
        return;
      }

      if (drawStatus === "unsupported") {
        setUseIframeFallback(true);
        return;
      }

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
  }, [card.html]);

  function handlePointerDown(event: PointerEvent<HTMLElement>) {
    if (event.button !== 0) return;

    event.currentTarget.setPointerCapture(event.pointerId);
    dragStateRef.current = {
      pointerId: event.pointerId,
      startClientX: event.clientX,
      startClientY: event.clientY,
      startX: frame.x,
      startY: frame.y,
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
      startWidth: frame.width,
      didDrag: false,
      mode: "resize",
    };
    setIsDragging(true);
  }

  function handlePointerMove(event: PointerEvent<HTMLElement>) {
    const dragState = dragStateRef.current;
    if (!dragState || dragState.pointerId !== event.pointerId) return;

    const deltaX = event.clientX - dragState.startClientX;
    const deltaY = event.clientY - dragState.startClientY;
    const hasMoved = Math.abs(deltaX) > 3 || Math.abs(deltaY) > 3;
    dragState.didDrag ||= hasMoved;

    if (hasMoved && dragState.mode === "drag") {
      onUpdateFrame(card.id, {
        width: dragState.startWidth,
        x: Math.max(0, dragState.startX + deltaX),
        y: Math.max(0, dragState.startY + deltaY),
      });
    }

    if (hasMoved && dragState.mode === "resize") {
      onUpdateFrame(card.id, {
        width: dragState.startWidth + Math.max(deltaX, deltaY * 0.75),
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

    onToggleSelect(card.id);
  }

  return (
    <article
      className={`canvas-card ${isSelected ? "selected" : ""} ${isDragging ? "dragging" : ""}`}
      onClick={handleClick}
      onPointerCancel={handlePointerCancel}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      style={{
        transform: `translate3d(${frame.x}px, ${frame.y}px, 0)`,
        width: `${frame.width}px`,
      }}
    >
      <button
        className="canvas-card-preview"
        type="button"
        aria-label={`Select ${card.name}`}
        aria-pressed={isSelected}
      >
        {useIframeFallback && <iframe title={card.name} srcDoc={createIframeSrcDoc(card.html)} sandbox="" loading="lazy" />}
        <canvas className={useIframeFallback ? "html-canvas-hidden" : undefined} ref={canvasRef} layoutsubtree="">
          <div
            className="html-canvas-source"
            ref={htmlRef}
            dangerouslySetInnerHTML={{ __html: card.html }}
          />
        </canvas>
      </button>
      <p>{card.prompt}</p>
      <button
        className="canvas-card-resize"
        type="button"
        aria-label={`Resize ${card.name}`}
        onPointerDown={handleResizePointerDown}
      />
    </article>
  );
}
