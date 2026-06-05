import type { AudioTimelineResponse, EditedMediaArtifact } from "../types";

const API_URL = import.meta.env.VITE_API_URL ?? "";

async function postJson<T>(path: string, payload: Record<string, unknown>): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let message = `Audio edit request failed: ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") {
        message = body.detail;
      }
    } catch {
      // Keep the status-based fallback.
    }
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

export function loadAudioTimeline(artifactUrl: string, maxPeaks = 160): Promise<AudioTimelineResponse> {
  return postJson<AudioTimelineResponse>("/api/artifacts/audio/timeline", {
    artifactUrl,
    maxPeaks,
  });
}

export function trimAudioArtifact(
  artifactUrl: string,
  startSeconds: number,
  endSeconds: number,
): Promise<EditedMediaArtifact> {
  return postJson<EditedMediaArtifact>("/api/artifacts/audio/trim", {
    artifactUrl,
    startSeconds,
    endSeconds,
  });
}
