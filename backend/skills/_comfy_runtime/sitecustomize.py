"""Loki-only monkey patches for comfy-agent-tools subprocesses."""

from __future__ import annotations

import os


def _enabled(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _install_sage_attention_patch() -> None:
    try:
        from comfy_diffusion import _runtime
    except ModuleNotFoundError:
        return

    if getattr(_runtime, "_loki_sage_attention_patch_installed", False):
        return

    original_ensure_comfyui_on_path = _runtime.ensure_comfyui_on_path

    def ensure_comfyui_on_path_with_sage_attention(*args: object, **kwargs: object) -> object:
        comfyui_root = original_ensure_comfyui_on_path(*args, **kwargs)
        try:
            import sageattention  # noqa: F401
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "LOKI_COMFY_USE_SAGE_ATTENTION=1 requires the sageattention package "
                "inside the comfy-agent-tools uv tool environment."
            ) from exc

        import comfy.cli_args as comfy_cli_args

        cli_args = comfy_cli_args.args
        for flag in (
            "use_split_cross_attention",
            "use_quad_cross_attention",
            "use_pytorch_cross_attention",
            "use_flash_attention",
        ):
            if hasattr(cli_args, flag):
                setattr(cli_args, flag, False)
        cli_args.use_sage_attention = True
        return comfyui_root

    _runtime.ensure_comfyui_on_path = ensure_comfyui_on_path_with_sage_attention
    _runtime._loki_sage_attention_patch_installed = True


if _enabled(os.environ.get("LOKI_COMFY_USE_SAGE_ATTENTION")):
    _install_sage_attention_patch()
