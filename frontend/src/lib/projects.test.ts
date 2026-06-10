import { createWorkspaceSnapshot, dedupeCanvasNodesByDocumentId, filterProjectSummaries } from "./projects";
import type { CanvasNode, CardDocument, ProjectSummary } from "../types";

function assertEqual<T>(actual: T, expected: T, message: string) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(`${message}\nExpected: ${JSON.stringify(expected)}\nActual: ${JSON.stringify(actual)}`);
  }
}

const documents: CardDocument[] = [
  {
    id: "card_1",
    name: "Card",
    prompt: "Prompt",
    html: "",
  },
];
const nodes: CanvasNode[] = [
  { id: "node_1", cardDocumentId: "card_1", frame: { x: 0, y: 0, width: 240 } },
  { id: "node_2", cardDocumentId: "card_1", frame: { x: 24, y: 24, width: 240 } },
];

assertEqual(
  dedupeCanvasNodesByDocumentId(nodes).map((node) => node.id),
  ["node_1"],
  "keeps the first canvas node for each card document",
);

assertEqual(
  createWorkspaceSnapshot(documents, nodes),
  JSON.stringify({ cardDocuments: documents, canvasNodes: [nodes[0]] }),
  "workspace snapshots normalize duplicate canvas nodes",
);

const summaries: ProjectSummary[] = [
  {
    id: "active",
    name: "Campaign Board",
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    status: "active",
    cardCount: 2,
    artifactCount: 1,
  },
  {
    id: "archived",
    name: "Old Campaign",
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    status: "archived",
    cardCount: 3,
    artifactCount: 2,
  },
];

assertEqual(
  filterProjectSummaries(summaries, "active", "campaign").map((project) => project.id),
  ["active"],
  "filters projects by status and search text",
);

console.log("project helper tests passed");
