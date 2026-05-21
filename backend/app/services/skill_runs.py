from datetime import datetime, timezone
from uuid import uuid4

from app.models import SkillRun, SkillRunRequest
from app.services.card_packager import CardPackagerService
from app.services.skill_invokers import SkillActionInvoker
from app.services.skill_registry import SkillRegistry


class SkillRunService:
    def __init__(
        self,
        registry: SkillRegistry | None = None,
        invoker: SkillActionInvoker | None = None,
        packager: CardPackagerService | None = None,
    ) -> None:
        self.registry = registry or SkillRegistry()
        self.invoker = invoker or SkillActionInvoker()
        self.packager = packager or CardPackagerService()
        self._runs: dict[str, SkillRun] = {}

    def create_run(self, payload: SkillRunRequest) -> SkillRun:
        run_id = f"skill_run_{uuid4().hex}"
        now = datetime.now(timezone.utc)
        run = SkillRun(
            id=run_id,
            skill_id=payload.skill_id,
            status="queued",
            created_at=now,
            updated_at=now,
        )
        self._runs[run_id] = run
        return run

    def get_run(self, run_id: str) -> SkillRun | None:
        return self._runs.get(run_id)

    def list_runs(self, status: str | None = None) -> list[SkillRun]:
        runs = sorted(self._runs.values(), key=lambda run: run.created_at)
        if status is None:
            return runs
        return [run for run in runs if run.status == status]

    def run_skill(self, run_id: str, payload: SkillRunRequest) -> None:
        run = self._runs.get(run_id)
        if run is None:
            return

        self._set_status(run_id, "running")
        skill = self.registry.get_skill(payload.skill_id)
        if skill is None:
            self._fail(run_id, f"Skill not found: {payload.skill_id}")
            return

        try:
            raw_result = self.invoker.invoke(
                skill,
                {
                    "runId": run_id,
                    "skillId": payload.skill_id,
                    "prompt": payload.prompt,
                    "context": payload.context,
                    "selectedCards": payload.selected_cards,
                    "selectedCardSnapshots": payload.selected_card_snapshots,
                    "params": payload.params,
                },
            )
            result = self.packager.package(
                skill=skill,
                run_id=run_id,
                prompt=payload.prompt,
                params=payload.params,
                raw_result=raw_result,
            )
        except Exception as exc:
            self._fail(run_id, str(exc))
            return

        now = datetime.now(timezone.utc)
        self._runs[run_id] = run.model_copy(
            update={
                "status": "succeeded",
                "updated_at": now,
                "result": result,
                "error": None,
            },
        )

    def _set_status(self, run_id: str, status: str) -> None:
        run = self._runs[run_id]
        self._runs[run_id] = run.model_copy(
            update={"status": status, "updated_at": datetime.now(timezone.utc)}
        )

    def _fail(self, run_id: str, error: str) -> None:
        run = self._runs[run_id]
        self._runs[run_id] = run.model_copy(
            update={
                "status": "failed",
                "updated_at": datetime.now(timezone.utc),
                "error": error,
            },
        )
