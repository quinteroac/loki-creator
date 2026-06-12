#!/usr/bin/env bash

set -euo pipefail

export LOKI_REPO_DIR="${LOKI_REPO_DIR:-/opt/loki-creator}"
export LOKI_WORKSPACE_DIR="${LOKI_WORKSPACE_DIR:-/workspace}"
export LOKI_ARTIFACTS_ROOT="${LOKI_ARTIFACTS_ROOT:-${LOKI_WORKSPACE_DIR}/.loki}"
export LOKI_COMFY_MODELS_DIR="${LOKI_COMFY_MODELS_DIR:-${LOKI_ARTIFACTS_ROOT}/models/comfyui}"
export LOKI_COMFY_RUNTIME_DIR="${LOKI_COMFY_RUNTIME_DIR:-${LOKI_ARTIFACTS_ROOT}/runtime/comfy-agent-tools}"
export LOKI_COMFY_TOOL_DIR="${LOKI_COMFY_TOOL_DIR:-${LOKI_COMFY_RUNTIME_DIR}/tools}"
export LOKI_COMFY_TOOL_BIN_DIR="${LOKI_COMFY_TOOL_BIN_DIR:-${LOKI_COMFY_RUNTIME_DIR}/bin}"
export LOKI_RUNTIME_SECRETS_FILE="${LOKI_RUNTIME_SECRETS_FILE:-${LOKI_ARTIFACTS_ROOT}/runpod/runtime-secrets.env}"
export LOKI_BACKEND_URL="${LOKI_BACKEND_URL:-http://127.0.0.1:8001}"
export LOKI_AGENT_BRIDGE_PORT="${LOKI_AGENT_BRIDGE_PORT:-8787}"
export PATH="${LOKI_REPO_DIR}/backend/.venv/bin:${LOKI_COMFY_TOOL_BIN_DIR}:${LOKI_ARTIFACTS_ROOT}/runtime/bin:/root/.local/bin:/root/.bun/bin:/usr/local/bin:${PATH}"

log() {
  printf '[loki-runpod] %s\n' "$*"
}

warn() {
  printf '[loki-runpod] warning: %s\n' "$*" >&2
}

die() {
  printf '[loki-runpod] error: %s\n' "$*" >&2
  exit 1
}

ensure_linked_dir() {
  local source_path="$1"
  local target_path="$2"

  mkdir -p "$target_path"

  if [[ -L "$source_path" ]]; then
    local current_target
    current_target="$(readlink "$source_path")"
    if [[ "$current_target" == "$target_path" ]]; then
      return
    fi
    rm "$source_path"
  elif [[ -e "$source_path" ]]; then
    if [[ -d "$source_path" ]]; then
      cp -a -n "${source_path}/." "$target_path/" 2>/dev/null || true
      rm -rf "$source_path"
    else
      die "cannot link ${source_path}; it exists and is not a directory"
    fi
  fi

  ln -s "$target_path" "$source_path"
}

ensure_linked_file() {
  local source_path="$1"
  local target_path="$2"

  mkdir -p "$(dirname "$target_path")"

  if [[ -L "$source_path" ]]; then
    local current_target
    current_target="$(readlink "$source_path")"
    if [[ "$current_target" == "$target_path" ]]; then
      return
    fi
    rm "$source_path"
  elif [[ -e "$source_path" ]]; then
    if [[ -f "$source_path" ]]; then
      if [[ ! -f "$target_path" ]]; then
        cp -a "$source_path" "$target_path"
      fi
      rm -f "$source_path"
    else
      die "cannot link ${source_path}; it exists and is not a file"
    fi
  fi

  ln -s "$target_path" "$source_path"
}

bootstrap_persistent_paths() {
  mkdir -p \
    "$LOKI_WORKSPACE_DIR" \
    "$LOKI_ARTIFACTS_ROOT" \
    "$LOKI_COMFY_MODELS_DIR" \
    "$LOKI_COMFY_TOOL_DIR" \
    "$LOKI_COMFY_TOOL_BIN_DIR" \
    "${LOKI_ARTIFACTS_ROOT}/runpod" \
    "${LOKI_ARTIFACTS_ROOT}/runtime"
  ensure_linked_dir /root/.pi "${LOKI_WORKSPACE_DIR}/.pi"
  ensure_linked_dir /root/.codex "${LOKI_WORKSPACE_DIR}/.codex"
  ensure_linked_dir /root/.grok "${LOKI_WORKSPACE_DIR}/.grok"
  ensure_linked_dir /root/.gemini "${LOKI_WORKSPACE_DIR}/.gemini"
  ensure_linked_dir "${LOKI_REPO_DIR}/.loki" "$LOKI_ARTIFACTS_ROOT"
  ensure_linked_file "${LOKI_REPO_DIR}/.comfy-agent-tools.json" "${LOKI_WORKSPACE_DIR}/.comfy-agent-tools.json"
}

load_runtime_secrets() {
  if [[ -f "$LOKI_RUNTIME_SECRETS_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$LOKI_RUNTIME_SECRETS_FILE"
  fi
}

run_with_version() {
  local command_name="$1"

  if ! command -v "$command_name" >/dev/null 2>&1; then
    return 1
  fi

  printf '%s -> %s\n' "$command_name" "$(command -v "$command_name")"
  "$command_name" --version 2>/dev/null \
    || "$command_name" version 2>/dev/null \
    || "$command_name" --help 2>/dev/null | sed -n '1p' \
    || true
}

http_ok() {
  local url="$1"
  curl -fsS --max-time 3 "$url" >/dev/null 2>&1
}
