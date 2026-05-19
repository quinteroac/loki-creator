from app.models import AgentDefinition


TOOL_BUILDER_AGENT = AgentDefinition(
    id="tool-builder",
    slug="tool-builder",
    name="Tool Builder",
    description="Built-in agent specialized in designing Loki-compatible tools.",
    default_model="Loki Default",
    default_skills=[],
    agent_skill_id="tool-builder",
)


BUILTIN_AGENTS = [TOOL_BUILDER_AGENT]
