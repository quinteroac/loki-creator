from pydantic import BaseModel, ConfigDict, Field


class AgentSkillStep(BaseModel):
    id: str
    order: int
    skill_id: str = Field(alias="skillId")
    input_card_ids: list[str] = Field(default_factory=list, alias="inputCardIds")
    output_card_ids: list[str] = Field(default_factory=list, alias="outputCardIds")
    prompt: str

    model_config = ConfigDict(populate_by_name=True)


class AgentSkillDefinition(BaseModel):
    id: str
    agent_id: str = Field(alias="agentId")
    name: str
    description: str
    steps: list[AgentSkillStep] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class AgentDefinition(BaseModel):
    id: str
    slug: str
    name: str
    description: str
    version: str = "0.1.0"
    author: str = "Loki"
    default_model: str | None = Field(default=None, alias="defaultModel")
    default_skills: list[str] = Field(default_factory=list, alias="defaultSkills")
    agent_skill_id: str = Field(alias="agentSkillId")

    model_config = ConfigDict(populate_by_name=True)
