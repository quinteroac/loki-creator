# Loki Tool Contracts

Tool Builder must produce drafts that match the backend models in `app.models.tools`.

## ToolDefinition

Required identity and display fields:

- `id`
- `slug`
- `name`
- `description`
- `version`
- `author`
- `origin`

Runtime and access fields:

- `sourceType`
- `invocationVisibility`
- `runtime`
- `permissions`
- `configuration`

Input/output separation:

- `ToolInvocationRequest.prompt` is the exact original user request.
- `params.toolPrompt` is an operational instruction for the tool runtime only.
- Visible card content must use explicit params such as `outputText`, `title`, `subtitle`, `body`, and `footer`, or structured provider output.
- `GeneratedCard.html` must not render `params.toolPrompt`, planning notes, implementation instructions, or model reasoning.

Schema and packaging fields:

- `capabilities`
- `inputSchema`
- `outputSchema`
- `exportable`

## ToolPackage

Use `ToolPackage` when a draft needs to be installable or exportable:

- `manifestVersion`
- `tool`
- `assets`
- `secretsRequired`
- `integrity`

Do not include secret values in packages. Use secret names in `secretsRequired` or `permissions.envVars`.
