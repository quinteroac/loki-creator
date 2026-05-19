from datetime import UTC, datetime
from threading import Lock
from uuid import uuid4

from app.models import ToolInvocationRequest, ToolJob
from app.services.tool_invokers import ToolInvocationError, ToolInvokerFactory
from app.services.tool_registry import ToolRegistry


class ToolJobService:
    def __init__(
        self,
        registry: ToolRegistry | None = None,
        invoker_factory: ToolInvokerFactory | None = None,
    ) -> None:
        self._registry = registry or ToolRegistry()
        self._invoker_factory = invoker_factory or ToolInvokerFactory()
        self._jobs: dict[str, ToolJob] = {}
        self._lock = Lock()

    def create_job(self, payload: ToolInvocationRequest) -> ToolJob:
        now = datetime.now(UTC)
        job = ToolJob(
            id=f"job_{uuid4().hex}",
            tool_id=payload.tool_id,
            status="queued",
            created_at=now,
            updated_at=now,
        )

        with self._lock:
            self._jobs[job.id] = job

        return job

    def get_job(self, job_id: str) -> ToolJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self, status: str | None = None) -> list[ToolJob]:
        with self._lock:
            jobs = list(self._jobs.values())

        if status is None:
            return jobs

        return [job for job in jobs if job.status == status]

    def run_job(self, job_id: str, payload: ToolInvocationRequest) -> None:
        tool = self._registry.get_tool(payload.tool_id)
        if tool is None:
            self._fail_job(job_id, f"Tool not found: {payload.tool_id}")
            return

        self._update_job(job_id, status="running", tool_id=tool.id)

        try:
            invoker = self._invoker_factory.get_invoker(tool.source_type)
            result = invoker.invoke(tool, payload)
            self._update_job(job_id, status="succeeded", result=result)
        except (ToolInvocationError, Exception) as error:
            self._fail_job(job_id, str(error))

    def _update_job(self, job_id: str, **updates) -> None:
        with self._lock:
            job = self._jobs[job_id]
            self._jobs[job_id] = job.model_copy(
                update={
                    **updates,
                    "updated_at": datetime.now(UTC),
                }
            )

    def _fail_job(self, job_id: str, error: str) -> None:
        self._update_job(job_id, status="failed", error=error)
