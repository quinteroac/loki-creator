import type { CanvasNode, CardDocument, ProjectStatus, ProjectSummary } from "../types";

export function dedupeCanvasNodesByDocumentId(nodes: CanvasNode[]): CanvasNode[] {
  const seenDocumentIds = new Set<string>();
  let hasDuplicate = false;
  const dedupedNodes = nodes.filter((node) => {
    if (seenDocumentIds.has(node.cardDocumentId)) {
      hasDuplicate = true;
      return false;
    }

    seenDocumentIds.add(node.cardDocumentId);
    return true;
  });

  return hasDuplicate ? dedupedNodes : nodes;
}

export function createWorkspaceSnapshot(cardDocuments: CardDocument[], canvasNodes: CanvasNode[]) {
  return JSON.stringify({
    cardDocuments,
    canvasNodes: dedupeCanvasNodesByDocumentId(canvasNodes),
  });
}

export function filterProjectSummaries(
  projects: ProjectSummary[],
  status: ProjectStatus,
  search: string,
): ProjectSummary[] {
  const normalizedSearch = search.trim().toLowerCase();

  return projects.filter((project) => {
    const matchesStatus = project.status === status;
    const matchesSearch = !normalizedSearch || project.name.toLowerCase().includes(normalizedSearch);

    return matchesStatus && matchesSearch;
  });
}
