import { mkdir, readlink, symlink } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { cors } from "@elysiajs/cors";
import {
  AuthStorage,
  createAgentSession,
  DefaultResourceLoader,
  defineTool,
  getAgentDir,
  ModelRegistry,
  SessionManager,
} from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { Elysia, t } from "elysia";

type LokiAgent = {
  id: string;
  name: string;
  description: string;
  defaultModel?: string | null;
};

type LokiModel = {
  id: string;
  provider: string;
  name: string;
  label: string;
};

type LokiTool = {
  id: string;
  slug: string;
  name: string;
  description: string;
  invocationVisibility: "frontend" | "internal";
};

type LokiToolJob = {
  id: string;
  toolId: string;
  status: "queued" | "running" | "succeeded" | "failed";
  result?: {
    cards?: Array<{ id: string; name: string; sourceToolId?: string | null }>;
  } | null;
  error?: string | null;
};

type AgentRunRequest = {
  prompt: string;
  agentId?: string | null;
  model: string;
  tools: string[];
  selectedCards: string[];
  context: Record<string, unknown>;
};

type AgentRunResponse = {
  id: string;
  agentId: string;
  status: "succeeded" | "failed";
  responseText: string;
  toolJobIds: string[];
  cardIds: string[];
  error?: string;
};

type BrowserExtensionResponse = {
  ok: boolean;
  action: string;
  url: string | null;
  title: string | null;
  observation: string;
  screenshotBase64?: string;
  error?: string;
};

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, "..");
const backendApiUrl = process.env.LOKI_BACKEND_URL ?? "http://127.0.0.1:8000";
const port = Number(process.env.LOKI_AGENT_BRIDGE_PORT ?? 8787);
const allowedOriginPattern = /^https?:\/\/(localhost|127\.0\.0\.1|0\.0\.0\.0|192\.168\.\d+\.\d+):\d+$/;
const authStorage = AuthStorage.create();
const modelRegistry = ModelRegistry.create(authStorage);
let activeBrowserExtension: { id: string; ws: { send: (data: string) => unknown } } | null = null;
const pendingBrowserExtensionCommands = new Map<
  string,
  {
    resolve: (result: BrowserExtensionResponse) => void;
    reject: (error: Error) => void;
    timeout: ReturnType<typeof setTimeout>;
  }
>();

const agents: LokiAgent[] = [
  {
    id: "base-agent",
    name: "Base Agent",
    description: "Default Loki agent behavior without an additional specialized skill.",
    defaultModel: "Loki Default",
  },
  {
    id: "tool-builder",
    name: "Tool Builder",
    description: "Built-in agent specialized in designing Loki-compatible tools.",
    defaultModel: "Loki Default",
  },
];

function listAvailableModels(): LokiModel[] {
  modelRegistry.refresh();

  return modelRegistry.getAvailable().map((model) => ({
    id: model.id,
    provider: model.provider,
    name: model.name,
    label: `${model.name} (${model.provider})`,
  }));
}

function resolveSelectedModel(label: string) {
  modelRegistry.refresh();

  return modelRegistry
    .getAvailable()
    .find((model) => `${model.name} (${model.provider})` === label || model.name === label || model.id === label);
}

