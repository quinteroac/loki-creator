ARG BASE_IMAGE=docker.io/library/ubuntu:22.04
FROM ${BASE_IMAGE}

ENV DEBIAN_FRONTEND=noninteractive
ENV BUN_INSTALL=/root/.bun
ENV LOKI_ARTIFACTS_ROOT=/workspace/.loki
ENV LOKI_COMFY_MODELS_DIR=/workspace/.loki/models/comfyui
ENV LOKI_COMFY_RUNTIME_DIR=/workspace/.loki/runtime/comfy-agent-tools
ENV LOKI_REQUIRE_COMFY_CUDA=1
ENV LOKI_BACKEND_URL=http://127.0.0.1:8001
ENV LOKI_AGENT_BRIDGE_PORT=8787
ENV PATH=/opt/loki-creator/backend/.venv/bin:/workspace/.loki/runtime/comfy-agent-tools/bin:/workspace/.loki/runtime/bin:/root/.local/bin:/root/.bun/bin:/usr/local/bin:${PATH}

WORKDIR /opt/loki-creator

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    curl \
    ffmpeg \
    git \
    gnupg \
    jq \
    libgl1 \
    libglib2.0-0 \
    nginx \
    openssh-client \
    openssh-server \
    procps \
    python3 \
    python3-venv \
    rsync \
    tini \
    unzip \
  && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://bun.sh/install | bash \
  && curl -LsSf https://astral.sh/uv/install.sh | sh \
  && curl -sL https://cli.runpod.io | bash \
  && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
  && apt-get install -y --no-install-recommends nodejs \
  && rm -rf /var/lib/apt/lists/*

COPY package.json bun.lock ./
COPY frontend/package.json frontend/bun.lock ./frontend/
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./backend/

RUN bun install --frozen-lockfile \
  && bun install --cwd frontend --frozen-lockfile \
  && cd backend \
  && uv python install 3.12 \
  && uv sync --frozen --python 3.12 \
  && CODEX_BIN="$(uv run python -c 'from pathlib import Path; import codex_cli_bin; print(Path(codex_cli_bin.__file__).parent / "bin" / "codex")')" \
  && chmod +x "${CODEX_BIN}" \
  && ln -sf "${CODEX_BIN}" /usr/local/bin/codex

RUN curl -fsSL https://x.ai/cli/install.sh | bash \
  && curl -fsSL https://antigravity.google/cli/install.sh | bash

COPY . .

RUN VITE_API_URL="" VITE_AGENT_API_URL="/agent" bun run --cwd frontend build \
  && install -m 0755 deploy/runpod/bin/* /usr/local/bin/ \
  && install -d /usr/local/lib/loki-runpod \
  && install -m 0644 deploy/runpod/lib/common.sh /usr/local/lib/loki-runpod/common.sh \
  && install -m 0644 deploy/runpod/nginx.conf /etc/nginx/nginx.conf \
  && ln -sf /opt/loki-creator/node_modules/.bin/pi /usr/local/bin/pi \
  && mkdir -p /run/nginx /workspace

EXPOSE 3000 8001 8787 22

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/loki-entrypoint"]
