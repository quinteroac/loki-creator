import type { ComfyGenerationRequest, ComfyGenerationResponse } from "../types";

const API_URL = import.meta.env.VITE_API_URL ?? "";

export async function generateComfy(payload: ComfyGenerationRequest): Promise<ComfyGenerationResponse> {
  const response = await fetch(`${API_URL}/api/generations/comfy`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let message = await response.text();
    try {
      const parsed = JSON.parse(message) as { detail?: string };
      message = parsed.detail ?? message;
    } catch {
      // Keep the raw response text.
    }
    throw new Error(message || `Comfy generation failed: ${response.status}`);
  }

  return response.json();
}