async function ensureToolBuilderSkillSymlink() {
  const target = resolve(repoRoot, "backend/builtin_agent_skills/tool-builder");
  const link = resolve(repoRoot, ".agents/skills/tool-builder");

  await mkdir(dirname(link), { recursive: true });

  try {
    const existingTarget = await readlink(link);
    if (resolve(dirname(link), existingTarget) === target || existingTarget === target) {
      return;
    }
  } catch {
    await symlink(target, link, "dir");
  }
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

async function listFrontendTools(): Promise<LokiTool[]> {
  return requestJson<LokiTool[]>(`${backendApiUrl}/api/tools?include_internal=true`);
}

function normalizeToolName(value: string) {
  return value.trim().toLowerCase().replace(/\s+/g, "-");
}

function toPiToolName(tool: LokiTool) {
  return `loki_${tool.id.replace(/[^a-zA-Z0-9_]/g, "_")}`;
}

function selectToolsForAgent(availableTools: LokiTool[], selectedTools: string[]) {
  const normalizedSelected = selectedTools.map(normalizeToolName);
  const isAuto = normalizedSelected.length === 0 || normalizedSelected.includes("auto");
  const visibleTools = availableTools.filter((tool) => tool.invocationVisibility === "frontend");
  const eligibleTools = visibleTools.filter((tool) => tool.id !== "tool-creator");

  if (isAuto) {
    return eligibleTools.filter((tool) => tool.id !== "auto");
  }

  return eligibleTools.filter((tool) => {
    const candidates = [tool.id, tool.slug, tool.name].map(normalizeToolName);
    return candidates.some((candidate) => normalizedSelected.includes(candidate));
  });
}

async function runBrowserExtensionAction(params: Record<string, unknown>): Promise<BrowserExtensionResponse> {
  if (!activeBrowserExtension) {
    throw new Error("No browser extension is connected.");
  }

  const id = crypto.randomUUID();

  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      pendingBrowserExtensionCommands.delete(id);
      reject(new Error(`Timed out waiting for browser extension command ${id}.`));
    }, Number(params.timeoutMs ?? 60000));

    pendingBrowserExtensionCommands.set(id, { resolve, reject, timeout });
    activeBrowserExtension?.ws.send(JSON.stringify({ type: "command", id, params }));
  });
}

async function waitForToolJob(jobId: string): Promise<LokiToolJob> {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    const job = await requestJson<LokiToolJob>(`${backendApiUrl}/api/tool-jobs/${jobId}`);
    if (job.status === "succeeded" || job.status === "failed") {
      return job;
    }

    await Bun.sleep(500);
  }

  throw new Error(`Timed out waiting for tool job ${jobId}`);
}

type LokiToolParams = {
  prompt: string;
  outputText: string;
  title?: string;
  subtitle?: string;
  body?: string;
  footer?: string;
};

