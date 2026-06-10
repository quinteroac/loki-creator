import {
  archiveProject,
  createProject,
  deleteProject,
  duplicateProject,
  listProjects,
  projectIdFromName,
  saveProject,
} from "./projects";

function assertEqual<T>(actual: T, expected: T, message: string) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(`${message}\nExpected: ${JSON.stringify(expected)}\nActual: ${JSON.stringify(actual)}`);
  }
}

function jsonResponse(payload: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(payload), {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

const originalFetch = globalThis.fetch;
const calls: Array<{ body?: unknown; method: string; url: string }> = [];

globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
  const url = String(input);
  const method = init?.method ?? "GET";
  const body = typeof init?.body === "string" ? JSON.parse(init.body) as Record<string, unknown> : undefined;
  calls.push({ body, method, url });

  if (url.endsWith("/api/projects?status=all")) {
    return jsonResponse([
      {
        id: "project",
        name: "Project",
        createdAt: "2026-01-01T00:00:00Z",
        updatedAt: "2026-01-01T00:00:00Z",
        status: "active",
        cardCount: 0,
        artifactCount: 0,
      },
    ]);
  }

  if (url.endsWith("/api/projects") && method === "POST") {
    return jsonResponse({ id: "new-project", name: body?.name, schemaVersion: 2, status: "active" });
  }

  if (url.endsWith("/api/projects/stable-id") && method === "PUT") {
    return jsonResponse({ id: "stable-id", name: body?.name, schemaVersion: 2, status: "active" });
  }

  if (url.endsWith("/api/projects/stable-id/archive") && method === "POST") {
    return jsonResponse({ id: "stable-id", name: "Archived", schemaVersion: 2, status: "archived" });
  }

  if (url.endsWith("/api/projects/stable-id/duplicate") && method === "POST") {
    return jsonResponse({ id: "stable-id-copy", name: "Copy", schemaVersion: 2, status: "active" });
  }

  if (url.endsWith("/api/projects/stable-id") && method === "DELETE") {
    return jsonResponse({ status: "deleted" });
  }

  return jsonResponse({ detail: "unexpected request" }, { status: 500 });
}) as typeof fetch;

assertEqual(projectIdFromName(" My Project! "), "my-project", "creates stable project slugs");

const projects = await listProjects("all");
assertEqual(projects[0]?.id, "project", "loads project summaries with status filter");

const created = await createProject({ name: "New Project", cardDocuments: [], canvasNodes: [] });
assertEqual(created.id, "new-project", "creates projects through POST /api/projects");

const saved = await saveProject("stable-id", { name: "Renamed Project", cardDocuments: [], canvasNodes: [] });
assertEqual(saved.id, "stable-id", "save keeps backend project id stable");

const archived = await archiveProject("stable-id");
assertEqual(archived.status, "archived", "archives projects through status endpoint");

const duplicated = await duplicateProject("stable-id");
assertEqual(duplicated.id, "stable-id-copy", "duplicates projects through duplicate endpoint");

await deleteProject("stable-id");

assertEqual(calls.map((call) => `${call.method} ${call.url}`), [
  "GET /api/projects?status=all",
  "POST /api/projects",
  "PUT /api/projects/stable-id",
  "POST /api/projects/stable-id/archive",
  "POST /api/projects/stable-id/duplicate",
  "DELETE /api/projects/stable-id",
], "uses the expected project endpoints");

globalThis.fetch = originalFetch;
console.log("projects api tests passed");
