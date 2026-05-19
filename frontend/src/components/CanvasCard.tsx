import { useEffect, useRef, useState } from "react";
import type { GeneratedCard } from "../types";

type CanvasRenderingContext2DWithHtml = CanvasRenderingContext2D & {
  drawElementImage?: (element: Element, x: number, y: number, width: number, height: number) => void;
};

type HtmlCanvasDrawStatus = "drawn" | "pending" | "unsupported";

type CanvasCardProps = {
  card: GeneratedCard;
  isSelected: boolean;
  onToggleSelect: (cardId: string) => void;
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

export function CanvasCard({ card, isSelected, onToggleSelect }: CanvasCardProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const htmlRef = useRef<HTMLDivElement | null>(null);
  const [useIframeFallback, setUseIframeFallback] = useState(false);

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

  return (
    <article className={`canvas-card ${isSelected ? "selected" : ""}`}>
      <button
        className="canvas-card-preview"
        type="button"
        aria-label={`Select ${card.name}`}
        aria-pressed={isSelected}
        onClick={() => onToggleSelect(card.id)}
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
    </article>
  );
}
