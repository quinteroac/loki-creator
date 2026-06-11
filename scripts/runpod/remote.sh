#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/runpod/remote.sh <pod-id> [command...]

If no command is provided, opens an interactive SSH shell.
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" || $# -lt 1 ]]; then
  usage
  exit $([[ $# -lt 1 ]] && printf 1 || printf 0)
fi

pod_id="$1"
shift

command -v runpodctl >/dev/null 2>&1 || {
  printf 'runpodctl is required locally. Run runpodctl doctor first.\n' >&2
  exit 1
}

ssh_info="$(runpodctl ssh info "$pod_id")"
ssh_command="$(printf '%s\n' "$ssh_info" | sed -nE 's/.*"sshCommand"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/p' | head -1)"
if [[ -z "$ssh_command" ]]; then
  ssh_command="$(printf '%s\n' "$ssh_info" | grep -Eo 'ssh .+' | head -1 || true)"
fi
if [[ -z "$ssh_command" ]]; then
  printf 'Could not find sshCommand in runpodctl output:\n%s\n' "$ssh_info" >&2
  exit 1
fi

eval "ssh_parts=(${ssh_command})"

if [[ $# -eq 0 ]]; then
  exec "${ssh_parts[@]}"
fi

remote_command="$(printf '%q ' "$@")"
exec "${ssh_parts[@]}" -t -- "$remote_command"
