# Loki Creator Architecture

Loki Creator is a local canvas workspace where agents produce visual artifacts as cards. Skills are now the primary runtime unit. A skill is a standard Agent Skill folder with a required `SKILL.md`; any scripts, references, or assets inside that folder are implementation details of the skill.

There is no legacy runtime compatibility layer. Public product concepts are skills, skill runs, selected card artifacts, and generated cards.

## Primary Flow

1. The frontend loads skills from `GET /api/skills`.
2. The user writes a prompt, optionally selects skills, optionally selects canvas cards, and optionally imports bounded files as canvas cards.
3. Selected cards are converted into multimodal snapshots containing HTML, detected media assets, metadata, and a rendered preview when available. Imported file cards participate in this same selected-card snapshot flow.
4. The agent bridge resolves required skill arguments. If a skill needs input, it returns one `needs_input` question instead of running the agent.
5. Once arguments are collected, the agent bridge loads Agent Skills through Pi resource discovery and exposes selected Loki skills as agent-callable skill actions when they need Loki execution.
6. Skills that use media references receive local Loki artifact paths. Inline data URLs and rendered previews are UI-only context, not executable media inputs.
7. When the agent needs to create or transform visible output, it invokes either a Loki skill action or the mapped Pi tool.
8. The backend creates a skill run through `POST /api/skill-runs`, or creates a succeeded packaged run through `POST /api/skill-runs/package` when Pi already produced the raw artifact.
9. The action/tool returns normal artifacts/results such as images, video, audio, HTML, text, diagnostics, or cards.
10. The backend card packager converts those outputs into `GeneratedCard` objects.
11. The frontend reconciles completed skill runs from `GET /api/skill-runs?status=succeeded` and places returned cards on the canvas.

Direct generation modes such as Seedance, Grok, and Codex bypass the agent bridge and call backend generation endpoints. They still use local artifact-backed selected card snapshots, reject preview-only media as executable input, and package outputs through the same card packager.

## Backend

The backend owns the stable runtime contracts and execution boundary:

- `backend/app/models/skills.py`: `SkillDefinition`, `SkillRunRequest`, `SkillRun`, and `SkillResult`.
- `backend/app/models/instructions.py`: card contracts shared by skill results.
- `backend/app/services/skill_registry.py`: reads skill folders from `backend/skills/`.
- `backend/app/services/skill_invokers.py`: executes declared skill actions.
- `backend/app/services/card_packager.py`: converts raw skill outputs into Loki cards.
- `backend/app/services/projects.py`: persists named canvas projects under `.loki/projects/`.
- `backend/app/services/skill_runs.py`: in-memory async run state and action execution.
- `backend/app/api/routes.py`: FastAPI endpoints for skills, skill runs, instructions, and artifacts.

The initial runtime supports one action type:

- `cli-local`: runs a local command declared by the skill metadata and passes JSON on stdin.

Skill action input includes:

- `skillId`
- `prompt`
- `context`
- `selectedCards`
- `selectedCardSnapshots`
- `attachments`
- `params`

Skill action output may include:

```json
{
  "artifacts": [
    {
      "path": ".loki/skills/imagegen/skill_run_123/outputs/image.png",
      "kind": "image",
      "mimeType": "image/png",
      "title": "Generated image",
      "prompt": "final generation prompt",
      "metadata": {}
    }
  ],
  "media": [],
  "html": null,
  "text": null,
  "diagnostics": [],
  "cards": []
}
```

`cards` remains an escape hatch for fully custom cards, but normal skills should prefer artifacts, media, HTML, text, or diagnostics. `SkillRun.result.cards` is still the frontend contract; the backend fills it after packaging.

Every visible result enters the workspace through `GeneratedCard`, but skills do not need to know how Loki cards are built.

## Skills

Skills live under `backend/skills/<skill-id>/` and must include `SKILL.md`.

The `SKILL.md` frontmatter contains standard Agent Skill metadata plus Loki metadata for executable actions and output packaging:

