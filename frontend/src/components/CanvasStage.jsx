export function CanvasStage({ selectedNode }) {
  return (
    <section className="canvas-shell" aria-label="Creative canvas">
      <div className="canvas" id="creativeCanvas" tabIndex={0}>
        <div className="canvas-selection-note">
          {selectedNode ? `${selectedNode.title} selected` : "No selection"}
        </div>
      </div>
    </section>
  );
}
