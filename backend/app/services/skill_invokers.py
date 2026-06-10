import json
import os
import signal
import subprocess
import threading
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError

from app.models import SkillDefinition, SkillRawResult


REPO_ROOT = Path(__file__).resolve().parents[3]


class SkillInvocationError(RuntimeError):
    pass


class SkillActionInvoker:
    def __init__(self) -> None:
        self._processes: dict[str, subprocess.Popen[str]] = {}

    def _terminate_process(self, process: subprocess.Popen[str]) -> None:
        if process.poll() is not None:
            return

        try:
            if os.name == "nt":
                process.kill()
            else:
                os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            return

    def _close_process_pipes(self, process: subprocess.Popen[str]) -> None:
        for pipe in (process.stdin, process.stdout, process.stderr):
            if pipe is None or pipe.closed:
                continue
            try:
                pipe.close()
            except OSError:
                continue

    def cancel(self, run_id: str) -> None:
        process = self._processes.get(run_id)
        if process is None or process.poll() is not None:
            return

        try:
            if os.name == "nt":
                process.terminate()
            else:
                os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._terminate_process(process)
        except ProcessLookupError:
            return

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

        run_id = str(payload.get("runId") or "")
        process = subprocess.Popen(
            action.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=skill_dir,
            start_new_session=os.name != "nt",
        )
        if run_id:
            self._processes[run_id] = process
        stdout_lines: list[str] = []
        stderr_lines: list[str] = []
        reader_errors: list[Exception] = []

        def read_stdout() -> None:
            assert process.stdout is not None
            try:
                for line in process.stdout:
                    stripped = line.strip()
                    if stripped.startswith("__LOKI_PARTIAL_RESULT__"):
                        if on_partial_result is None:
                            continue
                        partial_json = stripped.removeprefix("__LOKI_PARTIAL_RESULT__")
                        try:
                            on_partial_result(SkillRawResult.model_validate(json.loads(partial_json)))
                        except (json.JSONDecodeError, ValidationError) as exc:
                            reader_errors.append(SkillInvocationError("Skill action returned an invalid partial result"))
                            self._terminate_process(process)
                            return
                        continue
                    if stripped:
                        stdout_lines.append(line)
            except Exception as exc:
                reader_errors.append(exc)

        def read_stderr() -> None:
            assert process.stderr is not None
            try:
                for line in process.stderr:
                    stderr_lines.append(line)
            except Exception as exc:
                reader_errors.append(exc)

        try:
            assert process.stdin is not None
            process.stdin.write(json.dumps(payload))
            process.stdin.close()

            assert process.stdout is not None
            assert process.stderr is not None
            stdout_thread = threading.Thread(target=read_stdout, daemon=True)
            stderr_thread = threading.Thread(target=read_stderr, daemon=True)
            stdout_thread.start()
            stderr_thread.start()
            timeout_seconds = action.timeout_seconds if action.timeout_seconds > 0 else None
            process.wait(timeout=timeout_seconds)
            stdout_thread.join(timeout=5)
            stderr_thread.join(timeout=5)
        except subprocess.TimeoutExpired as exc:
            self._terminate_process(process)
            process.wait(timeout=10)
            self._close_process_pipes(process)
            raise SkillInvocationError(f"Skill action timed out after {action.timeout_seconds}s") from exc
        finally:
            if run_id:
                self._processes.pop(run_id, None)
            if process.poll() is not None:
                self._close_process_pipes(process)

        if reader_errors:
            first_error = reader_errors[0]
            if isinstance(first_error, SkillInvocationError):
                raise first_error
            raise SkillInvocationError(str(first_error)) from first_error

        stderr_text = "".join(stderr_lines)
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
