---
name: tool-builder
description: Designs Loki-compatible tools. Use when a user wants to create, plan, validate, package, or preview a new tool for the Loki Creator runtime.
metadata:
  author: Loki
  version: "0.1.0"
  agentId: tool-builder
  defaultModel: Loki Default
---

# Tool Builder

Tool Builder helps create tools that follow Loki Creator contracts. Use this skill when the user asks to design, generate, review, package, or preview a tool.

## Workflow

1. Analyze the requested tool.
   - Identify the user's intent, expected inputs, expected outputs, permissions, runtime source type, provider requirements, and any secrets.
   - Keep the tool focused on one responsibility.

2. Draft the tool contract.
   - Produce a `ToolDefinition`-compatible draft.
   - When packaging is needed, wrap the draft in a `ToolPackage`-compatible shape with `manifestVersion`, `tool`, `assets`, `secretsRequired`, and `integrity`.
   - Never include secret values. Reference secret names only.

3. Build the preview output.
   - Return operational output through `ToolResult.cards`.
   - Each card must be a `GeneratedCard` with `id`, `name`, `prompt`, `html`, and `sourceToolId`.
   - If the structured draft cannot yet travel as first-class data, render it inside a review card as formatted JSON.

## Loki Contracts

Tool inputs must remain compatible with `ToolInvocationRequest`:

- `toolId`
- `prompt`
- `context`
- `selectedCards`
- `params`

Tool execution output must remain compatible with `ToolResult`:

- `cards`

Each generated card must remain compatible with `GeneratedCard`:

- `id`
- `name`
- `prompt`
- `html`
- `sourceToolId`

## Built-In Tools Used By This Skill

- `tool-requirements-analyzer`: turns a user request into tool requirements.
- `tool-contract-drafter`: turns requirements into a Loki-compatible tool/package draft.
- `tool-preview-card-builder`: turns the draft into a canvas review card.

## Guardrails

- Prefer built-in source type when the tool is implemented by Loki.
- Require explicit permissions for network, filesystem, environment variables, and allowed commands.
- Keep generated HTML self-contained and safe to render in a canvas card.
- Keep user-created tool manifests exportable, but built-in tools non-exportable.
- Preserve the existing async tool-job contract until the runtime supports richer structured outputs.
