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
ssh_command=""
if command -v jq >/dev/null 2>&1; then
  ssh_command="$(printf '%s\n' "$ssh_info" | jq -r '.sshCommand // .ssh_command // empty' 2>/dev/null || true)"
fi
if [[ -z "$ssh_command" ]]; then
  ssh_command="$(printf '%s\n' "$ssh_info" | sed -nE 's/.*"ssh(Command|_command)"[[:space:]]*:[[:space:]]*"([^"]+)".*/\2/p' | head -1)"
fi
if [[ -z "$ssh_command" ]]; then
  ssh_command="$(printf '%s\n' "$ssh_info" | sed -nE 's/.*(ssh -i [^"]+).*/\1/p' | head -1 || true)"
fi
if [[ -z "$ssh_command" ]]; then
  printf 'Could not find ssh command in runpodctl output:\n%s\n' "$ssh_info" >&2
  exit 1
fi

eval "ssh_parts=(${ssh_command})"
ssh_options=(-o StrictHostKeyChecking=accept-new)

if [[ $# -eq 0 ]]; then
  exec "${ssh_parts[0]}" "${ssh_options[@]}" "${ssh_parts[@]:1}"
fi

remote_command="$(printf '%q ' "$@")"
exec "${ssh_parts[0]}" "${ssh_options[@]}" "${ssh_parts[@]:1}" -t -- "$remote_command"
