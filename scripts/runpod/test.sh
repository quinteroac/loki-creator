#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

cat > "${tmp_dir}/runpodctl" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ "$1 $2" == "ssh info" ]]; then
  printf '{"sshCommand":"ssh root@example.runpod.test -p 2222 -i /tmp/key"}\n'
  exit 0
fi
printf 'unexpected runpodctl args: %s\n' "$*" >&2
exit 1
EOF
chmod +x "${tmp_dir}/runpodctl"

cat > "${tmp_dir}/ssh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" > "${RUNPOD_TEST_CAPTURE}"
EOF
chmod +x "${tmp_dir}/ssh"

export PATH="${tmp_dir}:${PATH}"
export RUNPOD_TEST_CAPTURE="${tmp_dir}/capture"

"${repo_root}/scripts/runpod/remote.sh" pod123 loki-doctor

if ! grep -q -- '-t -- loki-doctor' "$RUNPOD_TEST_CAPTURE"; then
  printf 'remote.sh did not forward the expected remote command\n' >&2
  cat "$RUNPOD_TEST_CAPTURE" >&2
  exit 1
fi

printf 'runpod shell tests passed\n'
