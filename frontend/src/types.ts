export type CardKind = "generic" | "image" | "video" | "audio" | "diagnostic" | "artifact" | "interactive" | "note";

export type CardAspectRatio = "1:1" | "4:3" | "16:9" | "9:16" | "auto";

export type CardMetadata = {
  [key: string]: unknown;
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
  resolution?: string;
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

export type SeedanceAspectRatio = "16:9" | "9:16";

export type SeedanceDuration = 4 | 5 | 7 | 10 | 15;

export type ComposerMode = "agent" | "seedance" | "grok";

export type GrokTool = "image" | "video";

export type GrokImageAspectRatio = "1:1" | "4:3" | "16:9" | "9:16";

export type GrokImageResolution = "1k" | "2k";

export type GrokVideoAspectRatio = "16:9" | "9:16" | "1:1" | "4:3";

export type GrokVideoResolution = "720p" | "480p";

export type GrokVideoDuration = 5 | 10 | 15;

export type SeedanceVideoGenerationRequest = {
  prompt: string;
  aspectRatio: SeedanceAspectRatio;
  duration: SeedanceDuration;
  selectedCardSnapshots: SelectedCardSnapshot[];
  attachments: AgentAttachment[];
};

export type SeedanceVideoGenerationResponse = {
  cards: GeneratedCard[];
};

export type GrokImageGenerationRequest = {
  prompt: string;
  aspectRatio: GrokImageAspectRatio;
  resolution: GrokImageResolution;
  selectedCardSnapshots: SelectedCardSnapshot[];
  attachments: AgentAttachment[];
};

export type GrokVideoGenerationRequest = {
  prompt: string;
  aspectRatio: GrokVideoAspectRatio;
  resolution: GrokVideoResolution;
  duration: GrokVideoDuration;
  selectedCardSnapshots: SelectedCardSnapshot[];
  attachments: AgentAttachment[];
};

export type GrokGenerationResponse = {
  cards: GeneratedCard[];
};

export type VideoTimelineThumbnail = {
  artifactUrl: string;
  timeSeconds: number;
  width: number;
  height: number;
};

export type VideoTimelineResponse = {
  artifactUrl: string;
  durationSeconds: number;
  width: number;
  height: number;
  fps: number;
  thumbnails: VideoTimelineThumbnail[];
};

export type VideoLutOption = {
  id: string;
  label: string;
};

export type AudioTimelineResponse = {
  artifactUrl: string;
  durationSeconds: number;
  sampleRate: number;
  channels: number;
  peaks: number[];
};

export type EditedMediaArtifact = {
  artifactUrl: string;
  sourceArtifactUrl: string;
  name: string;
  kind: "image" | "video" | "audio";
  mimeType: string;
  size: number;
  width?: number | null;
  height?: number | null;
  durationSeconds?: number | null;
  timeSeconds?: number | null;
  startSeconds?: number | null;
  endSeconds?: number | null;
  sampleRate?: number | null;
  channels?: number | null;
  lutId?: string | null;
  lutLabel?: string | null;
};

export type VideoEditArtifact = EditedMediaArtifact;

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
  height?: number;
  width: number;
  x: number;
  y: number;
};

export type CanvasNode = {
  id: string;
  cardDocumentId: string;
  frame: CanvasNodeFrame;
};

export type ProjectDocument = {
  id: string;
  name: string;
  createdAt: string;
  updatedAt: string;
  cardDocuments: CardDocument[];
  canvasNodes: CanvasNode[];
};

export type ProjectSummary = {
  id: string;
  name: string;
  createdAt: string;
  updatedAt: string;
  cardCount: number;
};

export type ProjectSaveRequest = {
  name: string;
  cardDocuments: CardDocument[];
  canvasNodes: CanvasNode[];
};

export type SkillDefinition = {
  id: string;
  name: string;
  description: string;
  origin: "built-in" | "user";
  visibility: "user" | "internal";
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
  dependsOn?: Record<string, string>;
  options: SkillArgumentOption[];
  order: number;
};

export type SkillRunStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

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
  streamId?: string;
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
  status: "succeeded" | "failed" | "needs_input" | "cancelled";
  responseText: string;
  skillRunIds: string[];
  cardIds: string[];
  conversationId?: string;
  question?: AgentQuestion;
  collectedArgs?: Record<string, string>;
  error?: string;
};

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

export type AgentChatMessage = {
  id: string;
  role: "user" | "assistant" | "system" | "skill" | "thinking" | "tool";
  text: string;
  status?: AgentRunStreamEvent["status"];
  skillName?: string;
  toolName?: string;
  toolCallId?: string;
  createdAt: number;
};
