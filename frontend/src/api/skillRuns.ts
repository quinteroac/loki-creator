import type { SkillRun } from "../types";

const API_URL = import.meta.env.VITE_API_URL ?? "";

export async function listSkillRuns(options: { status?: SkillRun["status"] } = {}): Promise<SkillRun[]> {
  const searchParams = new URLSearchParams();
  if (options.status) searchParams.set("status", options.status);
  const suffix = searchParams.toString() ? `?${searchParams.toString()}` : "";
  const response = await fetch(`${API_URL}/api/skill-runs${suffix}`);

  if (!response.ok) {
    throw new Error(`Failed to load skill runs: ${response.status}`);
  }

  return response.json();
}

export async function waitForSkillRun(runId: string): Promise<SkillRun> {
  while (true) {
    const response = await fetch(`${API_URL}/api/skill-runs/${runId}`);

    if (!response.ok) {
      throw new Error(`Failed to load skill run ${runId}: ${response.status}`);
    }

    const run = (await response.json()) as SkillRun;
    if (run.status === "succeeded" || run.status === "failed" || run.status === "cancelled") return run;

    await new Promise((resolve) => window.setTimeout(resolve, 500));
  }
}
