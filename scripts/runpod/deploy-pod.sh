#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

config_file="${RUNPOD_CONFIG_FILE:-deploy/runpod/runpod.config.env}"
if [[ -f "$config_file" ]]; then
  # shellcheck disable=SC1090
  source "$config_file"
fi

require() {
  local name="$1"
  local value="${!name:-}"
  if [[ -z "$value" ]]; then
    printf 'Missing required variable: %s\n' "$name" >&2
    exit 1
  fi
}

json_escape() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//$'\n'/\\n}"
  printf '%s' "$value"
}

env_json() {
  local entries=()
  local key
  for key in LOKI_MODEL_CAPABILITIES; do
    if [[ -n "${!key:-}" ]]; then
      entries+=("\"${key}\":\"$(json_escape "${!key}")\"")
    fi
  done
  printf '{'
  local IFS=,
  printf '%s' "${entries[*]}"
  printf '}'
}

command -v runpodctl >/dev/null 2>&1 || {
  printf 'runpodctl is required locally. Run runpodctl doctor first.\n' >&2
  exit 1
}

require GHCR_IMAGE
require RUNPOD_GPU_ID

image_tag="${IMAGE_TAG:-latest}"
image_ref="${GHCR_IMAGE}:${image_tag}"
pod_name="${RUNPOD_POD_NAME:-loki-creator}"
ports="${RUNPOD_PORTS:-3000/http,22/tcp}"
container_disk="${RUNPOD_CONTAINER_DISK_GB:-80}"
volume_mount="${RUNPOD_VOLUME_MOUNT_PATH:-/workspace}"
gpu_count="${RUNPOD_GPU_COUNT:-1}"
env_payload="$(env_json)"

args=(
  pod create
  --name "$pod_name"
  --gpu-id "$RUNPOD_GPU_ID"
  --gpu-count "$gpu_count"
  --image "$image_ref"
  --container-disk-in-gb "$container_disk"
  --volume-mount-path "$volume_mount"
  --ports "$ports"
  --ssh
)

if [[ -n "${RUNPOD_NETWORK_VOLUME_ID:-}" ]]; then
  args+=(--network-volume-id "$RUNPOD_NETWORK_VOLUME_ID")
else
  args+=(--volume-in-gb "${RUNPOD_VOLUME_GB:-200}")
fi

if [[ -n "${RUNPOD_DATACENTER_ID:-}" ]]; then
  args+=(--data-center-ids "$RUNPOD_DATACENTER_ID")
fi

if [[ -n "${RUNPOD_REGISTRY_AUTH_ID:-}" ]]; then
  args+=(--registry-auth-id "$RUNPOD_REGISTRY_AUTH_ID")
fi

if [[ "$env_payload" != "{}" ]]; then
  args+=(--env "$env_payload")
fi

printf '[runpod] creating Pod %s with image %s\n' "$pod_name" "$image_ref"
pod_output="$(runpodctl "${args[@]}")"
printf '%s\n' "$pod_output"

pod_id="${RUNPOD_POD_ID:-}"
if [[ -z "$pod_id" ]]; then
  pod_id="$(printf '%s\n' "$pod_output" | sed -nE 's/.*"id"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/p' | head -1)"
fi
if [[ -z "$pod_id" ]]; then
  pod_id="$(printf '%s\n' "$pod_output" | grep -Eo '[a-z0-9]{8,}' | head -1 || true)"
fi

if [[ -n "$pod_id" ]]; then
  printf '[runpod] Loki URL: https://%s-3000.proxy.runpod.net\n' "$pod_id"
  printf '[runpod] Run doctor: scripts/runpod/doctor.sh %s\n' "$pod_id"
else
  printf '[runpod] Pod created. Use runpodctl pod list to get the Pod ID.\n'
  printf '[runpod] Loki URL format: https://<pod-id>-3000.proxy.runpod.net\n'
fi
