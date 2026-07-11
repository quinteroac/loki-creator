import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import type { LokiAgent } from "./types";

const __dirname = dirname(fileURLToPath(import.meta.url));

export const repoRoot = resolve(__dirname, "../..");
export const backendApiUrl = process.env.LOKI_BACKEND_URL ?? "http://127.0.0.1:8001";
export const port = Number(process.env.LOKI_AGENT_BRIDGE_PORT ?? 8787);
export const allowedOriginPattern = /^https?:\/\/(localhost|127\.0\.0\.1|0\.0\.0\.0|192\.168\.\d+\.\d+):\d+$/;
export const preferredAgentModelId = "gpt-5.4-mini";

export const directPiToolBySkillId: Record<string, string> = {};

export const directPiToolSkillByToolName = new Map(
  Object.entries(directPiToolBySkillId).map(([skillId, toolName]) => [toolName, skillId]),
);

export const agents: LokiAgent[] = [
  {
    id: "base-agent",
    name: "Base Agent",
    description: "Default Loki agent behavior for creating canvas cards through skills.",
    defaultModel: "GPT-5.4 mini (openai-codex)",
    defaultSkills: ["imagegen"],
  },
  {
    id: "video-director",
    name: "Video Director",
    description: "Interactive production director for planning, generating, reviewing, editing, assembling, and post-producing video workflows.",
    defaultModel: "GPT-5.4 mini (openai-codex)",
    defaultSkills: [
      "video-director-os",
      "imagegen",
      "comfy-image-generate",
      "comfy-krea2-image",
      "comfy-image-edit",
      "comfy-videogen",
      "comfy-videoedit",
      "comfy-s2vidgen",
      "comfy-motion-track-control",
      "comfy-musicgen",
      "ltx-seed-seeker",
      "wan-seed-seeker",
      "ffmpeg-video-join",
      "ffmpeg-video-audio-mux",
      "ffmpeg-audio-split",
      "hyperframes-text-video",
      "media-cleanup",
      "grok-imagine-video",
      "openrouter-seedance-video",
      "comfy-tools-setup",
      "comfy-model-onboarding",
      "comfy-model-downloader",
      "comfy-lora-onboarding",
    ],
  },
];
