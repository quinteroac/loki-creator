from __future__ import annotations

import sys
import time
import unittest

from app.models import SkillDefinition
from app.services.skill_invokers import SkillActionInvoker, SkillInvocationError


class SkillActionInvokerTest(unittest.TestCase):
    def test_cli_local_timeout_applies_while_stdout_is_open(self) -> None:
        skill = SkillDefinition(
            id="slow-skill",
            name="Slow skill",
            description="Sleeps past the timeout.",
            path=".",
            action={
                "type": "cli-local",
                "command": [sys.executable, "-c", "import time; print('started', flush=True); time.sleep(5)"],
                "timeoutSeconds": 1,
            },
        )
        invoker = SkillActionInvoker()

        started = time.monotonic()
        with self.assertRaisesRegex(SkillInvocationError, "timed out after 1s"):
            invoker.invoke(skill, {"runId": "slow_run"})
        elapsed = time.monotonic() - started

        self.assertLess(elapsed, 4)


if __name__ == "__main__":
    unittest.main()
