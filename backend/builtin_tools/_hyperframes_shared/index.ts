import { existsSync, readdirSync, statSync } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export type ToolInvocationRequest = {
  prompt: string;
  params?: Record<string, unknown>;
};

export type GeneratedCard = {
  id: string;
  name: string;
  prompt: string;
  html: string;
  sourceToolId: string;
  metadata?: CardMetadata;
};

export type ToolResult = {
  cards: GeneratedCard[];
};

export type CardMetadata = {
  kind?: "generic" | "image" | "video" | "audio" | "diagnostic" | "artifact" | "interactive";
  title?: string;
  description?: string;
  thumbnailUrl?: string;
  artifactUrl?: string;
  createdAt?: string;
  tags?: string[];
  capabilities?: string[];
  preferredAspectRatio?: "1:1" | "4:3" | "16:9" | "auto";
  playableMedia?: boolean;
};

export type CommandResult = {
  ok: boolean;
  command: string[];
  cwd?: string;
  exitCode: number | null;
  stdout: string;
  stderr: string;
};

const here = dirname(fileURLToPath(import.meta.url));
export const backendDir = resolve(here, "../..");
export const repoRoot = resolve(backendDir, "..");
export const hyperframesRoot = resolve(repoRoot, ".loki/hyperframes");
export const hyperframesProjectsDir = resolve(hyperframesRoot, "projects");
export const hyperframesRendersDir = resolve(hyperframesRoot, "renders");
const artifactRoot = resolve(repoRoot, ".loki");
const backendPublicUrl = (process.env.LOKI_BACKEND_PUBLIC_URL ?? process.env.LOKI_BACKEND_URL ?? "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);

export async function runTool(
  sourceToolId: string,
  handler: (payload: ToolInvocationRequest) => Promise<ToolResult>,
) {
  try {
    const input = await new Response(Bun.stdin.stream()).text();
    const payload = JSON.parse(input) as ToolInvocationRequest;
    const result = await handler(payload);
    process.stdout.write(JSON.stringify(result));
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    process.stdout.write(
      JSON.stringify({
        cards: [
          createCard({
            prompt: "Hyperframes tool failed",
            sourceToolId,
            name: "Hyperframes Error",
            title: "Hyperframes tool failed",
            body: message,
            tone: "error",
            metadata: { kind: "diagnostic", tags: ["hyperframes", "error"] },
          }),
        ],
      }),
    );
  }
}

export async function ensureHyperframesDirs() {
  await mkdir(hyperframesProjectsDir, { recursive: true });
  await mkdir(hyperframesRendersDir, { recursive: true });
}

export function getString(params: Record<string, unknown> | undefined, key: string, fallback = "") {
  const value = params?.[key];
  return typeof value === "string" && value.trim() ? value.trim() : fallback;
}

export function getNumber(params: Record<string, unknown> | undefined, key: string, fallback: number) {
  const value = params?.[key];
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() && Number.isFinite(Number(value))) return Number(value);
  return fallback;
}

export function getBoolean(params: Record<string, unknown> | undefined, key: string, fallback: boolean) {
  const value = params?.[key];
  if (typeof value === "boolean") return value;
  return fallback;
}

export function getStringList(
  params: Record<string, unknown> | undefined,
  key: string,
  fallback: string[] = [],
) {
  const value = params?.[key];
  if (Array.isArray(value)) return value.filter((item): item is string => typeof item === "string");
  if (typeof value === "string" && value.trim()) return value.split(",").map((item) => item.trim()).filter(Boolean);
  return fallback;
}

export function resolveProjectDir(params: Record<string, unknown> | undefined) {
  const projectId = slugify(getString(params, "projectId", "default"));
  return {
    projectId,
    projectDir: resolve(hyperframesProjectsDir, projectId),
  };
}

export function slugify(value: string) {
  return (
    value
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 64) || "hyperframes-project"
  );
}

