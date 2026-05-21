import json
import subprocess
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.models import SkillDefinition, SkillResult


REPO_ROOT = Path(__file__).resolve().parents[3]


class SkillInvocationError(RuntimeError):
    pass


class SkillActionInvoker:
    def invoke(self, skill: SkillDefinition, payload: dict[str, Any]) -> SkillResult:
        if skill.card_action is None:
            raise SkillInvocationError(f"Skill {skill.id} does not declare a card action")
        if skill.card_action.type != "cli-local":
            raise SkillInvocationError(f"Unsupported skill action type: {skill.card_action.type}")
        if not skill.card_action.command:
            raise SkillInvocationError(f"Skill {skill.id} card action has no command")

        skill_dir = (REPO_ROOT / skill.path).resolve()
        try:
            skill_dir.relative_to(REPO_ROOT)
        except ValueError as exc:
            raise SkillInvocationError(f"Skill path is outside the repository: {skill.path}") from exc

        process = subprocess.run(
            skill.card_action.command,
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            cwd=skill_dir,
            timeout=skill.card_action.timeout_seconds,
            check=False,
        )

        if process.returncode != 0:
            message = process.stderr.strip() or process.stdout.strip() or "skill action failed"
            raise SkillInvocationError(message)

        try:
            decoded = json.loads(process.stdout)
        except json.JSONDecodeError as exc:
            raise SkillInvocationError("Skill action did not return valid JSON") from exc

        try:
            return SkillResult.model_validate(decoded)
        except ValidationError as exc:
            raise SkillInvocationError("Skill action returned an invalid result") from exc
