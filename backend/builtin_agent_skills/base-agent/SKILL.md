---
name: base-agent
description: Default Loki agent behavior. Use inherited default skills for creative and tool-driven work without adding a specialized agent skill.
metadata:
  author: Loki
  version: "0.1.0"
  agentId: base-agent
  defaultModel: Loki Default
---

# Base Agent

Base Agent is the default Loki agent template. It does not add a specialized workflow of its own; it relies on inherited default skills and the tools exposed by the runtime.

## Guardrails

- Preserve the exact user prompt in `ToolInvocationRequest.prompt`.
- Use `params.toolPrompt` only for operational instructions to a tool.
- Put user-visible card output in explicit fields such as `outputText`, `title`, `subtitle`, `body`, and `footer`.
- Use Loki tools when the user asks to create or update canvas artifacts.