export async function runCommand(command: string[], options: { cwd?: string; timeoutMs?: number } = {}) {
  const process = Bun.spawn(command, {
    cwd: options.cwd,
    stdout: "pipe",
    stderr: "pipe",
  });

  const timeoutMs = options.timeoutMs ?? 120_000;
  const timeout = setTimeout(() => {
    process.kill();
  }, timeoutMs);

  const [stdout, stderr, exitCode] = await Promise.all([
    new Response(process.stdout).text(),
    new Response(process.stderr).text(),
    process.exited,
  ]);
  clearTimeout(timeout);

  return {
    ok: exitCode === 0,
    command,
    cwd: options.cwd,
    exitCode,
    stdout,
    stderr,
  };
}

export function hyperframesCommand(args: string[]) {
  return ["bun", "x", "hyperframes", ...args];
}

export function commandSummary(result: CommandResult) {
  return [
    `Command: ${result.command.join(" ")}`,
    result.cwd ? `CWD: ${result.cwd}` : "",
    `Exit: ${result.exitCode}`,
    result.stdout ? `STDOUT:\n${result.stdout}` : "",
    result.stderr ? `STDERR:\n${result.stderr}` : "",
  ]
    .filter(Boolean)
    .join("\n\n");
}

export function createCard(input: {
  prompt: string;
  sourceToolId: string;
  name: string;
  title: string;
  body: string;
  details?: string;
  imageDataUrl?: string;
  videoUrl?: string;
  artifactPath?: string;
  tone?: "ok" | "warn" | "error";
  metadata?: CardMetadata;
}) {
  const toneColor =
    input.tone === "error" ? "#ff5a3d" : input.tone === "warn" ? "#e9429f" : "#245cff";
  const details = input.details
    ? `<details style="margin-top:16px;color:rgba(255,255,255,.68);font-size:12px;line-height:1.5;"><summary>Details</summary><pre style="white-space:pre-wrap;overflow:auto;max-height:128px;">${escapeHtml(input.details)}</pre></details>`
    : "";
  const image = input.imageDataUrl
    ? `<img src="${escapeHtml(input.imageDataUrl)}" alt="${escapeHtml(input.title)}" style="display:block;width:100%;max-height:260px;object-fit:contain;border-radius:14px;background:#111111;margin-top:16px;" />`
    : "";
  const video = input.videoUrl
    ? `<video src="${escapeHtml(input.videoUrl)}" controls autoplay muted loop playsinline style="display:block;width:100%;max-height:260px;object-fit:contain;border-radius:14px;background:#111111;margin-top:16px;"></video>`
    : "";
  const artifact = input.artifactPath
    ? `<p style="margin:16px 0 0;color:rgba(255,255,255,.68);font-size:12px;line-height:1.5;word-break:break-word;">${escapeHtml(input.artifactPath)}</p>`
    : "";

  return {
    id: `card_${Date.now()}_${Math.random().toString(16).slice(2)}`,
    name: input.name,
    prompt: input.prompt,
    sourceToolId: input.sourceToolId,
    metadata: {
      kind: "artifact",
      title: input.title,
      description: input.body,
      artifactUrl: input.artifactPath,
      thumbnailUrl: input.imageDataUrl,
      preferredAspectRatio: input.videoUrl ? "16:9" : "1:1",
      playableMedia: Boolean(input.videoUrl),
      tags: ["hyperframes"],
      ...input.metadata,
    },
    html: `<section style="display:grid;width:100%;height:100%;background:#111111;color:#ffffff;font-family:DM Sans,Inter,Arial,sans-serif;overflow:hidden;">
  <article style="display:grid;grid-template-rows:auto 1fr;gap:18px;width:100%;height:100%;padding:28px;background:#202020;">
    <header>
      <span style="display:inline-block;width:42px;height:4px;border-radius:999px;background:${toneColor};"></span>
      <h1 style="margin:16px 0 0;font-size:28px;line-height:1.16;">${escapeHtml(input.title)}</h1>
    </header>
    <div style="min-height:0;overflow:auto;">
      <p style="margin:0;color:rgba(255,255,255,.76);font-size:14px;line-height:1.55;white-space:pre-wrap;">${escapeHtml(input.body)}</p>
      ${image}
      ${video}
      ${artifact}
      ${details}
    </div>
  </article>
</section>`,
  } satisfies GeneratedCard;
}

