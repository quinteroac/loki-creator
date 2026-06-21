from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ArchiveArtifactsRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    artifact_urls: list[str] = Field(default_factory=list, alias="artifactUrls")


class ArchivedArtifact(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    artifact_url: str = Field(alias="artifactUrl")
    deleted_path: str | None = Field(default=None, alias="deletedPath")
    status: str


class ArchiveArtifactsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    artifacts: list[ArchivedArtifact] = Field(default_factory=list)


class ImportedArtifact(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    artifact_url: str = Field(alias="artifactUrl")
    name: str
    mime_type: str = Field(alias="mimeType")
    size: int


class VideoArtifactRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    artifact_url: str = Field(alias="artifactUrl")


class VideoTimelineRequest(VideoArtifactRequest):
    max_thumbnails: int | None = Field(default=None, alias="maxThumbnails")
    lut_id: str | None = Field(default=None, alias="lutId")
    effect_id: str | None = Field(default=None, alias="effectId")


class VideoLutOption(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    label: str


class VideoEffectOption(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    label: str
    kind: Literal["filter", "generator"]
    available: bool


class VideoTimelineThumbnail(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    artifact_url: str = Field(alias="artifactUrl")
    time_seconds: float = Field(alias="timeSeconds")
    width: int
    height: int


class VideoTimelineResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    artifact_url: str = Field(alias="artifactUrl")
    duration_seconds: float = Field(alias="durationSeconds")
    width: int
    height: int
    fps: float
    thumbnails: list[VideoTimelineThumbnail] = Field(default_factory=list)


class VideoFrameRequest(VideoArtifactRequest):
    time_seconds: float = Field(alias="timeSeconds")
    lut_id: str | None = Field(default=None, alias="lutId")
    effect_id: str | None = Field(default=None, alias="effectId")


class VideoTrimRequest(VideoArtifactRequest):
    start_seconds: float = Field(alias="startSeconds")
    end_seconds: float = Field(alias="endSeconds")
    lut_id: str | None = Field(default=None, alias="lutId")
    effect_id: str | None = Field(default=None, alias="effectId")


class VideoImageRequest(VideoArtifactRequest):
    duration_seconds: float = Field(default=5, alias="durationSeconds")
    fps: float = 24
    lut_id: str | None = Field(default=None, alias="lutId")
    effect_id: str | None = Field(default=None, alias="effectId")


class AudioArtifactRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    artifact_url: str = Field(alias="artifactUrl")


class AudioTimelineRequest(AudioArtifactRequest):
    max_peaks: int | None = Field(default=None, alias="maxPeaks")


class AudioTimelineResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    artifact_url: str = Field(alias="artifactUrl")
    duration_seconds: float = Field(alias="durationSeconds")
    sample_rate: int = Field(alias="sampleRate")
    channels: int
    peaks: list[float] = Field(default_factory=list)


class AudioTrimRequest(AudioArtifactRequest):
    start_seconds: float = Field(alias="startSeconds")
    end_seconds: float = Field(alias="endSeconds")


class VideoEditArtifact(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    artifact_url: str = Field(alias="artifactUrl")
    source_artifact_url: str = Field(alias="sourceArtifactUrl")
    name: str
    kind: str
    mime_type: str = Field(alias="mimeType")
    size: int
    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = Field(default=None, alias="durationSeconds")
    fps: float | None = None
    time_seconds: float | None = Field(default=None, alias="timeSeconds")
    start_seconds: float | None = Field(default=None, alias="startSeconds")
    end_seconds: float | None = Field(default=None, alias="endSeconds")
    sample_rate: int | None = Field(default=None, alias="sampleRate")
    channels: int | None = None
    lut_id: str | None = Field(default=None, alias="lutId")
    lut_label: str | None = Field(default=None, alias="lutLabel")
    effect_id: str | None = Field(default=None, alias="effectId")
    effect_label: str | None = Field(default=None, alias="effectLabel")
