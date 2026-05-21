import type { SkillDefinition } from "../types";

const API_URL = import.meta.env.VITE_API_URL ?? "";

export async function listSkills(): Promise<SkillDefinition[]> {
  const response = await fetch(`${API_URL}/api/skills`);

  if (!response.ok) {
    throw new Error(`Failed to load skills: ${response.status}`);
  }

  return response.json();
}
