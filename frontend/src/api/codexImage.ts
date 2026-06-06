import type {
  CodexImageGenerationRequest,
  CodexImageGenerationResponse,
} from "../types";

const API_URL = import.meta.env.VITE_API_URL ?? "";

async function parseGenerationResponse(response: Response, fallback: string): Promise<CodexImageGenerationResponse> {
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

export async function generateCodexImage(payload: CodexImageGenerationRequest): Promise<CodexImageGenerationResponse> {
  const response = await fetch(`${API_URL}/api/generations/codex-image`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  return parseGenerationResponse(response, "Codex image generation failed");
}
