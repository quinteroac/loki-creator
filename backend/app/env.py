from __future__ import annotations

import os
import re
from pathlib import Path


ENV_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_env_line(line: str, *, line_number: int, path: Path) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped.startswith("export "):
        stripped = stripped.removeprefix("export ").strip()
    if "=" not in stripped:
        raise RuntimeError(f"Invalid .env line {line_number} in {path}: expected KEY=VALUE.")

    key, value = stripped.split("=", 1)
    key = key.strip()
    if not ENV_KEY_PATTERN.fullmatch(key):
        raise RuntimeError(f"Invalid .env key on line {line_number} in {path}: {key!r}.")

    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return key, value


def load_dotenv(path: Path | None = None) -> set[str]:
    env_path = (path or repo_root() / ".env").resolve()
    if not env_path.exists():
        return set()
    if not env_path.is_file():
        raise RuntimeError(f".env path is not a file: {env_path}")

    loaded: set[str] = set()
    for line_number, line in enumerate(env_path.read_text(encoding="utf-8").splitlines(), start=1):
        parsed = parse_env_line(line, line_number=line_number, path=env_path)
        if parsed is None:
            continue
        key, value = parsed
        if key not in os.environ:
            os.environ[key] = value
            loaded.add(key)
    return loaded