export function escapeHtml(value: string) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export async function readImageAsDataUrl(path: string) {
  const buffer = await readFile(path);
  return `data:image/png;base64,${Buffer.from(buffer).toString("base64")}`;
}

export async function writeTextFile(path: string, content: string) {
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, content, "utf-8");
}

export function fileExists(path: string) {
  return existsSync(path);
}

function artifactUrl(path: string) {
  const relativePath = relative(artifactRoot, path);
  if (relativePath.startsWith("..")) return undefined;

  const encodedPath = relativePath
    .split("/")
    .map((segment) => encodeURIComponent(segment))
    .join("/");

  return `${backendPublicUrl}/api/artifacts/${encodedPath}`;
}

function projectIndexPath(projectDir: string) {
  return resolve(projectDir, "index.html");
}

function missingProjectResult(
  payload: ToolInvocationRequest,
  sourceToolId: string,
  name: string,
  projectId: string,
  projectDir: string,
) {
  return {
    cards: [
      createCard({
        prompt: payload.prompt,
        sourceToolId,
        name,
        title: "Hyperframes project is not ready",
        body: `Project ${projectId} does not have an index.html yet. Create the project and write the composition before running this step.`,
        artifactPath: projectDir,
        tone: "warn",
        metadata: { kind: "diagnostic", tags: ["hyperframes", "missing-project"] },
      }),
    ],
  } satisfies ToolResult;
}

export async function runtimeCheck(payload: ToolInvocationRequest, sourceToolId: string) {
  await ensureHyperframesDirs();
  const node = await runCommand(["node", "-v"], { cwd: repoRoot, timeoutMs: 10_000 });
  const ffmpeg = await runCommand(["ffmpeg", "-version"], { cwd: repoRoot, timeoutMs: 10_000 });
  const hyperframes = await runCommand(hyperframesCommand(["--version"]), { cwd: repoRoot, timeoutMs: 30_000 });
  const browser = await runCommand(hyperframesCommand(["browser", "ensure"]), {
    cwd: repoRoot,
    timeoutMs: 120_000,
  });
  const nodeMajor = Number((node.stdout.trim() || node.stderr.trim()).replace(/^v/, "").split(".")[0]);
  const ok = nodeMajor >= 22 && ffmpeg.ok && hyperframes.ok && browser.ok;

  return {
    cards: [
      createCard({
        prompt: payload.prompt,
        sourceToolId,
        name: "Hyperframes Runtime Check",
        title: ok ? "Hyperframes runtime ready" : "Hyperframes runtime needs attention",
        body: [
          `Node: ${(node.stdout || node.stderr).trim() || "unknown"}`,
          `FFmpeg: ${firstLine(ffmpeg.stdout || ffmpeg.stderr) || "unknown"}`,
          `Hyperframes: ${(hyperframes.stdout || hyperframes.stderr).trim() || "unknown"}`,
          `Browser: ${browser.ok ? "ready" : "not ready"}`,
        ].join("\n"),
        details: [commandSummary(node), commandSummary(ffmpeg), commandSummary(hyperframes), commandSummary(browser)].join(
          "\n\n---\n\n",
        ),
        tone: ok ? "ok" : "warn",
        metadata: { kind: "diagnostic", tags: ["hyperframes", "runtime"] },
      }),
    ],
  } satisfies ToolResult;
}

export async function projectCreate(payload: ToolInvocationRequest, sourceToolId: string) {
  await ensureHyperframesDirs();
  const params = payload.params ?? {};
  const projectId = slugify(getString(params, "projectId", getString(params, "title", "hyperframes-project")));
  const example = getString(params, "example", "blank");
  const projectDir = resolve(hyperframesProjectsDir, projectId);
  const command = hyperframesCommand([
    "init",
    projectDir,
    "--non-interactive",
    "--example",
    example,
    "--skip-skills",
    "--skip-transcribe",
    "--no-open",
  ]);
  const result = await runCommand(command, { cwd: repoRoot, timeoutMs: 120_000 });

  return {
    cards: [
      createCard({
        prompt: payload.prompt,
        sourceToolId,
        name: "Hyperframes Project",
        title: result.ok ? "Hyperframes project created" : "Project creation failed",
        body: result.ok
          ? `Project ${projectId} is ready for composition authoring.`
          : `Could not create project ${projectId}.`,
        artifactPath: projectDir,
        details: commandSummary(result),
        tone: result.ok ? "ok" : "error",
        metadata: { kind: "artifact", tags: ["hyperframes", "project"] },
      }),
    ],
  } satisfies ToolResult;
}

