export type CardKind = "generic" | "image" | "video" | "audio" | "diagnostic" | "artifact" | "interactive";

export type CardAspectRatio = "1:1" | "4:3" | "16:9" | "9:16" | "auto";

export type CardMetadata = {
  kind?: CardKind;
  title?: string;
  description?: string;
  thumbnailUrl?: string;
  artifactUrl?: string;
  createdAt?: string;
  width?: number;
  height?: number;
  tags?: string[];
  capabilities?: string[];
  preferredAspectRatio?: CardAspectRatio;
  playableMedia?: boolean;
};

export type CardDocument = {
  id: string;
  name: string;
  prompt: string;
  html: string;
  sourceSkillId?: string | null;
  sourceActionId?: string | null;
  metadata?: CardMetadata;
};

export type GeneratedCard = CardDocument;

export type SelectedCardPreview =
  | {
      source: "rendered-preview";
      mimeType: "image/png";
      dataUrl: string;
      width: number;
      height: number;
      omitted?: false;
    }
  | {
      source: "rendered-preview";
      omitted: true;
      reason: "capture-unavailable" | "iframe-fallback" | "size-limit" | "tainted-canvas";
      width?: number;
      height?: number;
    };

export type SelectedCardMediaAsset = {
  kind: "image" | "video" | "audio" | "iframe" | "source" | "canvas";
  src?: string;
  dataUrl?: string;
  mimeType?: string;
  alt?: string;
  width?: number;
  height?: number;
  omitted?: boolean;
  reason?: "size-limit" | "missing-source" | "fetch-error";
};

export type SelectedCardSnapshot = {
  id: string;
  name: string;
  displayTitle: string;
  prompt: string;
  html: string;
  preview?: SelectedCardPreview;
  mediaAssets: SelectedCardMediaAsset[];
  sourceSkillId?: string | null;
  sourceActionId?: string | null;
  metadata?: CardMetadata;
};

export type AgentAttachmentKind = "image" | "video" | "audio" | "text" | "json" | "pdf" | "artifact";

export type AgentAttachment = {
  id: string;
  name: string;
  mimeType: string;
  size: number;
  kind: AgentAttachmentKind;
  dataUrl?: string;
  text?: string;
  omitted?: boolean;
  reason?: "size-limit" | "read-error";
};

export type CanvasNodeFrame = {
  width: number;
  x: number;
  y: number;
};

export type CanvasNode = {
  id: string;
  cardDocumentId: string;
  frame: CanvasNodeFrame;
};

export type SkillDefinition = {
  id: string;
  name: string;
  description: string;
  origin: "built-in" | "user";
  path: string;
  capabilities: string[];
  arguments: SkillArgumentDefinition[];
  action?: {
    type: "cli-local";
    command: string[];
    timeoutSeconds: number;
  } | null;
  output?: {
    packager: "auto";
    kind: "auto" | "image" | "video" | "audio" | "html" | "text" | "diagnostic" | "artifact";
  };
  runtime?: {
    modelsDir?: string | null;
  };
};

export type SkillArgumentOption = {
  value: string;
  label?: string | null;
  description?: string | null;
};

export type SkillArgumentDefinition = {
  id: string;
  label: string;
  description: string;
  type: "choice" | "text";
  required: boolean;
  askWhen: "always" | "missing";
  options: SkillArgumentOption[];
  order: number;
};

export type SkillRunStatus = "queued" | "running" | "succeeded" | "failed";

export type SkillRun = {
  id: string;
  skillId: string;
  status: SkillRunStatus;
  createdAt: string;
  updatedAt: string;
  result?: {
    cards: CardDocument[];
  } | null;
  error?: string | null;
};

export type SkillRunRequest = {
  skillId: string;
  prompt: string;
  context: Record<string, unknown>;
  selectedCards: string[];
  selectedCardSnapshots: SelectedCardSnapshot[];
  attachments: AgentAttachment[];
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
  skills: string[];
  selectedCards: string[];
  selectedCardSnapshots: SelectedCardSnapshot[];
  attachments: AgentAttachment[];
  context: Record<string, unknown>;
  conversationId?: string;
  answers?: Record<string, string>;
  collectedArgs?: Record<string, string>;
};

export type AgentQuestion = {
  id: string;
  text: string;
  inputType: "choice" | "text";
  options: SkillArgumentOption[];
  skillId?: string;
  argumentId?: string;
};

export type AgentRunResponse = {
  id: string;
  agentId: string;
  status: "succeeded" | "failed" | "needs_input";
  responseText: string;
  skillRunIds: string[];
  cardIds: string[];
  conversationId?: string;
  question?: AgentQuestion;
  collectedArgs?: Record<string, string>;
  error?: string;
};
