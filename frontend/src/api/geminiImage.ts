import type {
  GeminiImageGenerationRequest,
  GeminiImageGenerationResponse,
} from "../types";

const API_URL = import.meta.env.VITE_API_URL ?? "";

async function parseGenerationResponse(response: Response, fallback: string): Promise<GeminiImageGenerationResponse> {
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

export async function generateGeminiImage(payload: GeminiImageGenerationRequest): Promise<GeminiImageGenerationResponse> {
  const response = await fetch(`${API_URL}/api/generations/gemini-image`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  return parseGenerationResponse(response, "Gemini image generation failed");
}