export async function compositionWrite(payload: ToolInvocationRequest, sourceToolId: string) {
  await ensureHyperframesDirs();
  const params = payload.params ?? {};
  const { projectId, projectDir } = resolveProjectDir(params);
  const compositionPath = getString(params, "compositionPath", "index.html");
  const html = getString(params, "html", getString(params, "outputText"));
  if (!html) throw new Error("Missing params.html or params.outputText for composition content.");

  const target = resolve(projectDir, compositionPath);
  await writeTextFile(target, html);
  const validationIssues = validateCompositionHtml(html);
  const hasIssues = validationIssues.length > 0;

  return {
    cards: [
      createCard({
        prompt: payload.prompt,
        sourceToolId,
        name: "Hyperframes Composition",
        title: hasIssues ? "Composition written with issues" : "Composition written",
        body: hasIssues
          ? `Updated ${compositionPath} in project ${projectId}, but the composition is missing required Hyperframes contract fields:\n${validationIssues.map((issue) => `- ${issue}`).join("\n")}`
          : `Updated ${compositionPath} in project ${projectId}.`,
        artifactPath: target,
        tone: hasIssues ? "warn" : "ok",
        metadata: { kind: "artifact", tags: ["hyperframes", "composition"] },
      }),
    ],
  } satisfies ToolResult;
}

export async function registryAdd(payload: ToolInvocationRequest, sourceToolId: string) {
  await ensureHyperframesDirs();
  const params = payload.params ?? {};
  const { projectId, projectDir } = resolveProjectDir(params);
  const item = getString(params, "item", getString(params, "name"));
  if (!item) throw new Error("Missing params.item for hyperframes registry add.");

  const result = await runCommand(hyperframesCommand(["add", item, "--dir", projectDir, "--json", "--no-clipboard"]), {
    cwd: repoRoot,
    timeoutMs: 120_000,
  });

  return {
    cards: [
      createCard({
        prompt: payload.prompt,
        sourceToolId,
        name: "Hyperframes Registry Add",
        title: result.ok ? "Registry item installed" : "Registry install failed",
        body: result.ok ? `Installed ${item} into project ${projectId}.` : `Could not install ${item}.`,
        artifactPath: projectDir,
        details: commandSummary(result),
        tone: result.ok ? "ok" : "error",
        metadata: { kind: "artifact", tags: ["hyperframes", "registry"] },
      }),
    ],
  } satisfies ToolResult;
}

export async function lintProject(payload: ToolInvocationRequest, sourceToolId: string) {
  const { projectId, projectDir } = resolveProjectDir(payload.params);
  if (!fileExists(projectIndexPath(projectDir))) {
    return missingProjectResult(payload, sourceToolId, "Hyperframes Lint", projectId, projectDir);
  }

  const result = await runCommand(hyperframesCommand(["lint", projectDir, "--json"]), {
    cwd: repoRoot,
    timeoutMs: 120_000,
  });

  return diagnosticResult(payload, sourceToolId, "Hyperframes Lint", projectId, projectDir, result);
}

export async function inspectProject(payload: ToolInvocationRequest, sourceToolId: string) {
  const { projectId, projectDir } = resolveProjectDir(payload.params);
  if (!fileExists(projectIndexPath(projectDir))) {
    return missingProjectResult(payload, sourceToolId, "Hyperframes Inspect", projectId, projectDir);
  }

  const at = getString(payload.params, "at");
  const args = ["inspect", projectDir, "--json"];
  if (at) args.push("--at", at);
  const result = await runCommand(hyperframesCommand(args), { cwd: repoRoot, timeoutMs: 180_000 });

  return diagnosticResult(payload, sourceToolId, "Hyperframes Inspect", projectId, projectDir, result);
}

