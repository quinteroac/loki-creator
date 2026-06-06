import type { AgentDefinition, AgentRunRequest, AgentRunResponse, AgentModel } from "../types";

function defaultAgentApiUrl() {
  if (typeof window === "undefined") return "http://127.0.0.1:8787";
  return `${window.location.protocol}//${window.location.hostname}:8787`;
}

const AGENT_API_URL = import.meta.env.VITE_AGENT_API_URL ?? defaultAgentApiUrl();

export async function listAgents(): Promise<AgentDefinition[]> {
  const response = await fetch(`${AGENT_API_URL}/api/agents`);

  if (!response.ok) {
    throw new Error("Agent list request failed");
  }

  return response.json();
}

export async function listAgentModels(): Promise<AgentModel[]> {
  const response = await fetch(`${AGENT_API_URL}/api/models`);

  if (!response.ok) {
    throw new Error("Agent model list request failed");
  }

  return response.json();
}

export async function createAgentRun(payload: AgentRunRequest): Promise<AgentRunResponse> {
  const response = await fetch(`${AGENT_API_URL}/api/agent-runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Agent run request failed: ${response.status}`);
  }

  return response.json();
}

export async function stopAgentRun(runId: string): Promise<{ id: string; stopped: boolean; status: "cancelled" }> {
  const response = await fetch(`${AGENT_API_URL}/api/agent-runs/${encodeURIComponent(runId)}/stop`, {
    method: "POST",
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Agent stop request failed: ${response.status}`);
  }

  return response.json();
}

export function agentRunEventsUrl(streamId: string) {
  return `${AGENT_API_URL}/api/agent-runs/${encodeURIComponent(streamId)}/events`;
}
