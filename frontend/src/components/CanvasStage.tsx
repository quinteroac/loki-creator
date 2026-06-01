import { useRef } from "react";
import type { CSSProperties, ChangeEvent } from "react";
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
  const selectedIdSet = new Set(selectedIds);
  const selectedEditorItems = nodes
    .filter((node) => selectedIdSet.has(node.cardDocumentId))
    .map((node) => {
      const document = documentsById[node.cardDocumentId];
      if (!document) return null;

      return {
        document,
        node,
        style: {
          "--selected-card-editor-left": `${node.frame.x}px`,
          "--selected-card-editor-top": `${node.frame.y + getCardHeight(node.frame.width, document) + 12}px`,
          "--selected-card-editor-width": `${Math.min(Math.max(node.frame.width, 360), 720)}px`,
        } as CSSProperties,
      };
    })
    .filter((item): item is { document: CardDocument; node: CanvasNode; style: CSSProperties } => item !== null);

  function updateNodeFrame(nodeId: string, frame: CanvasNodeFrame) {
    const layer = cardLayerRef.current;
    const node = nodes.find((candidate) => candidate.id === nodeId);
    const document = node ? documentsById[node.cardDocumentId] : undefined;
    const canvasWidth = layer?.clientWidth ?? CARD_DEFAULT_WIDTH + CANVAS_PADDING * 2;
    const canvasHeight = layer?.clientHeight ?? getCardHeight(CARD_DEFAULT_WIDTH, document) + CANVAS_PADDING * 2;

    onUpdateNodeFrame(nodeId, clampCanvasNodeFrame(frame, canvasWidth, canvasHeight, document));
  }

  function handleSelectedNameChange(cardDocumentId: string, event: ChangeEvent<HTMLInputElement>) {
    onRenameDocument(cardDocumentId, event.target.value);
  }

  function handleSelectedPromptChange(cardDocumentId: string, event: ChangeEvent<HTMLTextAreaElement>) {
    onUpdateDocumentPrompt(cardDocumentId, event.target.value);
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
                isSelected={selectedIdSet.has(node.cardDocumentId)}
                key={node.id}
                onDeleteDocument={onDeleteDocument}
                onRedoDocument={onRedoDocument}
                onRegisterPreviewCapture={onRegisterPreviewCapture}
                onUpdateFrame={updateNodeFrame}
                onToggleSelect={onToggleNode}
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