export async function snapshotProject(payload: ToolInvocationRequest, sourceToolId: string) {
  const params = payload.params ?? {};
  const { projectId, projectDir } = resolveProjectDir(params);
  if (!fileExists(projectIndexPath(projectDir))) {
    return missingProjectResult(payload, sourceToolId, "Hyperframes Snapshot", projectId, projectDir);
  }

  const frames = getNumber(params, "frames", 3);
  const at = getString(params, "at");
  const args = ["snapshot", projectDir, "--frames", String(frames)];
  if (at) args.push("--at", at);
  const result = await runCommand(hyperframesCommand(args), { cwd: repoRoot, timeoutMs: 180_000 });
  const snapshot = findNewestFile(projectDir, [".png"]);
  const imageDataUrl = snapshot ? await readImageAsDataUrl(snapshot) : undefined;

  return {
    cards: [
      createCard({
        prompt: payload.prompt,
        sourceToolId,
        name: "Hyperframes Snapshot",
        title: result.ok ? "Snapshot captured" : "Snapshot failed",
        body: result.ok ? `Captured snapshot frames for project ${projectId}.` : `Snapshot failed for ${projectId}.`,
        artifactPath: snapshot ?? projectDir,
        imageDataUrl,
        details: commandSummary(result),
        tone: result.ok ? "ok" : "error",
        metadata: { kind: "image", preferredAspectRatio: "1:1", tags: ["hyperframes", "snapshot"] },
      }),
    ],
  } satisfies ToolResult;
}

export async function renderProject(payload: ToolInvocationRequest, sourceToolId: string) {
  await ensureHyperframesDirs();
  const params = payload.params ?? {};
  const { projectId, projectDir } = resolveProjectDir(params);
  if (!fileExists(projectIndexPath(projectDir))) {
    return missingProjectResult(payload, sourceToolId, "Hyperframes Render", projectId, projectDir);
  }

  const format = getString(params, "format", "mp4");
  const quality = getString(params, "quality", "draft");
  const fps = getString(params, "fps", "30");
  const output = resolve(hyperframesRendersDir, `${projectId}-${Date.now()}.${format === "png-sequence" ? "frames" : format}`);
  const args = ["render", projectDir, "--quality", quality, "--fps", fps, "--format", format, "--output", output];
  const variables = getString(params, "variables");
  if (variables) args.push("--variables", variables);
  const result = await runCommand(hyperframesCommand(args), { cwd: repoRoot, timeoutMs: 600_000 });

  return {
    cards: [
      createCard({
        prompt: payload.prompt,
        sourceToolId,
        name: "Hyperframes Render",
        title: result.ok ? "Render complete" : "Render failed",
        body: result.ok ? `Rendered ${projectId} as ${format}.` : `Could not render ${projectId}.`,
        artifactPath: output,
        videoUrl: result.ok && format !== "png-sequence" ? artifactUrl(output) : undefined,
        details: commandSummary(result),
        tone: result.ok ? "ok" : "error",
        metadata: {
          kind: "video",
          artifactUrl: artifactUrl(output),
          playableMedia: result.ok && format !== "png-sequence",
          preferredAspectRatio: "16:9",
          tags: ["hyperframes", "render"],
        },
      }),
    ],
  } satisfies ToolResult;
}

export async function tts(payload: ToolInvocationRequest, sourceToolId: string) {
  await ensureHyperframesDirs();
  const params = payload.params ?? {};
  const { projectId, projectDir } = resolveProjectDir(params);
  const text = getString(params, "text", getString(params, "outputText", payload.prompt));
  const voice = getString(params, "voice", "af_heart");
  const output = resolve(projectDir, "assets", getString(params, "output", "narration.wav"));
  await mkdir(dirname(output), { recursive: true });
  const result = await runCommand(hyperframesCommand(["tts", text, "--voice", voice, "--output", output]), {
    cwd: projectDir,
    timeoutMs: 300_000,
  });

  return artifactCommandResult(payload, sourceToolId, "Hyperframes TTS", projectId, output, result);
}

