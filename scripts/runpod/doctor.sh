#!/usr/bin/env bash

set -euo pipefail

if [[ $# -lt 1 ]]; then
  printf 'Usage: scripts/runpod/doctor.sh <pod-id>\n' >&2
  exit 1
fi

exec "$(dirname "${BASH_SOURCE[0]}")/remote.sh" "$1" loki-doctor
