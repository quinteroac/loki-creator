from app.models import ToolConfigurationField, ToolDefinition, ToolPermissions, ToolRuntime


TOOL_INPUT_SCHEMA = {
    "type": "object",
    "required": ["prompt"],
    "properties": {
        "prompt": {"type": "string"},
        "context": {"type": "object"},
        "selectedCards": {"type": "array", "items": {"type": "string"}},
        "params": {"type": "object"},
    },
}

TOOL_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["cards"],
    "properties": {
        "cards": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "name", "prompt", "html"],
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "prompt": {"type": "string"},
                    "html": {"type": "string"},
                    "sourceToolId": {"type": "string"},
                },
            },
        },
    },
}


def create_builtin_tool(
    *,
    tool_id: str,
    name: str,
    description: str,
    capabilities: list[str],
    invocation_visibility: str = "frontend",
    input_schema: dict | None = None,
    output_schema: dict | None = None,
    configuration: list[ToolConfigurationField] | None = None,
) -> ToolDefinition:
    return ToolDefinition(
        id=tool_id,
        slug=tool_id,
        name=name,
        description=description,
        version="0.1.0",
        author="Loki",
        origin="built-in",
        source_type="builtin",
        invocation_visibility=invocation_visibility,
        capabilities=capabilities,
        input_schema=input_schema or TOOL_INPUT_SCHEMA,
        output_schema=output_schema or TOOL_OUTPUT_SCHEMA,
        exportable=False,
        runtime=ToolRuntime(source_type="builtin", entrypoint=tool_id),
        permissions=ToolPermissions(),
        configuration=configuration or [],
    )


TOOL_PACKAGE_DRAFT_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["cards"],
    "properties": {
        **TOOL_OUTPUT_SCHEMA["properties"],
        "draftPackage": {
            "type": "object",
            "description": "Planned structured ToolPackage draft. Until ToolResult supports extra fields, render this draft inside a review card.",
            "properties": {
                "manifestVersion": {"type": "string"},
                "tool": {"type": "object"},
                "assets": {"type": "array", "items": {"type": "string"}},
                "secretsRequired": {"type": "array", "items": {"type": "string"}},
                "integrity": {"type": "object"},
            },
        },
    },
}


BUILTIN_TOOLS = [
    create_builtin_tool(
        tool_id="auto",
        name="Auto",
        description="Lets the agent choose the most appropriate built-in tool for the prompt.",
        capabilities=["auto-select", "routing"],
    ),
    create_builtin_tool(
        tool_id="image",
        name="Image",
        description="Generates or edits image-oriented HTML canvas cards.",
        capabilities=["image-generation", "image-editing", "html-card-output"],
        configuration=[
            ToolConfigurationField(
                key="defaultModel",
                label="Default model",
                type="string",
                description="Preferred image model identifier used by this tool.",
            ),
            ToolConfigurationField(
                key="apiKey",
                label="API key",
                type="secret",
                description="Optional provider API key reference for image generation.",
                secret=True,
            ),
        ],
    ),
    create_builtin_tool(
        tool_id="video",
        name="Video",
        description="Generates or edits video-oriented HTML canvas cards.",
        capabilities=["video-generation", "video-editing", "html-card-output"],
        configuration=[
            ToolConfigurationField(
                key="defaultModel",
                label="Default model",
                type="string",
                description="Preferred video model identifier used by this tool.",
            ),
            ToolConfigurationField(
                key="maxDurationSeconds",
                label="Max duration",
                type="number",
                description="Default max duration in seconds for generated videos.",
                default=8,
            ),
        ],
    ),
    create_builtin_tool(
        tool_id="sfx",
        name="SFX",
        description="Creates sound effect concepts and visual HTML cards for audio assets.",
        capabilities=["audio-generation", "sfx", "html-card-output"],
    ),
    create_builtin_tool(
        tool_id="voice",
        name="Voice",
        description="Creates voice generation concepts and visual HTML cards for voice assets.",
        capabilities=["voice-generation", "audio", "html-card-output"],
    ),
    create_builtin_tool(
        tool_id="music",
        name="Music",
        description="Creates music generation concepts and visual HTML cards for music assets.",
        capabilities=["music-generation", "audio", "html-card-output"],
    ),
    create_builtin_tool(
        tool_id="3d-asset",
        name="3D Asset",
        description="Generates or edits 3D asset concepts and HTML preview cards.",
        capabilities=["3d-generation", "asset-generation", "html-card-output"],
    ),
    create_builtin_tool(
        tool_id="gaussian-splat",
        name="Gaussian Splat",
        description="Generates gaussian splat concepts and HTML preview cards.",
        capabilities=["gaussian-splat", "3d", "html-card-output"],
    ),
    create_builtin_tool(
        tool_id="world-generation",
        name="World Generation",
        description="Generates virtual world concepts and HTML preview cards.",
        capabilities=["world-generation", "environment-generation", "html-card-output"],
    ),
    create_builtin_tool(
        tool_id="html-5-canva",
        name="HTML 5 Canva",
        description="Generates HTML-first canvas cards for interactive or visual compositions.",
        capabilities=["html", "canvas", "interactive-card-output"],
    ),
    create_builtin_tool(
        tool_id="tool-creator",
        name="Tool Creator",
        description="Creates draft tool contracts and manifests for future user-created tools.",
        capabilities=["tool-creation", "manifest-generation", "html-card-output"],
    ),
    create_builtin_tool(
        tool_id="tool-requirements-analyzer",
        name="Tool Requirements Analyzer",
        description="Internal Tool Builder capability that converts a user request into Loki tool requirements.",
        capabilities=["tool-creation", "requirements-analysis", "agent-internal"],
        invocation_visibility="internal",
    ),
    create_builtin_tool(
        tool_id="tool-contract-drafter",
        name="Tool Contract Drafter",
        description="Internal Tool Builder capability that drafts ToolDefinition and ToolPackage-compatible contracts.",
        capabilities=["tool-creation", "contract-drafting", "manifest-generation", "agent-internal"],
        invocation_visibility="internal",
        output_schema=TOOL_PACKAGE_DRAFT_OUTPUT_SCHEMA,
    ),
    create_builtin_tool(
        tool_id="tool-preview-card-builder",
        name="Tool Preview Card Builder",
        description="Internal Tool Builder capability that renders a tool draft as a Loki canvas review card.",
        capabilities=["tool-creation", "html-card-output", "preview-card", "agent-internal"],
        invocation_visibility="internal",
        output_schema=TOOL_PACKAGE_DRAFT_OUTPUT_SCHEMA,
    ),
    create_builtin_tool(
        tool_id="hello-world",
        name="Hello World",
        description="Simple built-in tool that returns an HTML canvas card with the requested greeting text.",
        capabilities=["dummy", "html-card-output"],
    ),
    create_builtin_tool(
        tool_id="browser-tool",
        name="Browser Tool",
        description="Internal browser automation capability for agents that need to inspect or interact with web pages.",
        capabilities=["browser", "web-inspection", "agent-internal"],
        invocation_visibility="internal",
        configuration=[
            ToolConfigurationField(
                key="headless",
                label="Headless mode",
                type="boolean",
                description="Run browser automation without a visible browser window.",
                default=True,
            )
        ],
    ),
]
