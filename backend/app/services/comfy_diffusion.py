import os
from pathlib import Path
from typing import Any


class ComfyDiffusionService:
    def __init__(self, models_dir: str | Path | None = None) -> None:
        self._models_dir = Path(models_dir).expanduser() if models_dir is not None else None

    def resolve_models_dir(self) -> Path:
        if self._models_dir is not None:
            return self._models_dir

        configured_dir = os.environ.get("LOKI_COMFY_MODELS_DIR")
        if configured_dir:
            return Path(configured_dir).expanduser()

        repo_root = Path(__file__).resolve().parents[3]
        return repo_root / ".loki" / "comfy-models"

    def check_runtime(self) -> dict[str, Any]:
        try:
            from comfy_diffusion import check_runtime
        except Exception as error:
            return {
                "error": f"Unable to import comfy-diffusion: {error}",
            }

        try:
            runtime_info = check_runtime()
        except Exception as error:
            return {
                "error": f"Unable to check comfy-diffusion runtime: {error}",
            }

        if not isinstance(runtime_info, dict):
            return {
                "error": "comfy-diffusion returned an unexpected runtime response.",
                "response": runtime_info,
            }

        return runtime_info

    def get_runtime_info(self) -> dict[str, Any]:
        runtime_info = self.check_runtime()
        models_dir = self.resolve_models_dir()

        return {
            **runtime_info,
            "modelsDir": str(models_dir),
            "modelsDirExists": models_dir.exists(),
        }
