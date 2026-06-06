import type { VideoEditArtifact, VideoLutOption, VideoTimelineResponse } from "../types";

const API_URL = import.meta.env.VITE_API_URL ?? "";

async function postJson<T>(path: string, payload: Record<string, unknown>): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let message = `Video edit request failed: ${response.status}`;
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

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`);

  if (!response.ok) {
    let message = `Video edit request failed: ${response.status}`;
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

export function listVideoLuts(): Promise<VideoLutOption[]> {
  return getJson<VideoLutOption[]>("/api/artifacts/video/luts");
}

export function loadVideoTimeline(
  artifactUrl: string,
  maxThumbnails = 16,
  lutId = "original",
): Promise<VideoTimelineResponse> {
  return postJson<VideoTimelineResponse>("/api/artifacts/video/timeline", {
    artifactUrl,
    maxThumbnails,
    lutId,
  });
}

export function exportVideoFrame(
  artifactUrl: string,
  timeSeconds: number,
  lutId = "original",
): Promise<VideoEditArtifact> {
  return postJson<VideoEditArtifact>("/api/artifacts/video/frame", {
    artifactUrl,
    timeSeconds,
    lutId,
  });
}

export function trimVideoArtifact(
  artifactUrl: string,
  startSeconds: number,
  endSeconds: number,
  lutId = "original",
): Promise<VideoEditArtifact> {
  return postJson<VideoEditArtifact>("/api/artifacts/video/trim", {
    artifactUrl,
    startSeconds,
    endSeconds,
    lutId,
  });
}
