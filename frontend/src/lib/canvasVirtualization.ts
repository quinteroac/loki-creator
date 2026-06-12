import { getCardHeight } from "./cardDocuments";
import type { CanvasNode, CardDocument } from "../types";

export type CanvasViewportBounds = {
  left: number;
  top: number;
  right: number;
  bottom: number;
};

export type VirtualizedCanvasNode = {
  node: CanvasNode;
  reason: "visible" | "selected" | "forced";
};

export function getCanvasViewportBounds({
  height,
  overscan = 0,
  pan,
  width,
  zoom,
}: {
  height: number;
  overscan?: number;
  pan: { x: number; y: number };
  width: number;
  zoom: number;
}): CanvasViewportBounds {
  const safeZoom = Math.max(zoom, 0.01);
  const left = -pan.x / safeZoom;
  const top = -pan.y / safeZoom;

  return {
    left: left - overscan,
    top: top - overscan,
    right: left + width / safeZoom + overscan,
    bottom: top + height / safeZoom + overscan,
  };
}

export function canvasNodeIntersectsBounds(
  node: CanvasNode,
  document: CardDocument,
  bounds: CanvasViewportBounds,
): boolean {
  const height = getCardHeight(node.frame.width, document, node.frame);
  const right = node.frame.x + node.frame.width;
  const bottom = node.frame.y + height;

  return node.frame.x <= bounds.right && right >= bounds.left && node.frame.y <= bounds.bottom && bottom >= bounds.top;
}

export function getVirtualizedCanvasNodes({
  bounds,
  documentsById,
  forcedNodeIds = new Set(),
  nodes,
  selectedCardIds = new Set(),
}: {
  bounds: CanvasViewportBounds;
  documentsById: Record<string, CardDocument>;
  forcedNodeIds?: Set<string>;
  nodes: CanvasNode[];
  selectedCardIds?: Set<string>;
}): VirtualizedCanvasNode[] {
  const virtualizedNodes: VirtualizedCanvasNode[] = [];

  for (const node of nodes) {
    const document = documentsById[node.cardDocumentId];
    if (!document) continue;

    if (forcedNodeIds.has(node.id)) {
      virtualizedNodes.push({ node, reason: "forced" });
      continue;
    }

    if (selectedCardIds.has(node.cardDocumentId)) {
      virtualizedNodes.push({ node, reason: "selected" });
      continue;
    }

    if (canvasNodeIntersectsBounds(node, document, bounds)) {
      virtualizedNodes.push({ node, reason: "visible" });
    }
  }

  return virtualizedNodes;
}
