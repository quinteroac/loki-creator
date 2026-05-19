import { useEffect, useRef, useState } from "react";

function resizeCanvas(canvas) {
  const pixelRatio = window.devicePixelRatio || 1;
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;

  canvas.width = width * pixelRatio;
  canvas.height = height * pixelRatio;

  return { height, pixelRatio, width };
}

function supportsHtmlInCanvas(context) {
  return typeof context?.drawElementImage === "function";
}

function drawHtmlInCanvas(canvas, htmlElement) {
  const context = canvas.getContext("2d");

  if (!supportsHtmlInCanvas(context) || !htmlElement) return false;

  const { height, pixelRatio, width } = resizeCanvas(canvas);
  context.reset?.();
  context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
  context.drawElementImage(htmlElement, 0, 0, width, height);

  return true;
}

export function CanvasCard({ card, isSelected, onToggleSelect }) {
  const canvasRef = useRef(null);
  const htmlRef = useRef(null);
  const [useIframeFallback, setUseIframeFallback] = useState(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    const htmlElement = htmlRef.current;

    if (!canvas) return undefined;

    function render() {
      const didDrawHtml = drawHtmlInCanvas(canvas, htmlElement);
      setUseIframeFallback(!didDrawHtml);
    }

    render();
    canvas.addEventListener("paint", render);
    window.addEventListener("resize", render);

    return () => {
      canvas.removeEventListener("paint", render);
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
