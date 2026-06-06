import { cors } from "@elysiajs/cors";
import { Elysia, t } from "elysia";
import {
  agents,
  allowedOriginPattern,
  createAgentRunEventStream,
  ensureSkillSymlinks,
  listAvailableModelsAsync,
  port,
  runAgent,
  stopAgentRun,
} from "./src/agentRunner";

await ensureSkillSymlinks();

const selectedCardSnapshotSchema = t.Object({
  id: t.String(),
  name: t.String(),
  displayTitle: t.String(),
  prompt: t.String(),
  html: t.String(),
  preview: t.Optional(
    t.Object({
      source: t.Literal("rendered-preview"),
      mimeType: t.Optional(t.String()),
      dataUrl: t.Optional(t.String()),
      width: t.Optional(t.Number()),
      height: t.Optional(t.Number()),
      omitted: t.Optional(t.Boolean()),
      reason: t.Optional(t.String()),
    }),
  ),
  mediaAssets: t.Optional(t.Array(
    t.Object({
      kind: t.Union([
        t.Literal("image"),
        t.Literal("video"),
        t.Literal("audio"),
        t.Literal("iframe"),
        t.Literal("source"),
        t.Literal("canvas"),
      ]),
      src: t.Optional(t.String()),
      dataUrl: t.Optional(t.String()),
      mimeType: t.Optional(t.String()),
      alt: t.Optional(t.String()),
      width: t.Optional(t.Number()),
      height: t.Optional(t.Number()),
      omitted: t.Optional(t.Boolean()),
      reason: t.Optional(t.String()),
    }),
  )),
  sourceSkillId: t.Optional(t.Nullable(t.String())),
  sourceActionId: t.Optional(t.Nullable(t.String())),
  metadata: t.Optional(t.Nullable(t.Record(t.String(), t.Unknown()))),
});

const attachmentSchema = t.Object({
  id: t.String(),
  name: t.String(),
  mimeType: t.String(),
  size: t.Number(),
  kind: t.Union([
    t.Literal("image"),
    t.Literal("video"),
    t.Literal("audio"),
    t.Literal("text"),
    t.Literal("json"),
    t.Literal("pdf"),
    t.Literal("artifact"),
  ]),
  dataUrl: t.Optional(t.String()),
  src: t.Optional(t.String()),
  artifactUrl: t.Optional(t.String()),
  text: t.Optional(t.String()),
  omitted: t.Optional(t.Boolean()),
  reason: t.Optional(t.String()),
});

const agentRunRequestSchema = t.Object({
  prompt: t.String({ minLength: 1 }),
  agentId: t.Optional(t.Nullable(t.String())),
  model: t.String({ minLength: 1 }),
  skills: t.Array(t.String()),
  selectedCards: t.Array(t.String()),
  streamId: t.Optional(t.String()),
  conversationId: t.Optional(t.String()),
  answers: t.Optional(t.Record(t.String(), t.String())),
  collectedArgs: t.Optional(t.Record(t.String(), t.String())),
  selectedCardSnapshots: t.Optional(t.Array(selectedCardSnapshotSchema)),
  attachments: t.Optional(t.Array(attachmentSchema)),
  context: t.Record(t.String(), t.Unknown()),
});

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
  .get("/api/models", () => listAvailableModelsAsync())
  .get("/api/agent-runs/:id/events", ({ params }) => createAgentRunEventStream(params.id))
  .post("/api/agent-runs/:id/stop", ({ params }) => stopAgentRun(params.id))
  .post("/api/agent-runs", async ({ body }) => runAgent(body), {
    body: agentRunRequestSchema,
  })
  .listen(port);

console.log(`Loki agent bridge listening on http://127.0.0.1:${app.server?.port}`);
