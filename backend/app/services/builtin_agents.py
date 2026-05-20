from app.models import AgentDefinition


BASE_AGENT_DEFAULT_SKILLS = [
    "hyperframes",
    "hyperframes-cli",
    "hyperframes-registry",
    "gsap",
    "css-animations",
    "waapi",
]

BASE_AGENT = AgentDefinition(
    id="base-agent",
    slug="base-agent",
    name="Base Agent",
    description="Default Loki agent behavior with core built-in creative skills.",
    default_model="Loki Default",
    default_skills=BASE_AGENT_DEFAULT_SKILLS,
    agent_skill_id="base-agent",
)

TOOL_BUILDER_AGENT = AgentDefinition(
    id="tool-builder",
    slug="tool-builder",
    name="Tool Builder",
    description="Built-in agent specialized in designing Loki-compatible tools.",
    default_model="Loki Default",
    default_skills=[],
    agent_skill_id="tool-builder",
)


BUILTIN_AGENTS = [BASE_AGENT, TOOL_BUILDER_AGENT]
