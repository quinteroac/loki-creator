import { useEffect, useRef, useState } from "react";
import type { GeneratedCard } from "../types";

type CanvasRenderingContext2DWithHtml = CanvasRenderingContext2D & {
  drawElementImage?: (element: Element, x: number, y: number, width: number, height: number) => void;
};

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

function drawHtmlInCanvas(canvas: HTMLCanvasElement, htmlElement: HTMLDivElement | null): boolean {
  const context = canvas.getContext("2d") as CanvasRenderingContext2DWithHtml | null;

  if (!supportsHtmlInCanvas(context) || !htmlElement) return false;
  if (!context?.drawElementImage) return false;

  const { height, pixelRatio, width } = resizeCanvas(canvas);
  context.reset?.();
  context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
  context.drawElementImage(htmlElement, 0, 0, width, height);

  return true;
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

    function render() {
      const didDrawHtml = drawHtmlInCanvas(activeCanvas, htmlElement);
      setUseIframeFallback(!didDrawHtml);
    }

    render();
    activeCanvas.addEventListener("paint", render);
    window.addEventListener("resize", render);

    return () => {
      activeCanvas.removeEventListener("paint", render);
      window.removeEventListener("resize", render);
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
        {useIframeFallback && <iframe title={card.name} srcDoc={card.html} sandbox="" loading="lazy" />}
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
