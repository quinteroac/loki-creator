from __future__ import annotations

from typing import Any

from app.models import SeedanceVideoGenerationRequest, SeedanceVideoGenerationResponse
from app.services.openrouter_video import (
    OpenRouterVideoConfig,
    OpenRouterVideoGenerationError,
    OpenRouterVideoGenerationService,
    OpenRouterVideoRequest,
    first_text,
)


SEEDANCE_MODEL = "bytedance/seedance-2.0-fast"
SEEDANCE_SKILL_ID = "openrouter-seedance-direct"
SEEDANCE_RESOLUTION = "480p"


class SeedanceVideoGenerationError(OpenRouterVideoGenerationError):
    pass


class SeedanceVideoGenerationService(OpenRouterVideoGenerationService):
    config = OpenRouterVideoConfig(
        model=SEEDANCE_MODEL,
        skill_id=SEEDANCE_SKILL_ID,
        name="Seedance",
        description="Direct OpenRouter Seedance reference-to-video generation.",
        output_folder="seedance-video",
        output_filename="seedance-video.mp4",
        resolution=SEEDANCE_RESOLUTION,
        capabilities=("video-generation", "reference-to-video", "image-reference", "audio-reference", "openrouter", "seedance"),
    )
    error_type = SeedanceVideoGenerationError
    response_type = SeedanceVideoGenerationResponse

    def build_request_body(self, payload: OpenRouterVideoRequest, prompt: str) -> dict[str, Any]:
        image_reference = self.first_reference(payload, "image")
        if image_reference is None:
            self.fail("Seedance video generation requires one selected or attached image.")

        references = [image_reference]
        audio_reference = self.first_reference(payload, "audio")
        if audio_reference is not None:
            references.append(audio_reference)
        return {
            "model": self.config.model,
            "prompt": prompt,
            "resolution": self.config.resolution,
            "aspect_ratio": payload.aspect_ratio,
            "duration": payload.duration,
            "generate_audio": True,
            "input_references": references,
        }

    def artifact_metadata(self, request_body: dict[str, Any]) -> dict[str, Any]:
        references = request_body.get("input_references")
        reference_list = references if isinstance(references, list) else []
        return {
            "source": "reference-to-video",
            "inputImageCount": 1,
            "inputAudioCount": sum(
                1 for reference in reference_list if isinstance(reference, dict) and first_text(reference.get("type")) == "audio_url"
            ),
        }

    def generate(self, payload: SeedanceVideoGenerationRequest) -> SeedanceVideoGenerationResponse:
        return super().generate(payload)
