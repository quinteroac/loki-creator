#!/usr/bin/env bash

set -euo pipefail

if [[ $# -lt 2 ]]; then
  printf 'Usage: scripts/runpod/models.sh <pod-id> list|show|validate|download [args...]\n' >&2
  exit 1
fi

pod_id="$1"
shift

exec "$(dirname "${BASH_SOURCE[0]}")/remote.sh" "$pod_id" loki-models "$@"
