from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.instructions import GeneratedCard


class SeedanceVideoGenerationRequest(BaseModel):
    prompt: str
    aspect_ratio: Literal["16:9", "9:16"] = Field(alias="aspectRatio")
    duration: Literal[4, 5, 7, 10, 15]
    selected_card_snapshots: list[dict[str, Any]] = Field(default_factory=list, alias="selectedCardSnapshots")
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class SeedanceVideoGenerationResponse(BaseModel):
    cards: list[GeneratedCard] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class GrokImageGenerationRequest(BaseModel):
    prompt: str
    aspect_ratio: Literal["1:1", "4:3", "16:9", "9:16"] = Field(alias="aspectRatio")
    resolution: Literal["1k", "2k"] = "1k"
    selected_card_snapshots: list[dict[str, Any]] = Field(default_factory=list, alias="selectedCardSnapshots")
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class GrokVideoGenerationRequest(BaseModel):
    prompt: str
    aspect_ratio: Literal["16:9", "9:16", "1:1", "4:3"] = Field(alias="aspectRatio")
    resolution: Literal["720p", "480p"] = "720p"
    duration: Literal[5, 10, 15]
    selected_card_snapshots: list[dict[str, Any]] = Field(default_factory=list, alias="selectedCardSnapshots")
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class GrokGenerationResponse(BaseModel):
    cards: list[GeneratedCard] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class CodexImageGenerationRequest(BaseModel):
    prompt: str
    resolution: Literal[
        "1024x1024",
        "1536x1024",
        "1024x1536",
        "2048x2048",
        "2048x1152",
        "3840x2160",
        "2160x3840",
        "auto",
    ] = "1024x1024"
    selected_card_snapshots: list[dict[str, Any]] = Field(default_factory=list, alias="selectedCardSnapshots")
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class CodexImageGenerationResponse(BaseModel):
    cards: list[GeneratedCard] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class GeminiImageGenerationRequest(BaseModel):
    prompt: str
    resolution: Literal[
        "1024x1024",
        "1536x1024",
        "1024x1536",
        "2048x2048",
        "2048x1152",
        "3840x2160",
        "2160x3840",
        "auto",
    ] = "1024x1024"
    model: Literal[
        "Gemini 3.5 Flash (Medium)",
        "Gemini 3.5 Flash (High)",
        "Gemini 3.5 Flash (Low)",
        "Gemini 3.1 Pro (Low)",
        "Gemini 3.1 Pro (High)",
        "Claude Sonnet 4.6 (Thinking)",
        "Claude Opus 4.6 (Thinking)",
        "GPT-OSS 120B (Medium)",
    ] = "Gemini 3.5 Flash (Medium)"
    selected_card_snapshots: list[dict[str, Any]] = Field(default_factory=list, alias="selectedCardSnapshots")
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class GeminiImageGenerationResponse(BaseModel):
    cards: list[GeneratedCard] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class ComfyGenerationRequest(BaseModel):
    prompt: str
    tool: Literal["image", "video"] = "image"
    image_mode: Literal["generate", "edit", "upscale"] = Field(default="generate", alias="imageMode")
    video_mode: Literal["t2v", "i2v", "flf2v", "wan22-i2v", "wan22-flf2v"] = Field(default="t2v", alias="videoMode")
    model_profile: str = Field(default="", alias="modelProfile")
    aspect_ratio: Literal["1:1", "4:3", "16:9", "9:16"] = Field(default="1:1", alias="aspectRatio")
    resolution: Literal["360p", "480p", "720p", "1080p"] = "480p"
    duration: Literal[4, 5, 7, 10, 15] = 5
    seed: int | None = None
    selected_card_snapshots: list[dict[str, Any]] = Field(default_factory=list, alias="selectedCardSnapshots")
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class ComfyGenerationResponse(BaseModel):
    cards: list[GeneratedCard] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)
