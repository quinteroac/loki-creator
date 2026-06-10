import type { ProjectCreateRequest, ProjectDocument, ProjectSaveRequest, ProjectStatus, ProjectSummary } from "../types";

const API_URL = import.meta.env.VITE_API_URL ?? "";

export type ProjectListStatus = ProjectStatus | "all";

export function projectIdFromName(name: string): string {
  return name.trim().toLowerCase().replace(/[^a-z0-9_-]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 80) || "project";
}

async function readJsonResponse<T>(response: Response, fallbackMessage: string): Promise<T> {
  if (response.ok) {
    return response.json();
  }

  let message = fallbackMessage;
  try {
    const payload = await response.json();
    if (typeof payload.detail === "string") {
      message = payload.detail;
    }
  } catch {
    // Keep the fallback message when the backend returns a non-JSON error.
  }

  throw new Error(`${message}: ${response.status}`);
}

export async function listProjects(status: ProjectListStatus = "active"): Promise<ProjectSummary[]> {
  const response = await fetch(`${API_URL}/api/projects?status=${encodeURIComponent(status)}`);

  return readJsonResponse(response, "Failed to load projects");
}

export async function createProject(payload: ProjectCreateRequest): Promise<ProjectDocument> {
  const response = await fetch(`${API_URL}/api/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  return readJsonResponse(response, "Failed to create project");
}

export async function loadProject(projectId: string): Promise<ProjectDocument> {
  const response = await fetch(`${API_URL}/api/projects/${encodeURIComponent(projectId)}`);

  return readJsonResponse(response, "Failed to load project");
}

export async function saveProject(projectId: string, payload: ProjectSaveRequest): Promise<ProjectDocument> {
  const response = await fetch(`${API_URL}/api/projects/${encodeURIComponent(projectId)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  return readJsonResponse(response, "Failed to save project");
}

export async function archiveProject(projectId: string): Promise<ProjectDocument> {
  const response = await fetch(`${API_URL}/api/projects/${encodeURIComponent(projectId)}/archive`, {
    method: "POST",
  });

  return readJsonResponse(response, "Failed to archive project");
}

export async function trashProject(projectId: string): Promise<ProjectDocument> {
  const response = await fetch(`${API_URL}/api/projects/${encodeURIComponent(projectId)}/trash`, {
    method: "POST",
  });

  return readJsonResponse(response, "Failed to move project to trash");
}

export async function restoreProject(projectId: string): Promise<ProjectDocument> {
  const response = await fetch(`${API_URL}/api/projects/${encodeURIComponent(projectId)}/restore`, {
    method: "POST",
  });

  return readJsonResponse(response, "Failed to restore project");
}

export async function deleteProject(projectId: string): Promise<void> {
  const response = await fetch(`${API_URL}/api/projects/${encodeURIComponent(projectId)}`, {
    method: "DELETE",
  });

  await readJsonResponse(response, "Failed to permanently delete project");
}

export async function duplicateProject(projectId: string): Promise<ProjectDocument> {
  const response = await fetch(`${API_URL}/api/projects/${encodeURIComponent(projectId)}/duplicate`, {
    method: "POST",
  });

  return readJsonResponse(response, "Failed to duplicate project");
}

function filenameFromContentDisposition(header: string | null): string {
  const fallback = "project.loki-project.zip";
  if (!header) return fallback;

  const quotedMatch = header.match(/filename="([^"]+)"/i);
  if (quotedMatch?.[1]) return quotedMatch[1];

  const plainMatch = header.match(/filename=([^;]+)/i);
  return plainMatch?.[1]?.trim() || fallback;
}

function triggerBrowserDownload(blob: Blob, filename: string) {
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = objectUrl;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
}

export async function exportProject(projectId: string): Promise<void> {
  const response = await fetch(`${API_URL}/api/projects/${encodeURIComponent(projectId)}/export`);
  if (!response.ok) {
    await readJsonResponse(response, "Failed to export project");
    return;
  }

  const blob = await response.blob();
  triggerBrowserDownload(blob, filenameFromContentDisposition(response.headers.get("Content-Disposition")));
}

export async function importProject(file: File): Promise<ProjectDocument> {
  const formData = new FormData();
  formData.set("file", file);
  const response = await fetch(`${API_URL}/api/projects/import`, {
    method: "POST",
    body: formData,
  });

  return readJsonResponse(response, "Failed to import project");
}
