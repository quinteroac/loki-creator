# Loki Creator Architecture

## Current Shape

Loki Creator is split into a React frontend and a FastAPI backend.

- Frontend: React + Vite running with Bun in `frontend/`.
- Backend: FastAPI running with uv in `backend/`.
- Agent bridge: ElysiaJS + Pi SDK running with Bun in `agent-bridge/`.
- The main user experience is a dark creative workspace with a dotted canvas and a bottom agent composer.
- The frontend does not execute tools directly. It sends intent to the backend/agent layer and reconciles async tool job results.

The current backend stores jobs in memory. This is intentional for the first version and should be treated as a development runtime, not durable production storage.

## Frontend Responsibilities

The frontend owns presentation and local workspace state:

- Load frontend-visible tools from `GET /api/tools`.
- Load available agents from the agent bridge.
- Let the user select tools and selected canvas cards in the composer.
- Submit prompts as agent runs through the agent bridge.
- Poll completed tool jobs and merge returned cards into the canvas.
- Show the latest textual agent response in a right-side response popover.
- Render each generated card from HTML.

Important modules:

- `frontend/src/App.jsx`: workspace orchestration and state composition.
- `frontend/src/components/AgentComposer.jsx`: prompt composer, popovers, selected tools/cards controls.
- `frontend/src/components/AgentResponsePanel.jsx`: right-side response popover for the latest agent run.
- `frontend/src/components/CanvasStage.jsx`: canvas surface.
- `frontend/src/components/CanvasCard.jsx`: card rendering using HTML-in-Canvas when available, iframe fallback otherwise.
- `frontend/src/api/agentRuns.js`: agent bridge client.
- `frontend/src/api/toolJobs.js`: async job client.
- `frontend/src/api/tools.js`: tools registry client.

## Backend Responsibilities

The backend owns contracts, tool registration, invocation, and async job state:

- Expose tool contracts.
- Create and run async tool jobs.
- Normalize tool output into HTML canvas cards.
- Keep built-in tools separate from future user-created tools.
- Keep user-created tool manifests in `backend/user_tools/`.

Important modules:

- `backend/app/models/agents.py`: base agent and agent-skill contracts for future user-created agents.
- `backend/app/models/tools.py`: tool, package, job, invocation, and result contracts.
- `backend/app/models/instructions.py`: current instruction and generated-card contracts.
- `backend/app/services/builtin_agents.py`: built-in agent definitions such as `Tool Builder`.
- `backend/app/services/builtin_tools.py`: built-in tool contracts.
- `backend/app/services/tool_registry.py`: hybrid registry for built-ins and user manifests.
- `backend/app/services/tool_invokers.py`: invoker abstraction for built-in, HTTP, and CLI tools.
- `backend/app/services/tool_jobs.py`: in-memory async job store and runner.
- `backend/app/api/routes.py`: API endpoints.

## Tool Execution Flow

1. User or agent creates a tool job through `POST /api/tool-jobs`.
2. Backend stores a `queued` job in memory.
3. Backend runs the job in the background.
4. `ToolRegistry` resolves the requested tool by id, slug, or name.
5. `ToolInvokerFactory` chooses the invoker by `sourceType`.
6. The tool returns `ToolResult`.
7. `ToolResult.cards` contains HTML cards.
8. Frontend polls `GET /api/tool-jobs?status=succeeded`.
9. New job cards are merged into the canvas and the first generated card becomes selected.

This polling/reconciliation behavior is not a temporary bridge. It is the current async contract between the backend/agent/tool runtime and the frontend workspace.

## Card Rendering

The backend returns card HTML as the primary visual output. A card has:

- `id`
- `name`
- `prompt`
- `html`
- `sourceToolId`

`CanvasCard` attempts to render HTML into a real `<canvas>` using the experimental HTML-in-Canvas API:

- `<canvas layoutsubtree>`
- `drawElementImage(...)`

If the browser does not support this API, the same HTML is rendered inside an iframe fallback. This is expected in Firefox and most browsers without the Chromium flag enabled.