async function runLokiTool(tool: LokiTool, toolParams: LokiToolParams, request: AgentRunRequest) {
  const createdJob = await requestJson<LokiToolJob>(`${backendApiUrl}/api/tool-jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      toolId: tool.id,
      prompt: request.prompt,
      context: {
        ...request.context,
        agentId: request.agentId ?? "base-agent",
        model: request.model,
      },
      selectedCards: request.selectedCards,
      params: {
        model: request.model,
        toolPrompt: toolParams.prompt,
        outputText: toolParams.outputText,
        title: toolParams.title,
        subtitle: toolParams.subtitle,
        body: toolParams.body,
        footer: toolParams.footer,
      },
    }),
  });

  const completedJob = await waitForToolJob(createdJob.id);
  const cards = completedJob.result?.cards ?? [];

  return {
    job: completedJob,
    cardIds: cards.map((card) => card.id),
  };
}

function createLokiPiTool(tool: LokiTool, request: AgentRunRequest, runState: { toolJobIds: string[]; cardIds: string[] }) {
  return defineTool({
    name: toPiToolName(tool),
    label: tool.name,
    description: `${tool.description} Use this to create Loki canvas cards. Keep prompt as operational instructions and put the user-visible card content in outputText or structured visible fields.`,
    promptSnippet: `${tool.name}: ${tool.description}. Use prompt for tool instructions. Use outputText/title/subtitle/body/footer for visible card content.`,
    parameters: Type.Object({
      prompt: Type.String({
        description:
          "Operational instruction for the Loki tool. This is not user-visible card copy and must not be rendered as the final output.",
      }),
      outputText: Type.String({
        description:
          "User-visible content for the generated card. Do not include tool instructions, implementation notes, or reasoning.",
      }),
      title: Type.Optional(Type.String({ description: "Optional user-visible card title." })),
      subtitle: Type.Optional(Type.String({ description: "Optional user-visible card subtitle." })),
      body: Type.Optional(Type.String({ description: "Optional user-visible card body." })),
      footer: Type.Optional(Type.String({ description: "Optional user-visible card footer or note." })),
    }),
    async execute(_toolCallId, params) {
      const { job, cardIds } = await runLokiTool(tool, params, request);
      runState.toolJobIds.push(job.id);
      runState.cardIds.push(...cardIds);

      if (job.status === "failed") {
        return {
          content: [{ type: "text", text: `Loki tool ${tool.name} failed: ${job.error ?? "unknown error"}` }],
          details: { jobId: job.id, status: job.status, error: job.error },
        };
      }

      return {
        content: [
          {
            type: "text",
            text: `Loki tool ${tool.name} completed. Job ${job.id} created cards: ${cardIds.join(", ") || "none"}.`,
          },
        ],
        details: { jobId: job.id, status: job.status, cardIds },
      };
    },
  });
}

function createBrowserPiTool(tool: LokiTool) {
  return defineTool({
    name: toPiToolName(tool),
    label: tool.name,
    description:
      "Control the user's connected browser extension. Use it for real browser tabs with the user's existing sessions.",
    promptSnippet:
      "Browser Tool: open URLs, inspect active tabs, extract page state, click selectors, type text, press keys, capture screenshots, and extract page images.",
    parameters: Type.Object({
      action: Type.String({
        description: "One of open_url, get_active_tab, extract_state, click, type, press, screenshot, extract_images.",
      }),
      url: Type.Optional(Type.String({ description: "URL for open_url." })),
      selector: Type.Optional(Type.String({ description: "CSS selector for click/type." })),
      text: Type.Optional(Type.String({ description: "Text for type." })),
      key: Type.Optional(Type.String({ description: "Key name for press, such as Enter or Tab." })),
      clear: Type.Optional(Type.Boolean({ description: "Whether type should clear the field first." })),
      timeoutMs: Type.Optional(Type.Number({ description: "Optional timeout in milliseconds." })),
    }),
    async execute(_toolCallId, params) {
      try {
        const result = await runBrowserExtensionAction(params);

        return {
          content: [
            {
              type: "text",
              text: `Browser extension completed ${result.action}. URL: ${result.url ?? "n/a"}. Observation: ${result.observation}`,
            },
          ],
          details: result,
        };
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown browser extension error";
        return {
          content: [{ type: "text", text: `Browser extension failed: ${message}` }],
          details: { status: "failed", error: message },
        };
      }
    },
  });
}

async function createResourceLoader(agentId: string) {
  const loader = new DefaultResourceLoader({
    cwd: repoRoot,
    agentDir: getAgentDir(),
    skillsOverride: (current) => {
      if (agentId !== "tool-builder") {
        return current;
      }

      return {
        skills: current.skills.filter((skill) => skill.name === "tool-builder"),
        diagnostics: current.diagnostics,
      };
    },
  });

  await loader.reload();
  return loader;
}

function buildAgentPrompt(request: AgentRunRequest, exposedTools: LokiTool[]) {
  const agentId = request.agentId ?? "base-agent";
  const toolNames = exposedTools.map((tool) => `${tool.name} (${toPiToolName(tool)})`).join(", ") || "none";
  const skillHint = agentId === "tool-builder" ? "\nUse the tool-builder skill for behavior and constraints." : "";

  return `User request:
${request.prompt}

Loki context:
- agentId: ${agentId}
- selected model label: ${request.model}
- exposed Loki tools: ${toolNames}
- selected canvas cards: ${request.selectedCards.join(", ") || "none"}

Use the exposed Loki tools when the request requires producing canvas cards. Return a concise final response for the UI response panel.${skillHint}`;
}

async function runAgent(request: AgentRunRequest): Promise<AgentRunResponse> {
  const id = `agent_run_${crypto.randomUUID().replaceAll("-", "")}`;
  const agentId = request.agentId || "base-agent";
  const runState = { toolJobIds: [] as string[], cardIds: [] as string[] };
  const responseChunks: string[] = [];

  let session: Awaited<ReturnType<typeof createAgentSession>>["session"] | undefined;

  try {
    const availableTools = await listFrontendTools();
    const selectedTools = selectToolsForAgent(availableTools, request.tools);
    const browserTool = availableTools.find((tool) => tool.id === "browser-tool");
    const browserToolAvailable = Boolean(browserTool && activeBrowserExtension);
    const exposedToolsForPrompt = [
      ...selectedTools,
      ...(browserTool && browserToolAvailable ? [browserTool] : []),
    ];
    const customTools = [
      ...selectedTools.map((tool) => createLokiPiTool(tool, request, runState)),
      ...(browserTool && browserToolAvailable ? [createBrowserPiTool(browserTool)] : []),
    ];
    const resourceLoader = await createResourceLoader(agentId);
    const model = resolveSelectedModel(request.model);

    const result = await createAgentSession({
      cwd: repoRoot,
      authStorage,
      modelRegistry,
      model,
      resourceLoader,
      sessionManager: SessionManager.inMemory(repoRoot),
      noTools: "builtin",
      customTools,
      tools: customTools.map((tool) => tool.name),
    });
    session = result.session;

    session.subscribe((event) => {
      if (event.type === "message_update" && event.assistantMessageEvent.type === "text_delta") {
        responseChunks.push(event.assistantMessageEvent.delta);
      }
    });

    await session.prompt(buildAgentPrompt(request, exposedToolsForPrompt), { source: "api" });

    return {
      id,
      agentId,
      status: "succeeded",
      responseText: responseChunks.join("").trim() || "Agent run completed.",
      toolJobIds: runState.toolJobIds,
      cardIds: runState.cardIds,
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown Pi agent error";
    return {
      id,
      agentId,
      status: "failed",
      responseText: `Agent run failed: ${message}`,
      toolJobIds: runState.toolJobIds,
      cardIds: runState.cardIds,
      error: message,
    };
  } finally {
    session?.dispose();
  }
}

await ensureToolBuilderSkillSymlink();

const app = new Elysia()
  .use(
    cors({
      origin: ({ headers }) => {
        const origin = headers.get("origin");
        return Boolean(origin && allowedOriginPattern.test(origin));
      },
      methods: ["GET", "POST", "OPTIONS"],
      allowedHeaders: ["Content-Type"],
      preflight: true,
    }),
  )
  .get("/api/health", () => ({ status: "ok" }))
  .get("/api/agents", () => agents)
  .get("/api/models", () => listAvailableModels())
  .get("/api/browser-extension/status", () => ({
    connected: Boolean(activeBrowserExtension),
    extensionId: activeBrowserExtension?.id ?? null,
  }))
  .post(
    "/api/browser-extension/actions",
    async ({ body }) => runBrowserExtensionAction(body),
    {
      body: t.Record(t.String(), t.Unknown()),
    },
  )
  .ws("/api/browser-extension/connect", {
    open(ws) {
      const extensionId = crypto.randomUUID();
      activeBrowserExtension = { id: extensionId, ws };
      ws.send(JSON.stringify({ type: "connected", extensionId }));
      console.log(`Browser extension connected: ${extensionId}`);
    },
    message(ws, message) {
      let parsed: { type?: string; id?: string; result?: BrowserExtensionResponse; error?: string };

      try {
        parsed = typeof message === "string" ? JSON.parse(message) : message;
      } catch {
        return;
      }

      if (parsed.type === "hello") {
        return;
      }

      if ((parsed.type === "result" || parsed.type === "error") && parsed.id) {
        const pending = pendingBrowserExtensionCommands.get(parsed.id);
        if (!pending) return;

        clearTimeout(pending.timeout);
        pendingBrowserExtensionCommands.delete(parsed.id);

        if (parsed.type === "error") {
          pending.reject(new Error(parsed.error ?? parsed.result?.error ?? "Browser extension command failed."));
          return;
        }

        if (parsed.result) {
          pending.resolve(parsed.result);
        }
      }
    },
    close(ws) {
      if (activeBrowserExtension?.ws === ws) {
        console.log(`Browser extension disconnected: ${activeBrowserExtension.id}`);
        activeBrowserExtension = null;

        for (const [id, pending] of pendingBrowserExtensionCommands) {
          clearTimeout(pending.timeout);
          pending.reject(new Error("Browser extension disconnected."));
          pendingBrowserExtensionCommands.delete(id);
        }
      }
    },
  })
  .post(
    "/api/agent-runs",
    async ({ body }) => runAgent(body),
    {
      body: t.Object({
        prompt: t.String({ minLength: 1 }),
        agentId: t.Optional(t.Nullable(t.String())),
        model: t.String({ minLength: 1 }),
        tools: t.Array(t.String()),
        selectedCards: t.Array(t.String()),
        context: t.Record(t.String(), t.Unknown()),
      }),
    },
  )
  .listen(port);

console.log(`Loki agent bridge listening on http://127.0.0.1:${app.server?.port}`);
