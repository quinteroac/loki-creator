#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

config_file="${RUNPOD_CONFIG_FILE:-deploy/runpod/runpod.config.env}"
if [[ -f "$config_file" ]]; then
  # shellcheck disable=SC1090
  source "$config_file"
fi

derive_ghcr_image() {
  local remote_url
  remote_url="$(git config --get remote.origin.url || true)"
  if [[ "$remote_url" =~ github.com[:/]([^/]+)/([^/.]+)(\.git)?$ ]]; then
    printf 'ghcr.io/%s/%s' "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}"
    return
  fi
  return 1
}

image_repository="${GHCR_IMAGE:-}"
if [[ -z "$image_repository" ]]; then
  image_repository="$(derive_ghcr_image)" || {
    printf 'Set GHCR_IMAGE, for example ghcr.io/OWNER/loki-creator.\n' >&2
    exit 1
  }
fi

image_tag="${IMAGE_TAG:-$(git rev-parse --short HEAD)}"
image_ref="${image_repository}:${image_tag}"
base_image="${RUNPOD_BASE_IMAGE:-nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04}"

printf '[runpod] building %s\n' "$image_ref"
docker build \
  --build-arg "BASE_IMAGE=${base_image}" \
  -f deploy/runpod/Dockerfile \
  -t "$image_ref" \
  .

if [[ "${TAG_LATEST:-0}" == "1" && "$image_tag" != "latest" ]]; then
  docker tag "$image_ref" "${image_repository}:latest"
fi

if [[ "${PUSH:-1}" == "1" ]]; then
  printf '[runpod] pushing %s\n' "$image_ref"
  docker push "$image_ref"
  if [[ "${TAG_LATEST:-0}" == "1" && "$image_tag" != "latest" ]]; then
    docker push "${image_repository}:latest"
  fi
fi

printf '[runpod] image ready: %s\n' "$image_ref"
