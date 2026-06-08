from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
import json
import mimetypes
import os
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from importlib import util as importlib_util
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from PIL import Image

from app.models import (
    CodexImageGenerationRequest,
    CodexImageGenerationResponse,
    SkillArtifact,
    SkillDefinition,
    SkillOutputConfig,
    SkillRawResult,
)
from app.services.card_packager import CardPackagerService


CODEX_IMAGE_SKILL_ID = "codex-image-direct"
BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent
IMAGEGEN_ACTION_PATH = REPO_ROOT / "backend" / "skills" / "imagegen" / "scripts" / "card_action.py"
SUPPORTED_IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}


class CodexImageGenerationError(RuntimeError):
    pass


def first_text(*values: object) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def load_imagegen_action_module() -> Any:
    if not IMAGEGEN_ACTION_PATH.is_file():
        raise CodexImageGenerationError(f"Codex image action helpers not found at {IMAGEGEN_ACTION_PATH}.")
    spec = importlib_util.spec_from_file_location("loki_imagegen_card_action", IMAGEGEN_ACTION_PATH)
    if spec is None or spec.loader is None:
        raise CodexImageGenerationError(f"Could not load Codex image action helpers from {IMAGEGEN_ACTION_PATH}.")
    module = importlib_util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CodexImageGenerationService:
    def __init__(self, artifacts_root: Path, *, packager: CardPackagerService | None = None) -> None:
        self.artifacts_root = artifacts_root.resolve()
        self.packager = packager or CardPackagerService()

    def generate(self, payload: CodexImageGenerationRequest) -> CodexImageGenerationResponse:
        prompt = payload.prompt.strip()
        if not prompt:
            raise CodexImageGenerationError("Codex image generation requires a prompt.")
        self.reject_preview_only_image_media(payload.selected_card_snapshots, payload.attachments)

        params = {
            "prompt": prompt,
            "skillPrompt": prompt,
            "resolution": payload.resolution,
        }
        raw = self.invoke_action(prompt, params, payload.selected_card_snapshots, payload.attachments, payload.context)
        raw_result = self.validated_raw_result(raw)
        result = self.packager.package(
            skill=self.skill_definition(),
            run_id=f"generation_{uuid4().hex}",
            prompt=prompt,
            params=params,
            raw_result=raw_result,
        )
        return CodexImageGenerationResponse(cards=result.cards)

    def reject_preview_only_image_media(
        self,
        selected_card_snapshots: list[dict[str, Any]],
        attachments: list[dict[str, Any]],
    ) -> None:
        for snapshot in selected_card_snapshots:
            if not isinstance(snapshot, dict):
                continue
            for asset in snapshot.get("mediaAssets", []):
                if not isinstance(asset, dict) or asset.get("omitted"):
                    continue
                if asset.get("kind") == "image" and not first_text(asset.get("src")):
                    raise CodexImageGenerationError("Codex image inputs must be local Loki artifacts; preview-only media is not executable.")
            metadata = snapshot.get("metadata")
            if isinstance(metadata, dict) and metadata.get("kind") == "image" and not first_text(metadata.get("artifactUrl")):
                raise CodexImageGenerationError("Codex image inputs must be local Loki artifacts; preview-only media is not executable.")

        for attachment in attachments:
            if not isinstance(attachment, dict) or attachment.get("omitted"):
                continue
            if attachment.get("kind") == "image" and not first_text(attachment.get("artifactUrl"), attachment.get("src")):
                raise CodexImageGenerationError("Codex image inputs must be local Loki artifacts; preview-only media is not executable.")

    def invoke_action(
        self,
        prompt: str,
        params: dict[str, Any],
        selected_card_snapshots: list[dict[str, Any]],
        attachments: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        imagegen_action = load_imagegen_action_module()
        run_id = f"generation_{uuid4().hex}"
        run_dir = (self.artifacts_root / "skills" / "imagegen" / imagegen_action.safe_slug(run_id, "run")).resolve()
        output_dir = run_dir / "outputs"
        input_dir = run_dir / "inputs"
        output_dir.mkdir(parents=True, exist_ok=True)

        action_context = {
            **context,
            "selectedCardSnapshots": selected_card_snapshots,
        }
        action_payload = {
            "runId": run_id,
            "skillId": "imagegen",
            "prompt": prompt,
            "params": params,
            "context": action_context,
            "selectedCardSnapshots": selected_card_snapshots,
            "attachments": attachments,
        }

        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "request.json").write_text(json.dumps(action_payload, indent=2), encoding="utf-8")
        selected_images = self.materialize_selected_images(action_payload, input_dir)
        if not selected_images and self.has_non_local_image_reference(action_payload):
            raise CodexImageGenerationError(
                "Codex image inputs must be local Loki artifacts; preview-only media is not executable."
            )

        codex_prompt = imagegen_action.build_codex_prompt(action_payload, run_dir, output_dir, selected_images)
        codex_prompt = f"{codex_prompt}\n{self.codex_sdk_materialization_override()}"
        sdk_response = self.run_codex_sdk(codex_prompt, run_dir, selected_images)
        (run_dir / "codex-final-response.txt").write_text(sdk_response, encoding="utf-8")

        try:
            result = imagegen_action.extract_json_object(sdk_response)
        except (json.JSONDecodeError, ValueError) as exc:
            raise CodexImageGenerationError("Codex SDK did not return valid JSON.") from exc
        if not isinstance(result, dict):
            raise CodexImageGenerationError("Codex SDK did not return a JSON object.")
        result = self.materialize_sdk_generated_images(result, run_dir)
        (run_dir / "codex-response.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

        codex_images = imagegen_action.normalize_codex_images(result)
        if not codex_images:
            raise CodexImageGenerationError("Codex SDK response did not include images.")

        diagnostics = imagegen_action.normalize_codex_diagnostics(result)
        artifacts: list[dict[str, Any]] = []
        image_count = len(codex_images)
        resolution = imagegen_action.normalize_resolution(params.get("resolution"))
        for image_index, codex_image in enumerate(codex_images, start=1):
            try:
                artifact = self.sdk_image_to_artifact(
                    codex_image,
                    result,
                    action_payload,
                    run_dir,
                    image_index=image_index,
                    image_count=image_count,
                    resolution=resolution,
                )
            except Exception as error:
                diagnostics.append(
                    {
                        "level": "warning",
                        "title": f"Image {image_index} skipped",
                        "message": str(error),
                        "metadata": {"imageIndex": image_index, "imageCount": image_count},
                    }
                )
                continue
            artifacts.append(artifact)

        if not artifacts:
            details = "; ".join(
                diagnostic["message"]
                for diagnostic in diagnostics
                if isinstance(diagnostic, dict) and diagnostic.get("message")
            )
            raise CodexImageGenerationError(
                f"Codex SDK did not produce any valid image artifacts{': ' + details if details else ''}"
            )

        return {"artifacts": artifacts, "diagnostics": diagnostics}

    def run_codex_sdk(self, prompt: str, run_dir: Path, selected_images: list[Path]) -> str:
        try:
            from openai_codex import ApprovalMode, Codex, CodexConfig, LocalImageInput, Sandbox, TextInput
            from openai_codex._run import _collect_turn_result
            from openai_codex.generated.v2_all import ReasoningSummary
        except ImportError as exc:
            raise CodexImageGenerationError("Codex SDK dependency openai-codex is not installed.") from exc

        model = self.codex_sdk_model()
        summary = ReasoningSummary(self.codex_reasoning_summary())
        timeout_seconds = int(os.environ.get("LOKI_CODEX_DIRECT_TIMEOUT_SECONDS", "930"))
        codex_holder: dict[str, Any] = {}

        def execute() -> str:
            env = {**os.environ, "LOKI_ARTIFACTS_ROOT": str(self.artifacts_root)}
            model_kwargs = {"model": model} if model else {}
            config = CodexConfig(cwd=str(run_dir), env=env)
            stream_path = run_dir / "codex-sdk-events.jsonl"
            status_path = run_dir / "codex-sdk-status.json"
            self.write_codex_sdk_status(status_path, {"status": "starting", "runDir": str(run_dir)})
            with Codex(config) as codex:
                codex_holder["codex"] = codex
                thread = codex.thread_start(
                    approval_mode=ApprovalMode.deny_all,
                    cwd=str(run_dir),
                    sandbox=Sandbox.workspace_write,
                    **model_kwargs,
                )
                self.write_codex_sdk_status(
                    status_path,
                    {
                        "status": "thread_started",
                        "threadId": getattr(thread, "id", None),
                        "runDir": str(run_dir),
                        "streamPath": str(stream_path),
                    },
                )
                run_input: list[Any] = [TextInput(prompt)]
                run_input.extend(LocalImageInput(str(image_path)) for image_path in selected_images)
                turn = thread.turn(
                    run_input,
                    cwd=str(run_dir),
                    sandbox=Sandbox.workspace_write,
                    summary=summary,
                    **model_kwargs,
                )
                self.write_codex_sdk_status(
                    status_path,
                    {
                        "status": "running",
                        "threadId": getattr(thread, "id", None),
                        "turnId": getattr(turn, "id", None),
                        "runDir": str(run_dir),
                        "streamPath": str(stream_path),
                    },
                )
                try:
                    stream = self.logged_codex_sdk_stream(turn.stream(), stream_path, status_path, getattr(turn, "id", None))
                    result = _collect_turn_result(stream, turn_id=turn.id)
                except Exception as exc:
                    self.write_codex_sdk_status(
                        status_path,
                        {
                            "status": "failed",
                            "threadId": getattr(thread, "id", None),
                            "turnId": getattr(turn, "id", None),
                            "error": str(exc),
                            "runDir": str(run_dir),
                            "streamPath": str(stream_path),
                        },
                    )
                    raise
                self.write_codex_sdk_status(
                    status_path,
                    {
                        "status": "completed",
                        "threadId": getattr(thread, "id", None),
                        "turnId": getattr(turn, "id", None),
                        "runDir": str(run_dir),
                        "streamPath": str(stream_path),
                        "durationMs": getattr(result, "duration_ms", None),
                    },
                )
            return self.final_response_text(result)

        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="codex-sdk-image")
        future = executor.submit(execute)
        try:
            return future.result(timeout=timeout_seconds)
        except FutureTimeoutError as exc:
            codex = codex_holder.get("codex")
            if codex is not None:
                try:
                    codex.close()
                except Exception:
                    pass
            executor.shutdown(wait=False, cancel_futures=True)
            raise CodexImageGenerationError(f"Codex SDK image generation timed out after {timeout_seconds} seconds.") from exc
        except CodexImageGenerationError:
            raise
        except Exception as exc:
            raise CodexImageGenerationError(f"Codex SDK image generation failed: {exc}") from exc
        finally:
            if future.done():
                executor.shutdown(wait=True)

    def codex_sdk_model(self) -> str | None:
        model = os.environ.get("LOKI_CODEX_SDK_MODEL")
        if isinstance(model, str) and model.strip():
            return model.strip()
        return None

    def codex_reasoning_summary(self) -> str:
        summary = os.environ.get("LOKI_CODEX_REASONING_SUMMARY", "auto").strip().lower()
        if summary in {"auto", "concise", "detailed", "none"}:
            return summary
        raise CodexImageGenerationError(
            "LOKI_CODEX_REASONING_SUMMARY must be one of: auto, concise, detailed, none."
        )

    def codex_sdk_materialization_override(self) -> str:
        return f"""
Direct Codex SDK materialization override:
- First invoke Codex's built-in image generation/editing path. Do not begin the final JSON response until an image was generated or the image tool failed.
- Do not stream partial JSON while waiting for image generation.
- Do not run shell commands to inspect, find, list, copy, or move files from CODEX_HOME or ~/.codex/generated_images.
- If the built-in image generation tool returns a saved_path, use that exact saved_path as imagePath in the final JSON.
- Loki backend will copy only SDK-stream-reported saved_path files into {self.artifacts_root}/skills/imagegen/.../outputs and validate them there.
""".strip()

    def logged_codex_sdk_stream(
        self,
        stream: Iterator[Any],
        stream_path: Path,
        status_path: Path,
        turn_id: str | None,
    ) -> Iterator[Any]:
        stream_path.parent.mkdir(parents=True, exist_ok=True)
        event_count = 0
        with stream_path.open("a", encoding="utf-8") as events_file:
            for event in stream:
                event_count += 1
                received_at = time.time()
                event_type = self.codex_event_type(event)
                record = {
                    "receivedAt": received_at,
                    "eventIndex": event_count,
                    "eventType": event_type,
                    "turnId": turn_id,
                    "event": self.redacted_jsonable(event),
                }
                sdk_image = self.sdk_image_generation_event(record["event"])
                if sdk_image:
                    record["sdkImageGeneration"] = sdk_image
                events_file.write(json.dumps(record, ensure_ascii=False) + "\n")
                events_file.flush()
                status = {
                    "status": "running",
                    "turnId": turn_id,
                    "eventCount": event_count,
                    "lastEventType": event_type,
                    "lastEventAt": record["receivedAt"],
                    "streamPath": str(stream_path),
                }
                if sdk_image:
                    status["lastSdkImageGeneration"] = sdk_image
                    if sdk_image.get("savedPath"):
                        status["statusDetail"] = "image_generation_completed"
                    elif sdk_image.get("status"):
                        status["statusDetail"] = f"image_generation_{sdk_image['status']}"
                self.write_codex_sdk_status(status_path, status)
                yield event

    def codex_event_type(self, event: Any) -> str:
        payload = getattr(event, "payload", None)
        if payload is not None:
            return payload.__class__.__name__
        return event.__class__.__name__

    def write_codex_sdk_status(self, status_path: Path, status: dict[str, Any]) -> None:
        status_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"updatedAt": time.time(), **status}
        status_path.write_text(json.dumps(self.jsonable(payload), ensure_ascii=False, indent=2), encoding="utf-8")

    def jsonable(self, value: Any) -> Any:
        if value is None or isinstance(value, str | int | float | bool):
            return value
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, dict):
            return {str(key): self.jsonable(item) for key, item in value.items()}
        if isinstance(value, list | tuple | set):
            return [self.jsonable(item) for item in value]
        if hasattr(value, "model_dump"):
            return self.jsonable(value.model_dump(mode="json"))
        if is_dataclass(value):
            return self.jsonable(asdict(value))
        if hasattr(value, "__dict__"):
            return self.jsonable(vars(value))
        return str(value)

    def redacted_jsonable(self, value: Any) -> Any:
        return self.redact_stream_payload(self.jsonable(value))

    def redact_stream_payload(self, value: Any) -> Any:
        if isinstance(value, dict):
            redacted: dict[str, Any] = {}
            for key, item in value.items():
                if key in {"result", "encrypted_content", "encryptedContent"} and isinstance(item, str):
                    redacted[key] = {"redacted": True, "length": len(item)}
                elif isinstance(item, str) and len(item) > 4096:
                    redacted[key] = {"redacted": True, "length": len(item), "preview": item[:512]}
                else:
                    redacted[key] = self.redact_stream_payload(item)
            return redacted
        if isinstance(value, list):
            return [self.redact_stream_payload(item) for item in value]
        return value

    def sdk_image_generation_event(self, event: Any) -> dict[str, Any] | None:
        item = self.find_event_item(event)
        if not isinstance(item, dict) or item.get("type") != "imageGeneration":
            return None
        saved_path = first_text(item.get("saved_path"), item.get("savedPath"))
        return {
            "id": first_text(item.get("id")),
            "status": first_text(item.get("status")),
            "savedPath": saved_path or None,
            "revisedPrompt": first_text(item.get("revised_prompt"), item.get("revisedPrompt")) or None,
        }

    def find_event_item(self, value: Any) -> dict[str, Any] | None:
        if isinstance(value, dict):
            item = value.get("item")
            if isinstance(item, dict):
                return item
            for child in value.values():
                found = self.find_event_item(child)
                if found is not None:
                    return found
        elif isinstance(value, list):
            for child in value:
                found = self.find_event_item(child)
                if found is not None:
                    return found
        return None

    def final_response_text(self, result: Any) -> str:
        response = getattr(result, "final_response", None)
        if isinstance(response, str) and response.strip():
            return response
        if isinstance(result, dict):
            response = result.get("final_response") or result.get("finalResponse") or result.get("response")
            if isinstance(response, str) and response.strip():
                return response
        if isinstance(result, str) and result.strip():
            return result
        raise CodexImageGenerationError("Codex SDK completed without a final response.")

    def codex_output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["images", "diagnostics"],
            "properties": {
                "images": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["title", "prompt", "imagePath", "mimeType", "width", "height"],
                        "properties": {
                            "title": {"type": "string"},
                            "prompt": {"type": "string"},
                            "imagePath": {"type": "string"},
                            "mimeType": {"type": "string"},
                            "width": {"type": "integer"},
                            "height": {"type": "integer"},
                        },
                    },
                },
                "diagnostics": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["level", "title", "message"],
                        "properties": {
                            "level": {"type": "string", "enum": ["info", "warning", "error"]},
                            "title": {"type": "string"},
                            "message": {"type": "string"},
                        },
                    },
                },
            },
        }

    def materialize_sdk_generated_images(self, result: dict[str, Any], run_dir: Path) -> dict[str, Any]:
        images = result.get("images")
        if not isinstance(images, list) or not images:
            return result

        saved_paths = self.sdk_stream_saved_paths(run_dir)
        if not saved_paths:
            return result

        next_result = {**result, "images": [dict(image) if isinstance(image, dict) else image for image in images]}
        used_saved_paths: set[Path] = set()
        for index, image in enumerate(next_result["images"], start=1):
            if not isinstance(image, dict):
                continue
            current_path_text = first_text(image.get("imagePath"))
            current_path = Path(current_path_text).expanduser().resolve() if current_path_text else None
            if current_path is not None and self.path_is_inside_loki(current_path, run_dir) and current_path.is_file():
                continue

            source = self.match_sdk_generated_path(current_path, saved_paths, used_saved_paths)
            if source is None:
                continue
            used_saved_paths.add(source)
            destination = current_path if current_path is not None and self.path_is_inside_run_dir(current_path, run_dir) else None
            image["imagePath"] = str(self.copy_sdk_generated_image(source, run_dir, image, index, destination=destination))

        return next_result

    def sdk_stream_saved_paths(self, run_dir: Path) -> list[Path]:
        stream_path = run_dir / "codex-sdk-events.jsonl"
        if not stream_path.is_file():
            return []

        saved_paths: list[Path] = []
        for line in stream_path.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            image_generation = record.get("sdkImageGeneration") if isinstance(record, dict) else None
            if not isinstance(image_generation, dict):
                continue
            saved_path = first_text(image_generation.get("savedPath"))
            if not saved_path:
                continue
            path = Path(saved_path).expanduser().resolve()
            if path not in saved_paths and self.is_codex_sdk_generated_path(path):
                saved_paths.append(path)
        return saved_paths

    def match_sdk_generated_path(
        self,
        current_path: Path | None,
        saved_paths: list[Path],
        used_saved_paths: set[Path],
    ) -> Path | None:
        if current_path is not None and current_path in saved_paths and current_path not in used_saved_paths:
            return current_path
        for saved_path in saved_paths:
            if saved_path not in used_saved_paths:
                return saved_path
        return None

    def is_codex_sdk_generated_path(self, path: Path) -> bool:
        codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser().resolve()
        try:
            path.relative_to(codex_home / "generated_images")
        except ValueError:
            return False
        return path.is_file()

    def copy_sdk_generated_image(
        self,
        source: Path,
        run_dir: Path,
        codex_image: dict[str, Any],
        index: int,
        *,
        destination: Path | None = None,
    ) -> Path:
        output_dir = run_dir / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        if destination is None:
            source_suffix = source.suffix if source.suffix else ".png"
            title = first_text(codex_image.get("title"), source.stem, f"codex_image_{index}")
            imagegen_action = load_imagegen_action_module()
            base_name = imagegen_action.safe_slug(title, f"codex_image_{index}")
            destination = (output_dir / f"{base_name}{source_suffix}").resolve()
            counter = 2
            while destination.exists() and destination.resolve() != source:
                destination = (output_dir / f"{base_name}_{counter}{source_suffix}").resolve()
                counter += 1
        else:
            destination = destination.resolve()
        try:
            destination.relative_to(run_dir)
        except ValueError as exc:
            raise CodexImageGenerationError("Codex SDK materialized output must stay inside the Loki run directory.") from exc
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination != source:
            shutil.copy2(source, destination)
        return destination

    def path_is_inside_loki(self, path: Path, run_dir: Path) -> bool:
        for root in (self.artifacts_root, run_dir):
            try:
                path.relative_to(root)
                return True
            except ValueError:
                continue
        return False

    def path_is_inside_run_dir(self, path: Path, run_dir: Path) -> bool:
        try:
            path.relative_to(run_dir)
        except ValueError:
            return False
        return True

    def sdk_image_to_artifact(
        self,
        codex_image: dict[str, Any],
        result: dict[str, Any],
        payload: dict[str, Any],
        run_dir: Path,
        *,
        image_index: int,
        image_count: int,
        resolution: str,
    ) -> dict[str, Any]:
        image_path = self.validate_sdk_image_path(codex_image, run_dir)
        mime_type = first_text(codex_image.get("mimeType")) or mimetypes.guess_type(image_path.name)[0] or "image/png"
        if mime_type not in SUPPORTED_IMAGE_MIME_TYPES and not mime_type.startswith("image/"):
            raise CodexImageGenerationError(f"Codex SDK output is not an image: {mime_type}")
        width, height = self.verified_image_dimensions(image_path)
        title = first_text(codex_image.get("title"), result.get("title"), f"Generated image {image_index}")
        final_prompt = first_text(codex_image.get("prompt"), result.get("prompt"), payload.get("prompt"))
        metadata: dict[str, Any] = {
            "resolution": resolution,
            "requestedResolution": resolution,
            "imageIndex": image_index,
            "imageCount": image_count,
            "tags": ["imagegen"],
            "capabilities": ["image-generation", "image-editing"],
            "width": width,
            "height": height,
        }
        return {
            "path": str(image_path),
            "kind": "image",
            "mimeType": mime_type,
            "title": title,
            "prompt": final_prompt,
            "metadata": metadata,
        }

    def validate_sdk_image_path(self, codex_image: dict[str, Any], run_dir: Path) -> Path:
        image_path_value = first_text(codex_image.get("imagePath"))
        if not image_path_value:
            raise CodexImageGenerationError("Codex SDK response did not include imagePath.")

        image_path = Path(image_path_value).expanduser().resolve()
        try:
            image_path.relative_to(self.artifacts_root)
        except ValueError:
            try:
                image_path.relative_to(run_dir)
            except ValueError as exc:
                raise CodexImageGenerationError("Codex SDK imagePath must be inside the Loki artifacts directory.") from exc

        if not image_path.is_file():
            raise CodexImageGenerationError(f"Codex SDK returned an imagePath but no artifact was written: {image_path}")
        return image_path

    def verified_image_dimensions(self, image_path: Path) -> tuple[int, int]:
        try:
            with Image.open(image_path) as image:
                image.verify()
            with Image.open(image_path) as image:
                return image.size
        except Exception as exc:
            raise CodexImageGenerationError(f"Codex SDK artifact is not a valid image: {image_path}") from exc

    def resolve_artifact_src(self, src: str) -> Path | None:
        if not src.startswith("/api/artifacts/"):
            return None
        artifact_path = (self.artifacts_root / src.removeprefix("/api/artifacts/")).resolve()
        try:
            artifact_path.relative_to(self.artifacts_root)
        except ValueError:
            return None
        return artifact_path if artifact_path.is_file() else None

    def append_image_path(self, paths: list[Path], src: str) -> bool:
        artifact_path = self.resolve_artifact_src(src)
        if artifact_path is None or artifact_path in paths:
            return False
        paths.append(artifact_path)
        return True

    def materialize_selected_images(self, payload: dict[str, Any], inputs_dir: Path) -> list[Path]:
        inputs_dir.mkdir(parents=True, exist_ok=True)
        materialized: list[Path] = []

        for reference in self.local_media_references(payload):
            if first_text(reference.get("kind")) != "image":
                continue
            path = Path(first_text(reference.get("path"))).expanduser().resolve()
            try:
                path.relative_to(self.artifacts_root)
            except ValueError:
                continue
            if path.is_file() and path not in materialized:
                materialized.append(path)

        attachments = payload.get("attachments")
        if isinstance(attachments, list):
            for attachment in attachments:
                if not isinstance(attachment, dict) or attachment.get("omitted") or attachment.get("kind") != "image":
                    continue
                self.append_image_path(materialized, first_text(attachment.get("artifactUrl"), attachment.get("src")))

        snapshots = payload.get("selectedCardSnapshots")
        if isinstance(snapshots, list):
            for snapshot in snapshots:
                if not isinstance(snapshot, dict):
                    continue
                metadata = snapshot.get("metadata")
                if isinstance(metadata, dict) and first_text(metadata.get("kind")) == "image":
                    self.append_image_path(materialized, first_text(metadata.get("artifactUrl")))
                media_assets = snapshot.get("mediaAssets")
                if isinstance(media_assets, list):
                    for asset in media_assets:
                        if isinstance(asset, dict) and asset.get("kind") == "image":
                            self.append_image_path(materialized, first_text(asset.get("src")))

        for image_path in materialized:
            if image_path.parent == inputs_dir:
                continue
            destination = inputs_dir / image_path.name
            if destination == image_path:
                continue
            if not destination.exists():
                shutil.copy2(image_path, destination)
        return materialized

    def local_media_references(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        references: list[dict[str, Any]] = []
        params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
        context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
        for source in (params.get("localMediaReferences"), context.get("localMediaReferences")):
            if isinstance(source, list):
                references.extend(reference for reference in source if isinstance(reference, dict))
        return references

    def has_non_local_image_reference(self, payload: dict[str, Any]) -> bool:
        attachments = payload.get("attachments")
        if isinstance(attachments, list):
            for attachment in attachments:
                if not isinstance(attachment, dict) or attachment.get("omitted"):
                    continue
                if attachment.get("kind") == "image" and first_text(attachment.get("dataUrl")):
                    return True

        snapshots = payload.get("selectedCardSnapshots")
        if not isinstance(snapshots, list):
            return False

        for snapshot in snapshots:
            if not isinstance(snapshot, dict):
                continue
            media_assets = snapshot.get("mediaAssets")
            if isinstance(media_assets, list):
                for asset in media_assets:
                    if not isinstance(asset, dict) or asset.get("omitted"):
                        continue
                    if asset.get("kind") == "image" and not first_text(asset.get("src")) and first_text(asset.get("dataUrl")):
                        return True
            preview = snapshot.get("preview")
            if isinstance(preview, dict) and not preview.get("omitted") and first_text(preview.get("dataUrl")):
                return True
        return False

    def validated_raw_result(self, raw: dict[str, Any]) -> SkillRawResult:
        artifacts = raw.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            raise CodexImageGenerationError("Codex image action completed without returning artifacts.")

        validated: list[SkillArtifact] = []
        for item in artifacts:
            if not isinstance(item, dict):
                raise CodexImageGenerationError("Codex image action returned an invalid artifact.")
            artifact = SkillArtifact.model_validate(item)
            if artifact.kind != "image":
                raise CodexImageGenerationError(f"Codex artifact kind must be image, got {artifact.kind}.")
            path = Path(artifact.path).expanduser().resolve()
            try:
                path.relative_to(self.artifacts_root)
            except ValueError as exc:
                raise CodexImageGenerationError(f"Codex artifact must be inside Loki artifacts root: {path}") from exc
            if not path.is_file():
                raise CodexImageGenerationError(f"Codex artifact path does not exist: {path}")
            self.verified_image_dimensions(path)
            artifact.path = str(path)
            validated.append(artifact)

        diagnostics = raw.get("diagnostics") if isinstance(raw.get("diagnostics"), list) else []
        return SkillRawResult(artifacts=validated, diagnostics=diagnostics)

    def skill_definition(self) -> SkillDefinition:
        return SkillDefinition(
            id=CODEX_IMAGE_SKILL_ID,
            name="Codex image",
            description="Direct Codex image generation and editing.",
            path="backend/app/services/codex_image.py",
            visibility="user",
            capabilities=["image-generation", "image-editing", "codex"],
            output=SkillOutputConfig(kind="image"),
        )
