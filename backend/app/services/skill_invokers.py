import json
import subprocess
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError

from app.models import SkillDefinition, SkillRawResult


REPO_ROOT = Path(__file__).resolve().parents[3]


class SkillInvocationError(RuntimeError):
    pass


class SkillActionInvoker:
    def invoke(
        self,
        skill: SkillDefinition,
        payload: dict[str, Any],
        on_partial_result: Callable[[SkillRawResult], None] | None = None,
    ) -> SkillRawResult:
        action = skill.action
        if action is None:
            raise SkillInvocationError(f"Skill {skill.id} does not declare an action")
        if action.type != "cli-local":
            raise SkillInvocationError(f"Unsupported skill action type: {action.type}")
        if not action.command:
            raise SkillInvocationError(f"Skill {skill.id} action has no command")

        skill_dir = (REPO_ROOT / skill.path).resolve()
        try:
            skill_dir.relative_to(REPO_ROOT)
        except ValueError as exc:
            raise SkillInvocationError(f"Skill path is outside the repository: {skill.path}") from exc

        process = subprocess.Popen(
            action.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=skill_dir,
        )
        stdout_lines: list[str] = []
        stderr_text = ""
        try:
            assert process.stdin is not None
            process.stdin.write(json.dumps(payload))
            process.stdin.close()

            assert process.stdout is not None
            for line in process.stdout:
                stripped = line.strip()
                if stripped.startswith("__LOKI_PARTIAL_RESULT__"):
                    if on_partial_result is None:
                        continue
                    partial_json = stripped.removeprefix("__LOKI_PARTIAL_RESULT__")
                    try:
                        on_partial_result(SkillRawResult.model_validate(json.loads(partial_json)))
                    except (json.JSONDecodeError, ValidationError) as exc:
                        raise SkillInvocationError("Skill action returned an invalid partial result") from exc
                    continue
                if stripped:
                    stdout_lines.append(line)

            stderr_text = process.stderr.read() if process.stderr is not None else ""
            process.wait(timeout=action.timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            process.kill()
            raise SkillInvocationError(f"Skill action timed out after {action.timeout_seconds}s") from exc

        if process.returncode != 0:
            message = stderr_text.strip() or "".join(stdout_lines).strip() or "skill action failed"
            raise SkillInvocationError(message)

        try:
            decoded = json.loads("".join(stdout_lines))
        except json.JSONDecodeError as exc:
            raise SkillInvocationError("Skill action did not return valid JSON") from exc

        try:
            return SkillRawResult.model_validate(decoded)
        except ValidationError as exc:
            raise SkillInvocationError("Skill action returned an invalid result") from exc