## Tool Registry

The registry is hybrid:

- Built-in tools are Python contracts in `backend/app/services/builtin_tools.py`.
- Built-in manifest tools can live in `backend/builtin_tools/<tool-id>/tool.json`.
- User-created tools will be local JSON manifests in `backend/user_tools/*.json`.
- User-created folder tools can live in `backend/user_tools/<tool-id>/tool.json`.
- Both are exposed as `ToolDefinition`.

Built-in tools may be:

- `invocationVisibility: "frontend"`: visible/selectable in the UI.
- `invocationVisibility: "internal"`: available to the agent/backend only.

`GET /api/tools` returns only frontend-visible tools.  
`GET /api/tools?include_internal=true` includes internal tools such as `Browser Tool`.

Node/React tools use the existing `cli-local` runtime. They receive `ToolInvocationRequest` JSON on stdin and must write a `ToolResult` JSON object to stdout. React tools render to self-contained HTML, typically through server rendering, and place that HTML in `GeneratedCard.html`; the frontend does not mount or hydrate tool-provided React components in this version.

Folder-based tool manifests get a runtime `workingDirectory` derived from their containing folder. Built-in manifest tools are always normalized to `origin: "built-in"` and `exportable: false`; user manifest tools are normalized to `origin: "user"` and `exportable: true`.

Tools must separate operational instructions from visible output. `ToolInvocationRequest.prompt` preserves the exact original user request for card metadata. `params.toolPrompt` is only a runtime instruction and must not be rendered into card HTML. Visible card content should come from explicit fields such as `params.outputText`, `params.title`, `params.subtitle`, `params.body`, `params.footer`, or structured provider output.

## Agent Contracts

Agents are the base template for future user-created agents and built-in agents. The first contract-only version defines:

- `AgentDefinition`: identity, display metadata, `defaultModel`, inherited `defaultSkills`, and `agentSkillId`.
- `AgentSkillDefinition`: the agent-specific skill referenced by an agent.
- `AgentSkillStep`: an ordered canvas workflow step with tool, input card, output card, and prompt references.

`defaultModel` represents the agent's preferred model for future execution, but it is not used by the runtime yet. `defaultSkills` represents skills inherited by every agent, but starts empty in this first version. `agentSkillId` expresses the planned 1:1 relationship between an agent and its primary agent skill.

Agent skills adopt the Agent Skills standard: a skill is a folder with a required `SKILL.md` file containing YAML frontmatter and Markdown instructions. Built-in agent skills live in `backend/builtin_agent_skills/`, for example `backend/builtin_agent_skills/tool-builder/SKILL.md`. Future user-created agent skills should live in an equivalent user-owned location such as `backend/user_agent_skills/`.

`AgentDefinition.agentSkillId` points to the standard skill folder name, not to a JSON manifest. JSON remains reserved for user-created tool manifests.

`Tool Builder` is a built-in agent defined in code and backed by the standard `tool-builder` Agent Skill folder. Its helper tools are built-in internal `ToolDefinition` entries:

- `tool-requirements-analyzer`
- `tool-contract-drafter`
- `tool-preview-card-builder`

Creation from canvas elements is intentionally reserved for a future implementation. There are no agent endpoints, registries, frontend flows, or `ToolJobService` integration in this version.

## Agent Bridge

The frontend calls an ElysiaJS bridge for agent runs instead of invoking Pi SDK in the browser. The bridge owns Pi SDK sessions, loads agent skills, exposes Loki tools as Pi custom tools, and delegates actual tool execution back to FastAPI through `POST /api/tool-jobs`.

Bridge endpoints:

- `GET /api/health`
- `GET /api/agents`
- `POST /api/agent-runs`

The bridge creates `.agents/skills/tool-builder` as a development symlink to `backend/builtin_agent_skills/tool-builder` when it starts. The backend skill folder remains the source of truth; `.agents/` is a runtime discovery path and is ignored by git.

Agent run responses return text and references:

- `responseText`: shown in the right-side response popover.
- `toolJobIds`: jobs created by Pi custom tool calls.
- `cardIds`: cards created by those jobs.

