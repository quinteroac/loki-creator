from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.env import load_dotenv


class EnvTest(unittest.TestCase):
    def test_load_dotenv_sets_missing_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(os.environ, {}, clear=True):
            env_path = Path(tmpdir) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "# local secrets",
                        "OPENROUTER_API_KEY=secret-key",
                        "export LOKI_GEMINI_BIN='agy'",
                        'LOKI_CODEX_BIN="codex"',
                    ]
                ),
                encoding="utf-8",
            )

            loaded = load_dotenv(env_path)

            self.assertEqual(loaded, {"OPENROUTER_API_KEY", "LOKI_GEMINI_BIN", "LOKI_CODEX_BIN"})
            self.assertEqual(os.environ["OPENROUTER_API_KEY"], "secret-key")
            self.assertEqual(os.environ["LOKI_GEMINI_BIN"], "agy")
            self.assertEqual(os.environ["LOKI_CODEX_BIN"], "codex")

    def test_load_dotenv_does_not_override_existing_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(os.environ, {"OPENROUTER_API_KEY": "shell-key"}, clear=True):
            env_path = Path(tmpdir) / ".env"
            env_path.write_text("OPENROUTER_API_KEY=file-key\n", encoding="utf-8")

            loaded = load_dotenv(env_path)

            self.assertEqual(loaded, set())
            self.assertEqual(os.environ["OPENROUTER_API_KEY"], "shell-key")

    def test_load_dotenv_rejects_invalid_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text("OPENROUTER_API_KEY\n", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "expected KEY=VALUE"):
                load_dotenv(env_path)


if __name__ == "__main__":
    unittest.main()
