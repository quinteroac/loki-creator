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


class VideoTrimRequest(VideoArtifactRequest):
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
    width: int
    height: int
    duration_seconds: float | None = Field(default=None, alias="durationSeconds")
    time_seconds: float | None = Field(default=None, alias="timeSeconds")
    start_seconds: float | None = Field(default=None, alias="startSeconds")
    end_seconds: float | None = Field(default=None, alias="endSeconds")