Cards continue to flow through the existing tool-job polling contract.

## Browser Extension

`browser-tool` is an internal agent capability backed by a user-installed browser extension, not by Selenium/WebDriver. The extension connects outbound to the agent bridge over WebSocket, so the hosted bridge does not need direct network access to the user's machine.

The extension has separate Chrome and Firefox builds generated from shared source in `browser-extension/`. It operates on the user's real browser tabs and existing sessions. Initial actions are intentionally small:

- `open_url`
- `get_active_tab`
- `extract_state`
- `click`
- `type`
- `press`
- `screenshot`
- `extract_images`

The agent bridge exposes `browser-tool` to Pi only when an extension is connected. Direct browser results are returned to the agent as tool details and text observations. Extracted image data URLs can be passed through the existing `image` tool to produce normal Loki canvas cards.

## ComfyUI Runtime Preparation

Loki prepares for local/cloud generation tools through `comfy-diffusion`, a Python package that exposes ComfyUI runtime capabilities without running the ComfyUI web server. The dependency lives in the FastAPI backend because backend tool jobs own generation, tool invocation, and card normalization.

The integration is intentionally diagnostic-only for now:

- `ComfyDiffusionService` is the backend boundary for lazy `comfy-diffusion` imports, runtime checks, and model directory resolution.
- `LOKI_COMFY_MODELS_DIR` can override the model directory; the default is a local `.loki/comfy-models` path ignored by git.
- `comfy-runtime-check` is an internal built-in tool that reports runtime readiness as a normal Loki card.
- No image, video, audio, or model-download Comfy tools are implemented yet.

Future Comfy tools should keep the existing async flow: `POST /api/tool-jobs`, registry resolution, invoker execution, `ComfyDiffusionService`, and `ToolResult.cards`. Pipeline outputs from `comfy-diffusion` should be converted to `GeneratedCard` HTML, with the exact user prompt preserved in the card description.

## Export And Import Preparation

The contract includes `ToolPackage` for future export/import:

- `manifestVersion`
- `tool`
- `assets`
- `secretsRequired`
- `integrity`

Secrets must never be exported as values. Packages may reference required secret names, such as `OPENAI_API_KEY` or `RUNPOD_TOKEN`.

Current behavior:

- Built-in tools are not exportable.
- User-created tools will be exportable once import/install is implemented.
- `POST /api/tools/import` exists as a placeholder and returns `501`.

## API Surface

Current backend endpoints:

- `GET /api/health`
- `GET /api/tools`
- `GET /api/tools?include_internal=true`
- `GET /api/tools/{tool_id}/export`
- `POST /api/tools/import`
- `POST /api/tool-jobs`
- `GET /api/tool-jobs`
- `GET /api/tool-jobs?status=succeeded`
- `GET /api/tool-jobs/{job_id}`
- `POST /api/instructions`

Current agent bridge endpoints:

- `GET /api/health`
- `GET /api/agents`
- `POST /api/agent-runs`
- `GET /api/browser-extension/status`
- `POST /api/browser-extension/actions`
- `WS /api/browser-extension/connect`

`POST /api/instructions` is legacy-compatible and currently returns one generated card. The preferred architecture for agent/tool execution is the async tool-job flow.

## Architectural Decisions

- Use async jobs for tool execution, even while jobs are in memory.
- Keep the frontend passive with respect to tool execution; it requests work and reconciles results.
- Use HTML as the primary card output format.
- Support HTML-in-Canvas progressively with iframe fallback.
- Separate tool contracts from tool implementations.
- Define agent contracts before implementing user-created agent persistence, canvas creation, or execution.
- Store agent skills as Agent Skills standard folders with `SKILL.md`, not as JSON manifests.
- Keep Pi SDK on the server-side agent bridge; do not expose Pi credentials or SDK runtime in React.
- Prepare for user tool export/import with manifests and package contracts before adding UI.
- Keep SOLID boundaries: schemas, registry, invokers, services, routes, and UI components remain separate.
