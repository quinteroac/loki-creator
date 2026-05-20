export type GeneratedCard = {
  id: string;
  name: string;
  prompt: string;
  html: string;
  sourceToolId?: string | null;
};

export type ToolDefinition = {
  id: string;
  slug: string;
  name: string;
  description: string;
  version: string;
  author: string;
  origin: "built-in" | "user";
  sourceType: "builtin" | "http" | "cli-local" | "cli-remote";
  invocationVisibility: "frontend" | "internal";
  capabilities: string[];
  inputSchema: Record<string, unknown>;
  outputSchema: Record<string, unknown>;
  exportable: boolean;
  createdBy?: string | null;
  createdAt?: string | null;
  updatedAt?: string | null;
  runtime: {
    sourceType: "builtin" | "http" | "cli-local" | "cli-remote";
    entrypoint?: string | null;
    command: string[];
    method: string;
    timeoutSeconds: number;
    workingDirectory?: string | null;
  };
  permissions: {
    network: boolean;
    filesystem: boolean;
    envVars: string[];
    allowedCommands: string[];
  };
  configuration: Array<{
    key: string;
    label: string;
    type: "string" | "number" | "boolean" | "select" | "secret";
    description?: string | null;
    required: boolean;
    default: unknown;
    options: string[];
    secret: boolean;
  }>;
};

export type ToolJobStatus = "queued" | "running" | "succeeded" | "failed";

export type ToolJob = {
  id: string;
  toolId: string;
  status: ToolJobStatus;
  createdAt: string;
  updatedAt: string;
  result?: {
    cards: GeneratedCard[];
  } | null;
  error?: string | null;
};

export type ToolJobRequest = {
  toolId: string;
  prompt: string;
  context: Record<string, unknown>;
  selectedCards: string[];
  params: Record<string, unknown>;
};

export type AgentDefinition = {
  id: string;
  name: string;
  description: string;
  defaultModel?: string | null;
};

export type AgentModel = {
  id: string;
  provider: string;
  name: string;
  label: string;
};

export type AgentRunRequest = {
  prompt: string;
  agentId: string | null;
  model: string;
  tools: string[];
  selectedCards: string[];
  context: Record<string, unknown>;
};

export type AgentRunResponse = {
  id: string;
  agentId: string;
  status: "succeeded" | "failed";
  responseText: string;
  toolJobIds: string[];
  cardIds: string[];
  error?: string;
};
