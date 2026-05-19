const API_URL = import.meta.env.VITE_API_URL ?? "";

import type { ToolDefinition } from "../types";

export async function listTools(): Promise<ToolDefinition[]> {
  const response = await fetch(`${API_URL}/api/tools`);

  if (!response.ok) {
    throw new Error("Tool list request failed");
  }

  return response.json();
}
