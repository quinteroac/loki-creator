import { useRef } from "react";
import {
  CARD_DEFAULT_WIDTH,
  CANVAS_PADDING,
  clampCanvasNodeFrame,
  getCardDisplayTitle,
  getCardHeight,
} from "../lib/cardDocuments";
import { CanvasCard } from "./CanvasCard";
import type { CardDocument, CanvasNode, CanvasNodeFrame, SelectedCardPreview } from "../types";

type CanvasStageProps = {
  documentsById: Record<string, CardDocument>;
  nodes: CanvasNode[];
  selectedIds: string[];
  selectedDocument?: CardDocument;
  onRenameDocument: (cardDocumentId: string, title: string) => void;
  onRegisterPreviewCapture: (cardDocumentId: string, capturePreview: () => SelectedCardPreview) => () => void;
  onToggleNode: (nodeId: string) => void;
  onUpdateNodeFrame: (nodeId: string, frame: CanvasNodeFrame) => void;
};

export function CanvasStage({
  documentsById,
  nodes,
  selectedIds,
  selectedDocument,
  onRenameDocument,
  onRegisterPreviewCapture,
  onToggleNode,
  onUpdateNodeFrame,
}: CanvasStageProps) {
  const canvasRef = useRef<HTMLDivElement | null>(null);
  const cardLayerRef = useRef<HTMLDivElement | null>(null);

  function updateNodeFrame(nodeId: string, frame: CanvasNodeFrame) {
    const layer = cardLayerRef.current;
    const node = nodes.find((candidate) => candidate.id === nodeId);
    const document = node ? documentsById[node.cardDocumentId] : undefined;
    const canvasWidth = layer?.clientWidth ?? CARD_DEFAULT_WIDTH + CANVAS_PADDING * 2;
    const canvasHeight = layer?.clientHeight ?? getCardHeight(CARD_DEFAULT_WIDTH, document) + CANVAS_PADDING * 2;

    onUpdateNodeFrame(nodeId, clampCanvasNodeFrame(frame, canvasWidth, canvasHeight, document));
  }

  return (
    <section className="canvas-shell" aria-label="Creative canvas">
      <div className="canvas" id="creativeCanvas" ref={canvasRef} tabIndex={0}>
        <div className="canvas-card-layer" ref={cardLayerRef}>
          {nodes.map((node) => {
            const document = documentsById[node.cardDocumentId];
            if (!document) return null;

            return (
              <CanvasCard
                document={document}
                node={node}
                isSelected={selectedIds.includes(node.cardDocumentId)}
                key={node.id}
                onRenameDocument={onRenameDocument}
                onRegisterPreviewCapture={onRegisterPreviewCapture}
                onUpdateFrame={updateNodeFrame}
                onToggleSelect={onToggleNode}
              />
            );
          })}
        </div>
        <div className="canvas-selection-note">
          {selectedDocument ? `${getCardDisplayTitle(selectedDocument)} selected` : "No selection"}
        </div>
      </div>
    </section>
  );
}
