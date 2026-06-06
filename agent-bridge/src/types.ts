export type LokiAgent = {
  id: string;
  name: string;
  description: string;
  defaultModel?: string | null;
  defaultSkills: string[];
};

export type LokiModel = {
  id: string;
  provider: string;
  name: string;
  label: string;
};

export type LokiSkill = {
  id: string;
  name: string;
  description: string;
  path: string;
  origin: "built-in" | "user";
  capabilities: string[];
  arguments: LokiSkillArgument[];
  action?: {
    type: "cli-local";
    command: string[];
    timeoutSeconds: number;
  } | null;
  output?: {
    packager: "auto";
    kind: "auto" | "image" | "video" | "audio" | "html" | "text" | "diagnostic" | "artifact";
  };
};

export type LokiSkillArgumentOption = {
  value: string;
  label?: string | null;
  description?: string | null;
};

export type LokiSkillArgument = {
  id: string;
  label: string;
  description?: string;
  type: "choice" | "text";
  required: boolean;
  askWhen: "always" | "missing";
  dependsOn?: Record<string, string>;
  options: LokiSkillArgumentOption[];
  order: number;
};

export type LokiSkillRun = {
  id: string;
  skillId: string;
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  result?: {
    cards?: Array<{
      id: string;
      name: string;
      sourceSkillId?: string | null;
      sourceActionId?: string | null;
      metadata?: Record<string, unknown> | null;
    }>;
  } | null;
  error?: string | null;
};

export type LokiSkillRawResult = {
  cards?: unknown[];
  artifacts?: Array<Record<string, unknown> | string>;
  media?: Array<Record<string, unknown> | string>;
  html?: string | null;
  text?: string | null;
  diagnostics?: Array<Record<string, unknown> | string>;
  metadata?: Record<string, unknown>;
};

export type SelectedCardSnapshot = {
  id: string;
  name: string;
  displayTitle: string;
  prompt: string;
  html: string;
  preview?: {
    source: "rendered-preview";
    mimeType?: string;
    dataUrl?: string;
    width?: number;
    height?: number;
    omitted?: boolean;
    reason?: string;
  };
  mediaAssets?: Array<{
    kind: "image" | "video" | "audio" | "iframe" | "source" | "canvas";
    src?: string;
    dataUrl?: string;
    mimeType?: string;
    alt?: string;
    width?: number;
    height?: number;
    omitted?: boolean;
    reason?: string;
  }>;
  sourceSkillId?: string | null;
  sourceActionId?: string | null;
  metadata?: Record<string, unknown> | null;
};

export type AgentAttachment = {
  id: string;
  name: string;
  mimeType: string;
  size: number;
  kind: "image" | "video" | "audio" | "text" | "json" | "pdf" | "artifact";
  dataUrl?: string;
  src?: string;
  artifactUrl?: string;
  text?: string;
  omitted?: boolean;
  reason?: string;
};

export type AgentRunRequest = {
  prompt: string;
  agentId?: string | null;
  model: string;
  skills: string[];
  selectedCards: string[];
  selectedCardSnapshots?: SelectedCardSnapshot[];
  attachments?: AgentAttachment[];
  context: Record<string, unknown>;
  conversationId?: string;
  answers?: Record<string, string>;
  collectedArgs?: Record<string, string>;
  streamId?: string;
};

export type AgentQuestion = {
  id: string;
  text: string;
  inputType: "choice" | "text";
  options: LokiSkillArgumentOption[];
  skillId?: string;
  argumentId?: string;
};

export type AgentRunResponse = {
  id: string;
  agentId: string;
  status: "succeeded" | "failed" | "needs_input" | "cancelled";
  responseText: string;
  skillRunIds: string[];
  cardIds: string[];
  conversationId?: string;
  question?: AgentQuestion;
  collectedArgs?: Record<string, string>;
  error?: string;
};

export type LokiSkillParams = {
  prompt: string;
  outputText?: string;
  title?: string;
  subtitle?: string;
  body?: string;
  footer?: string;
  paramsJson?: string;
};

export type AgentRuntimeMode = "pi-tools" | "grok-build-stdio";

export type AgentRunStreamEvent = {
  type:
    | "status"
    | "user"
    | "assistant_delta"
    | "assistant_message"
    | "thinking_delta"
    | "tool_start"
    | "tool_update"
    | "tool_end"
    | "skill"
    | "question"
    | "done"
    | "error";
  message?: string;
  status?: AgentRunResponse["status"] | "running";
  skillName?: string;
  toolName?: string;
  toolCallId?: string;
  skillRunId?: string;
  cardIds?: string[];
};
