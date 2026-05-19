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
