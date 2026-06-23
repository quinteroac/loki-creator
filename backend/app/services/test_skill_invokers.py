from __future__ import annotations

import sys
import time
import unittest

from app.models import SkillDefinition
from app.services.skill_invokers import SkillActionInvoker


class SkillActionInvokerTest(unittest.TestCase):
    def test_cli_local_does_not_timeout_while_stdout_is_open(self) -> None:
        skill = SkillDefinition(
            id="slow-skill",
            name="Slow skill",
            description="Sleeps past the legacy timeout.",
            path=".",
            action={
                "type": "cli-local",
                "command": [
                    sys.executable,
                    "-c",
                    "import sys, time; print('started', file=sys.stderr, flush=True); time.sleep(1.2); print('{\"artifacts\": []}')",
                ],
                "timeoutSeconds": 1,
            },
        )
        invoker = SkillActionInvoker()

        started = time.monotonic()
        result = invoker.invoke(skill, {"runId": "slow_run"})
        elapsed = time.monotonic() - started

        self.assertEqual(result.artifacts, [])
        self.assertGreaterEqual(elapsed, 1)


if __name__ == "__main__":
    unittest.main()
