import { useEffect, useRef, useState } from "react";
import { CanvasCard } from "./CanvasCard";
import type { CanvasCardFrame } from "./CanvasCard";
import type { GeneratedCard } from "../types";

type CanvasStageProps = {
  cards: GeneratedCard[];
  selectedCards: string[];
  selectedNode?: GeneratedCard;
  onToggleCard: (cardId: string) => void;
};

const CARD_DEFAULT_WIDTH = 512;
const CARD_MIN_WIDTH = 240;
const CARD_MAX_WIDTH = 720;
const CARD_ASPECT_HEIGHT_RATIO = 4 / 3;
const CARD_GAP = 16;
const CANVAS_PADDING = 24;

function getCardHeight(width: number) {
  return width * CARD_ASPECT_HEIGHT_RATIO;
}

function clampFrameToCanvas(frame: CanvasCardFrame, canvasWidth: number, canvasHeight: number): CanvasCardFrame {
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

function getInitialCardFrame(index: number, canvasWidth: number): CanvasCardFrame {
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

export function CanvasStage({ cards, selectedCards, selectedNode, onToggleCard }: CanvasStageProps) {
  const canvasRef = useRef<HTMLDivElement | null>(null);
  const cardLayerRef = useRef<HTMLDivElement | null>(null);
  const [cardFrames, setCardFrames] = useState<Record<string, CanvasCardFrame>>({});

  useEffect(() => {
    setCardFrames((currentFrames) => {
      const layerWidth = cardLayerRef.current?.clientWidth ?? 0;
      const nextFrames = { ...currentFrames };
      const cardIds = new Set(cards.map((card) => card.id));
      let didChange = false;

      cards.forEach((card, index) => {
        if (!nextFrames[card.id]) {
          nextFrames[card.id] = getInitialCardFrame(index, layerWidth);
          didChange = true;
        }
      });

      Object.keys(nextFrames).forEach((cardId) => {
        if (!cardIds.has(cardId)) {
          delete nextFrames[cardId];
          didChange = true;
        }
      });

      return didChange ? nextFrames : currentFrames;
    });
  }, [cards]);

  function updateCardFrame(cardId: string, frame: CanvasCardFrame) {
    const layer = cardLayerRef.current;
    const canvasWidth = layer?.clientWidth ?? CARD_DEFAULT_WIDTH + CANVAS_PADDING * 2;
    const canvasHeight = layer?.clientHeight ?? getCardHeight(CARD_DEFAULT_WIDTH) + CANVAS_PADDING * 2;

    setCardFrames((currentFrames) => ({
      ...currentFrames,
      [cardId]: clampFrameToCanvas(frame, canvasWidth, canvasHeight),
    }));
  }

  return (
    <section className="canvas-shell" aria-label="Creative canvas">
      <div className="canvas" id="creativeCanvas" ref={canvasRef} tabIndex={0}>
        <div className="canvas-card-layer" ref={cardLayerRef}>
          {cards.map((card) => (
            <CanvasCard
              card={card}
              frame={cardFrames[card.id] ?? getInitialCardFrame(0, cardLayerRef.current?.clientWidth ?? 0)}
              isSelected={selectedCards.includes(card.id)}
              key={card.id}
              onUpdateFrame={updateCardFrame}
              onToggleSelect={onToggleCard}
            />
          ))}
        </div>
        <div className="canvas-selection-note">
          {selectedNode ? `${selectedNode.name} selected` : "No selection"}
        </div>
      </div>
    </section>
  );
}