export async function transcribe(payload: ToolInvocationRequest, sourceToolId: string) {
  const params = payload.params ?? {};
  const { projectId, projectDir } = resolveProjectDir(params);
  const input = getString(params, "input", resolve(projectDir, "assets", "narration.wav"));
  const model = getString(params, "model", "small");
  const language = getString(params, "language");
  const args = ["transcribe", input, "--model", model];
  if (language) args.push("--language", language);
  const result = await runCommand(hyperframesCommand(args), { cwd: projectDir, timeoutMs: 300_000 });
  const transcript = findNewestFile(projectDir, [".json"]) ?? resolve(projectDir, "transcript.json");

  return artifactCommandResult(payload, sourceToolId, "Hyperframes Transcribe", projectId, transcript, result);
}

export async function removeBackground(payload: ToolInvocationRequest, sourceToolId: string) {
  const params = payload.params ?? {};
  const { projectId, projectDir } = resolveProjectDir(params);
  const input = getString(params, "input");
  if (!input) throw new Error("Missing params.input for background removal.");
  const output = resolve(projectDir, "assets", getString(params, "output", "subject.webm"));
  const quality = getString(params, "quality", "balanced");
  await mkdir(dirname(output), { recursive: true });
  const result = await runCommand(hyperframesCommand(["remove-background", input, "--quality", quality, "--output", output]), {
    cwd: projectDir,
    timeoutMs: 600_000,
  });

  return artifactCommandResult(payload, sourceToolId, "Hyperframes Remove Background", projectId, output, result);
}

function diagnosticResult(
  payload: ToolInvocationRequest,
  sourceToolId: string,
  name: string,
  projectId: string,
  projectDir: string,
  result: CommandResult,
) {
  return {
    cards: [
      createCard({
        prompt: payload.prompt,
        sourceToolId,
        name,
        title: result.ok ? `${name} passed` : `${name} found issues`,
        body: result.ok ? `Project ${projectId} passed ${name.toLowerCase()}.` : `Project ${projectId} needs attention.`,
        artifactPath: projectDir,
        details: commandSummary(result),
        tone: result.ok ? "ok" : "warn",
        metadata: { kind: "diagnostic", tags: ["hyperframes", "diagnostic"] },
      }),
    ],
  } satisfies ToolResult;
}

function artifactCommandResult(
  payload: ToolInvocationRequest,
  sourceToolId: string,
  name: string,
  projectId: string,
  artifactPath: string,
  result: CommandResult,
) {
  return {
    cards: [
      createCard({
        prompt: payload.prompt,
        sourceToolId,
        name,
        title: result.ok ? `${name} complete` : `${name} failed`,
        body: result.ok ? `Generated artifact for project ${projectId}.` : `Could not generate artifact for ${projectId}.`,
        artifactPath,
        details: commandSummary(result),
        tone: result.ok ? "ok" : "error",
        metadata: { kind: name.includes("TTS") ? "audio" : "artifact", tags: ["hyperframes", "artifact"] },
      }),
    ],
  } satisfies ToolResult;
}

function validateCompositionHtml(html: string) {
  const issues: string[] = [];
  const lowerHtml = html.toLowerCase();

  for (const attribute of [
    "data-composition-id",
    "data-start",
    "data-duration",
    "data-width",
    "data-height",
    "data-track-index",
  ]) {
    if (!lowerHtml.includes(attribute)) {
      issues.push(attribute);
    }
  }

  if (!html.includes("window.__timelines")) {
    issues.push("window.__timelines registration");
  }

  return issues;
}

function findNewestFile(root: string, extensions: string[]) {
  if (!existsSync(root)) return null;
  const files: string[] = [];
  const visit = (dir: string) => {
    for (const entry of readdirSync(dir)) {
      const path = resolve(dir, entry);
      const stat = statSync(path);
      if (stat.isDirectory()) visit(path);
      else if (extensions.some((extension) => path.endsWith(extension))) files.push(path);
    }
  };
  visit(root);
  return files.sort((a, b) => statSync(b).mtimeMs - statSync(a).mtimeMs)[0] ?? null;
}

function firstLine(value: string) {
  return value.split(/\r?\n/).find((line) => line.trim())?.trim() ?? "";
}
