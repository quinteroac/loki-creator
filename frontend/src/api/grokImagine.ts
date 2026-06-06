import type {
  GrokGenerationResponse,
  GrokImageGenerationRequest,
  GrokVideoGenerationRequest,
} from "../types";

const API_URL = import.meta.env.VITE_API_URL ?? "";

async function parseGenerationResponse(response: Response, fallback: string): Promise<GrokGenerationResponse> {
  if (!response.ok) {
    let message = await response.text();
    try {
      const parsed = JSON.parse(message) as { detail?: string };
      message = parsed.detail ?? message;
    } catch {
      // Keep the raw response text.
    }
    throw new Error(message || `${fallback}: ${response.status}`);
  }

  return response.json();
}

export async function generateGrokImage(payload: GrokImageGenerationRequest): Promise<GrokGenerationResponse> {
  const response = await fetch(`${API_URL}/api/generations/grok-image`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  return parseGenerationResponse(response, "Grok image generation failed");
}

export async function generateGrokVideo(payload: GrokVideoGenerationRequest): Promise<GrokGenerationResponse> {
  const response = await fetch(`${API_URL}/api/generations/grok-video`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  return parseGenerationResponse(response, "Grok video generation failed");
}
