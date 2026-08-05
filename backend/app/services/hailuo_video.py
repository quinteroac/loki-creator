from __future__ import annotations

from typing import Any

from app.models.generations import HailuoVideoGenerationRequest, HailuoVideoGenerationResponse
from app.services.openrouter_video import (
    OpenRouterVideoConfig,
    OpenRouterVideoGenerationError,
    OpenRouterVideoGenerationService,
    OpenRouterVideoRequest,
)


HAILUO_MODEL = "minimax/hailuo-3"
HAILUO_SKILL_ID = "openrouter-hailuo-direct"
HAILUO_RESOLUTION = "2K"


class HailuoVideoGenerationError(OpenRouterVideoGenerationError):
    pass


class HailuoVideoGenerationService(OpenRouterVideoGenerationService):
    config = OpenRouterVideoConfig(
        model=HAILUO_MODEL,
        skill_id=HAILUO_SKILL_ID,
        name="MiniMax H3",
        description="Direct OpenRouter MiniMax H3 text, image, or first/last-frame video generation.",
        output_folder="hailuo-video",
        output_filename="hailuo-video.mp4",
        resolution=HAILUO_RESOLUTION,
        capabilities=("video-generation", "text-to-video", "image-to-video", "first-last-frame", "audio-generation", "openrouter", "minimax", "hailuo"),
    )
    error_type = HailuoVideoGenerationError
    response_type = HailuoVideoGenerationResponse

    def build_request_body(self, payload: OpenRouterVideoRequest, prompt: str) -> dict[str, Any]:
        image_urls = self.reference_urls(payload, "image", limit=2)
        body: dict[str, Any] = {
            "model": self.config.model,
            "prompt": prompt,
            "resolution": self.config.resolution,
            "aspect_ratio": payload.aspect_ratio,
            "duration": payload.duration,
            "generate_audio": True,
        }
        if image_urls:
            frame_types = ("first_frame", "last_frame")
            body["frame_images"] = [
                {"type": "image_url", "image_url": {"url": url}, "frame_type": frame_types[index]}
                for index, url in enumerate(image_urls)
            ]
        return body

    def artifact_metadata(self, request_body: dict[str, Any]) -> dict[str, Any]:
        frames = request_body.get("frame_images")
        image_count = len(frames) if isinstance(frames, list) else 0
        source = "text-to-video" if image_count == 0 else "image-to-video" if image_count == 1 else "first-last-frame-to-video"
        return {"source": source, "inputImageCount": image_count, "generateAudio": True}

    def generate(self, payload: HailuoVideoGenerationRequest) -> HailuoVideoGenerationResponse:
        return super().generate(payload)
