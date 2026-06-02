from app.models import AgentDefinition


BASE_AGENT_DEFAULT_SKILLS = [
    "imagegen",
]

BASE_AGENT = AgentDefinition(
    id="base-agent",
    slug="base-agent",
    name="Base Agent",
    description="Default Loki agent behavior for creating canvas cards through skills.",
    default_model="GPT-5.4 mini (openai-codex)",
    default_skills=BASE_AGENT_DEFAULT_SKILLS,
    agent_skill_id="base-agent",
)

BUILTIN_AGENTS = [BASE_AGENT]
