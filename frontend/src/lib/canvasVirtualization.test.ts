import {
  canvasNodeIntersectsBounds,
  getCanvasViewportBounds,
  getVirtualizedCanvasNodes,
  type CanvasViewportBounds,
} from "./canvasVirtualization";
import type { CanvasNode, CardDocument } from "../types";

function assertEqual<T>(actual: T, expected: T, message: string) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(`${message}\nExpected: ${JSON.stringify(expected)}\nActual: ${JSON.stringify(actual)}`);
  }
}

function card(id: string): CardDocument {
  return {
    id,
    name: id,
    prompt: "",
    html: "",
    metadata: {
      kind: "image",
      preferredAspectRatio: "1:1",
      title: id,
    },
  };
}

function node(id: string, cardDocumentId: string, x: number, y: number): CanvasNode {
  return {
    id,
    cardDocumentId,
    frame: {
      width: 100,
      x,
      y,
    },
  };
}

const documentsById = {
  card_inside: card("card_inside"),
  card_outside: card("card_outside"),
  card_overscan: card("card_overscan"),
  card_selected: card("card_selected"),
  card_forced: card("card_forced"),
};

const bounds: CanvasViewportBounds = {
  left: 0,
  top: 0,
  right: 300,
  bottom: 300,
};

assertEqual(
  canvasNodeIntersectsBounds(node("node_inside", "card_inside", 40, 50), documentsById.card_inside, bounds),
  true,
  "includes a node inside viewport bounds",
);

assertEqual(
  canvasNodeIntersectsBounds(node("node_outside", "card_outside", 420, 420), documentsById.card_outside, bounds),
  false,
  "excludes a node outside viewport bounds",
);

assertEqual(
  getCanvasViewportBounds({
    height: 300,
    overscan: 50,
    pan: { x: -100, y: -40 },
    width: 600,
    zoom: 2,
  }),
  { left: 0, top: -30, right: 400, bottom: 220 },
  "respects pan, zoom, and overscan when calculating logical bounds",
);

const virtualized = getVirtualizedCanvasNodes({
  bounds,
  documentsById,
  forcedNodeIds: new Set(["node_forced"]),
  nodes: [
    node("node_inside", "card_inside", 40, 50),
    node("node_outside", "card_outside", 420, 420),
    node("node_overscan", "card_overscan", 330, 40),
    node("node_selected", "card_selected", 680, 680),
    node("node_forced", "card_forced", 900, 900),
  ],
  selectedCardIds: new Set(["card_selected"]),
});

assertEqual(
  virtualized.map((entry) => [entry.node.id, entry.reason]),
  [
    ["node_inside", "visible"],
    ["node_selected", "selected"],
    ["node_forced", "forced"],
  ],
  "returns visible, selected, and forced nodes only",
);

const overscanVirtualized = getVirtualizedCanvasNodes({
  bounds: { ...bounds, right: 360 },
  documentsById,
  nodes: [
    node("node_overscan", "card_overscan", 330, 40),
  ],
});

assertEqual(
  overscanVirtualized.map((entry) => [entry.node.id, entry.reason]),
  [["node_overscan", "visible"]],
  "includes a node that intersects overscan-expanded bounds",
);

console.log("canvasVirtualization tests passed");