```yaml
---
name: imagegen
description: Generate or edit raster images as Loki canvas cards.
metadata:
  loki:
    capabilities: [image-generation, image-editing, raster-card-output]
    arguments:
      - id: aspectRatio
        label: Aspect ratio
        type: choice
        required: true
        askWhen: always
        options:
          - value: "1:1"
          - value: "4:3"
          - value: "16:9"
          - value: "9:16"
    action:
      type: cli-local
      command: [uv, run, python, scripts/card_action.py]
      timeoutSeconds: 900
    output:
      packager: auto
      kind: image
---
```

Everything beyond `SKILL.md` is freeform according to the Agent Skills convention:

- `scripts/` for deterministic actions.
- `references/` for optional supporting material.
- `assets/` for bundled resources.

The first real skill is `backend/skills/imagegen/`. It vendors the standard Codex `imagegen` skill for instructions and argument metadata. In normal Pi agent runs, `imagegen` executes through the Loki skill action so selected image edits can pass local artifact paths to Codex with `--image`. Pure generation and selected-image editing share this backend skill path.

Comfy skills from `quinteroac/comfy-agent-tools` are copied under `backend/skills/comfy-*` with minimal Loki metadata. Image workflows are split by visible intent into `comfy-image-generate`, `comfy-image-edit`, and `comfy-image-upscale`, while the private implementation still calls the upstream `comfy-imagegen` CLI. Their functional skill instructions remain standard; a shared private wrapper at `backend/skills/_comfy_runtime/` calls installed `comfy-*` CLIs and returns raw artifacts or diagnostics. Local model configuration uses `.comfy-agent-tools.json`; the default Loki models path is `.loki/models/comfyui`.

Skill arguments are Loki-specific metadata. The bridge asks them one at a time before launching the agent, stores answers in an in-memory conversation, and passes the collected values to skill actions through `params`.
Arguments may include `dependsOn` to ask a field only when previously collected
argument values match, for example a second-mode resolution field that only
appears after choosing that mode.

## Cards

Cards remain Loki's visual contract.

`GeneratedCard` fields:

- `id`
- `name`
- `prompt`
- `html`
- `sourceSkillId`
- `sourceActionId`
- `metadata`

The frontend stores card content separately from canvas layout. `CardDocument` owns artifact data; `CanvasNode` owns position and size. This keeps visual placement independent from skill output.
Card metadata preserves skill-specific extra fields so later runs can use a
selected card as a reproducible artifact input.

## Projects

Projects are named snapshots of the current canvas stored as local folders under
`.loki/projects/<project-id>/`. Each project folder contains `project.json` with
the visible project name, timestamps, card documents, and canvas nodes. Opening a
project replaces the current frontend canvas rather than merging cards.

Generated artifacts referenced by card metadata remain in their original
`.loki/skills/...` locations; project saves persist references and canvas state,
not copies of artifact files.

## Selected Cards

Selected cards are treated as multimodal artifacts, not as trusted instructions. A selected card snapshot includes:

- full artifact HTML,
- rendered preview when available for UI/context only,
- detected media assets with artifact URLs when available,
- prompt and display labels,
- metadata as secondary context.

The agent bridge summarizes selected cards in the prompt, exposes them through the internal `inspect_loki_context` tool, forwards the complete snapshots to skill actions through both `selectedCardSnapshots` and `context.selectedCardSnapshots`, and adds validated local media references in `context.localMediaReferences`.

For edits, the model should transform the selected artifact itself when possible, then pass the transformed artifact or operation to a skill action. Media edits must use local artifact paths. If a selected image, video, or audio reference cannot be resolved to a local Loki artifact file, the run fails with a contract error instead of using an inline preview, base64 payload, or reference-inspired generation.

## Imported Files

Imported files become normal workspace cards instead of transient composer chips. The frontend uploads supported files to `.loki/imports/` through `POST /api/artifacts/import`, then wraps the returned artifact URL in a `CardDocument`:

