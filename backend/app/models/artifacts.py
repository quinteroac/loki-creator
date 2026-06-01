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
