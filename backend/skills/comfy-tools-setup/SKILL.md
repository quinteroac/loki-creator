---
name: comfy-tools-setup
description: Bootstrap and validate the comfy-agent-tools Python CLIs for agent use. Use when the user asks to setup, install, update, or diagnose comfy-agent-tools; when a required CLI such as comfy-imagegen, comfy-imagedescribe, comfy-videogen, comfy-musicgen, or comfy-models is missing; or before another comfy skill runs a CLI on a new machine.
metadata:
  loki:
    visibility: internal
    capabilities: [setup, diagnostics, comfy]
    action:
      type: cli-local
      command: [python3, ../_comfy_runtime/comfy_action.py]
      timeoutSeconds: 0
    output:
      packager: auto
      kind: diagnostic
---

# comfy-tools-setup

Use this skill to install or validate the Python tools that back the
`comfy-agent-tools` skills. The public install flow is skills-first; the agent
installs the CLIs only when they are needed.

## Detect Mode

First determine whether you are inside the `comfy-agent-tools` repo:

```bash
test -f pyproject.toml && test -d comfy_agent_tools && test -d skills
```

If true, prefer repo/dev commands:

```bash
uv sync --extra dev
uv run comfy-models validate
```

If not in this repo, use globally installed tools from `uv tool`.

## Install Tools

Check for `uv` before installing:

```bash
command -v uv
```

If `uv` is missing, ask the user to install `uv` first. Do not install package
managers or system packages without explicit user approval.

Install the CLIs:

```bash
uv tool install git+https://github.com/quinteroac/comfy-agent-tools
```

Upgrade the CLIs to the current upstream revision:

```bash
uv tool install --force git+https://github.com/quinteroac/comfy-agent-tools@70bc48bedf17e3cd36253581e44fe9af83a21156
```

Validate that the expected commands exist:

```bash
command -v comfy-imagegen
command -v comfy-imagedescribe
command -v comfy-videogen
command -v comfy-musicgen
command -v comfy-models
```

Validate that `comfy-imagegen` is new enough for Loki's supported image
profiles:

```bash
comfy-imagegen --help | grep krea2-generate
comfy-imagegen --help | grep rtx-upscale
comfy-imagegen krea2-generate --help | grep -- --profile
```

If `krea2-generate`, its `--profile` option, or `rtx-upscale` is missing,
reinstall the current upstream revision with the command above. Validate H3
support with `comfy-videogen --help | grep minimax-h3` and confirm that
`minimax-h3-t2v`, `minimax-h3-i2v`, and `minimax-h3-r2v` are present.
The MiniMax H3 R2V runner must preserve ComfyUI's normal VRAM mode and release
conditioning models before loading the diffusion model. Do not add a global
`COMFY_VRAM_MODE=low` override to work around H3 memory errors.
MiniMax H3 also supports the `--sageattention` and `--easycache` flags; ask
whether to enable each one before generation when the user is running H3.

## Model Config

If `.comfy-agent-tools.json` is missing in the current project, ask the user
where they want to store or use ComfyUI model files for these tools. Do not pick
`.loki/models/comfyui` automatically; mention it only as an example.

After the user provides a path, initialize config and set that exact path:

```bash
comfy-models init
comfy-models set-models-dir <models_dir>
```

Then validate:

```bash
comfy-models validate
comfy-models show
```

In repo/dev mode, prefix CLI commands with `uv run`, for example:

```bash
uv run comfy-models init
uv run comfy-models set-models-dir <models_dir>
uv run comfy-models validate
```

If `.comfy-agent-tools.json` already exists, respect its configured `models_dir`
and do not ask again unless validation fails or the user wants to change it.

If validation reports missing models, switch to `comfy-model-downloader` when the
user is trying to run a supported built-in capability. Use
`comfy-model-onboarding` for custom checkpoints, changed defaults, or unsupported
profiles.

`comfy-imagedescribe` uses a HuggingFace directory, not a single safetensors
file. The expected default model folder is
`LLM/Qwen-VL/Qwen3-VL-2B-Instruct` under the configured models directory. Do not
auto-download it; if missing, tell the user to place `Qwen/Qwen3-VL-2B-Instruct`
there.

## Skill Installation

Users install the agent guidance first:

```bash
npx skills add quinteroac/comfy-agent-tools
```

After that, the skills can bootstrap the Python tools on demand.