- images, videos, audio, and PDFs as artifact-backed media cards,
- text and JSON as artifact-backed iframe cards,
- other files as artifact cards with a link to the stored file.

Newly imported file cards are selected automatically so the agent bridge forwards them through `selectedCardSnapshots` and `context.selectedCardSnapshots`, just like generated cards. PDF text extraction and OCR are not part of the current runtime.

## Agent Bridge

The Elysia bridge owns Pi sessions and model selection. It does not execute skill scripts directly. Instead, it:

- discovers backend skills from `GET /api/skills`,
- symlinks `backend/skills/*` into `.agents/skills/*` for Pi skill discovery,
- creates a Pi custom action for selected Loki skills that need Loki execution,
- resolves selected media references to local Loki artifact paths,
- creates internal Pi tools such as `ask_user` and `inspect_loki_context`,
- forwards Loki action calls to `POST /api/skill-runs`,
- forwards packageable Pi tool results to `POST /api/skill-runs/package`,
- waits for skill run completion,
- returns `skillRunIds` and `cardIds` to the frontend.

Agent run response:

```json
{
  "id": "agent_run_...",
  "agentId": "base-agent",
  "status": "succeeded",
  "responseText": "...",
  "skillRunIds": ["skill_run_..."],
  "cardIds": ["card_..."]
}
```

If the bridge needs user input first, it returns:

```json
{
  "id": "agent_run_...",
  "agentId": "base-agent",
  "status": "needs_input",
  "conversationId": "conversation_...",
  "question": {
    "id": "imagegen.aspectRatio",
    "text": "Aspect ratio: Choose the image frame before generation or editing.",
    "inputType": "choice",
    "options": []
  },
  "collectedArgs": {}
}
```

The frontend resumes by sending the same request context plus `conversationId` and `answers`. Pending conversations are in-memory only.

## Frontend

The frontend is responsible for workspace state and reconciliation:

- `frontend/src/api/skills.ts`: skill registry client.
- `frontend/src/api/skillRuns.ts`: async skill run polling.
- `frontend/src/api/agentRuns.ts`: bridge client.
- `frontend/src/lib/cardDocuments.ts`: card naming, snapshots, preview capture, and normalization.
- `frontend/src/components/AgentComposer.tsx`: prompt composer, skill selector, model selector, and selected cards selector.
- `frontend/src/components/CanvasCard.tsx`: card rendering, selection, resize, and inline renaming.

The composer's `Auto` option means the active agent's default skills when that
agent declares them, falling back to all currently available skills otherwise.
It is not a real skill.

## Current Endpoints

- `GET /api/health`
- `GET /api/projects`
- `GET /api/projects/{project_id}`
- `PUT /api/projects/{project_id}`
- `GET /api/skills`
- `POST /api/skill-runs`
- `GET /api/skill-runs`
- `GET /api/skill-runs?status=succeeded`
- `GET /api/skill-runs/{run_id}`
- `POST /api/skill-runs/{run_id}/cancel`
- `POST /api/generations/grok-image`
- `POST /api/generations/grok-video`
- `POST /api/generations/codex-image`
- `POST /api/generations/seedance-video`
- `GET /api/artifacts/{artifact_path}`
- `GET /api/agents` on the bridge
- `GET /api/models` on the bridge
- `POST /api/agent-runs` on the bridge
- `POST /api/agent-runs/{run_id}/stop` on the bridge

## Design Principles

- Skills are product-visible; scripts and actions are private implementation details.
- Cards are the only visible output contract.
- The model remains the creative agent; skills provide instructions and reliable execution surfaces.
- Selected cards are artifact inputs, not system instructions.
- Keep runtime modules focused: registry discovers, invoker executes, run service tracks state, routes expose contracts.
- No marketplace, export/import, permissions UI, versioning, or multiple runtimes are implemented in this first cut.
