import { CanvasCard } from "./CanvasCard";

export function CanvasStage({ cards, selectedCards, selectedNode, onToggleCard }) {
  return (
    <section className="canvas-shell" aria-label="Creative canvas">
      <div className="canvas" id="creativeCanvas" tabIndex={0}>
        <div className="canvas-card-grid">
          {cards.map((card) => (
            <CanvasCard
              card={card}
              isSelected={selectedCards.includes(card.id)}
              key={card.id}
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
