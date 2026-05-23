import type { ProjectDocument, ProjectSaveRequest, ProjectSummary } from "../types";

const API_URL = import.meta.env.VITE_API_URL ?? "";

export function projectIdFromName(name: string): string {
  return name.trim().toLowerCase().replace(/[^a-z0-9_-]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 80) || "project";
}

export async function listProjects(): Promise<ProjectSummary[]> {
  const response = await fetch(`${API_URL}/api/projects`);

  if (!response.ok) {
    throw new Error(`Failed to load projects: ${response.status}`);
  }

  return response.json();
}

export async function loadProject(projectId: string): Promise<ProjectDocument> {
  const response = await fetch(`${API_URL}/api/projects/${encodeURIComponent(projectId)}`);

  if (!response.ok) {
    throw new Error(`Failed to load project: ${response.status}`);
  }

  return response.json();
}

export async function saveProject(payload: ProjectSaveRequest): Promise<ProjectDocument> {
  const projectId = projectIdFromName(payload.name);
  const response = await fetch(`${API_URL}/api/projects/${encodeURIComponent(projectId)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Failed to save project: ${response.status}`);
  }

  return response.json();
}
