from datetime import datetime
from typing import Any, Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.instructions import GeneratedCard


SourceType = Literal["builtin", "http", "cli-local", "cli-remote"]
JobStatus = Literal["queued", "running", "succeeded", "failed"]
ToolInvocationVisibility = Literal["frontend", "internal"]


class ToolRuntime(BaseModel):
    source_type: SourceType = Field(alias="sourceType")
    entrypoint: str | None = None
    command: list[str] = Field(default_factory=list)
    method: str = "POST"
    timeout_seconds: int = Field(default=120, alias="timeoutSeconds")
    working_directory: str | None = Field(default=None, alias="workingDirectory")

    model_config = ConfigDict(populate_by_name=True)


class ToolPermissions(BaseModel):
    network: bool = False
    filesystem: bool = False
    env_vars: list[str] = Field(default_factory=list, alias="envVars")
    allowed_commands: list[str] = Field(default_factory=list, alias="allowedCommands")

    model_config = ConfigDict(populate_by_name=True)


class ToolConfigurationField(BaseModel):
    key: str
    label: str
    type: Literal["string", "number", "boolean", "select", "secret"]
    description: str | None = None
    required: bool = False
    default: Any = None
    options: list[str] = Field(default_factory=list)
    secret: bool = False

    model_config = ConfigDict(populate_by_name=True)


class ToolDefinition(BaseModel):
    id: str
    slug: str
    name: str
    description: str
    version: str = "0.1.0"
    author: str = "Loki"
    origin: Literal["built-in", "user"] = "built-in"
    source_type: SourceType = Field(alias="sourceType")
    invocation_visibility: ToolInvocationVisibility = Field(default="frontend", alias="invocationVisibility")
    capabilities: list[str] = Field(default_factory=list)
    input_schema: dict[str, Any] = Field(default_factory=dict, alias="inputSchema")
    output_schema: dict[str, Any] = Field(default_factory=dict, alias="outputSchema")
    exportable: bool = False
    created_by: str | None = Field(default=None, alias="createdBy")
    created_at: datetime | None = Field(default=None, alias="createdAt")
    updated_at: datetime | None = Field(default=None, alias="updatedAt")
    runtime: ToolRuntime
    permissions: ToolPermissions = Field(default_factory=ToolPermissions)
    configuration: list[ToolConfigurationField] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class ToolPackage(BaseModel):
    manifest_version: str = Field(alias="manifestVersion")
    tool: ToolDefinition
    assets: list[str] = Field(default_factory=list)
    secrets_required: list[str] = Field(default_factory=list, alias="secretsRequired")
    integrity: dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class ToolInvocationRequest(BaseModel):
    tool_id: str = Field(alias="toolId")
    prompt: Annotated[str, Field(min_length=1, max_length=4000)]
    context: dict[str, Any] = Field(default_factory=dict)
    selected_cards: list[str] = Field(default_factory=list, alias="selectedCards")
    params: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class ToolResult(BaseModel):
    cards: list[GeneratedCard] = Field(default_factory=list)


class ToolJob(BaseModel):
    id: str
    tool_id: str = Field(alias="toolId")
    status: JobStatus
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    result: ToolResult | None = None
    error: str | None = None

    model_config = ConfigDict(populate_by_name=True)
