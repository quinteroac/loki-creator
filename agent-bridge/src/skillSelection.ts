import { agents, directPiToolBySkillId, directPiToolSkillByToolName } from "./config";
import type { AgentRuntimeMode, LokiSkill } from "./types";

export function normalizeSkillName(value: string) {
  return value.trim().toLowerCase().replace(/\s+/g, "-");
}

export function toPiSkillToolName(skill: LokiSkill) {
  return `loki_skill_${skill.id.replace(/[^a-zA-Z0-9_]/g, "_")}`;
}

export function directPiToolForSkill(skill: LokiSkill) {
  return directPiToolBySkillId[skill.id];
}

export function isDirectPiToolRoutedSkill(skill: LokiSkill, runtimeMode: AgentRuntimeMode) {
  return runtimeMode === "pi-tools" && Boolean(directPiToolForSkill(skill));
}

export function formatSkillRuntimeTarget(skill: LokiSkill, runtimeMode: AgentRuntimeMode) {
  if (runtimeMode === "grok-build-stdio") return `${skill.name} (${skill.id})`;
  const directToolName = directPiToolForSkill(skill);
  return `${skill.name} (${directToolName || toPiSkillToolName(skill)})`;
}

export function findDirectPiToolSkill(toolName: string, selectedSkills: LokiSkill[]) {
  const skillId = directPiToolSkillByToolName.get(toolName);
  if (!skillId) return null;
  return selectedSkills.find((skill) => skill.id === skillId) ?? null;
}

export function hasDirectPiToolRoutedSkill(selectedSkills: LokiSkill[], runtimeMode: AgentRuntimeMode) {
  return selectedSkills.some((skill) => isDirectPiToolRoutedSkill(skill, runtimeMode));
}

export function getAgentRuntimeMode(model: { provider?: string } | undefined): AgentRuntimeMode {
  const provider = model?.provider?.toLowerCase() ?? "";
  const id = "id" in (model ?? {}) && typeof (model as { id?: unknown }).id === "string"
    ? (model as { id: string }).id.toLowerCase()
    : "";
  const name = "name" in (model ?? {}) && typeof (model as { name?: unknown }).name === "string"
    ? (model as { name: string }).name.toLowerCase()
    : "";
  if (provider === "pi-grok-build" || provider === "xai" || id.includes("grok") || name.includes("grok")) {
    return "grok-build-stdio";
  }
  return "pi-tools";
}

function getDefaultSkillIds(agentId: string) {
  return agents.find((agent) => agent.id === agentId)?.defaultSkills ?? [];
}

export function selectSkillsForAgent(availableSkills: LokiSkill[], selectedSkills: string[], agentId: string) {
  const normalizedSelected = selectedSkills.map(normalizeSkillName);
  const isAuto = normalizedSelected.length === 0 || normalizedSelected.includes("auto");
  const defaultSkillIds = getDefaultSkillIds(agentId).map(normalizeSkillName);

  if (isAuto) {
    if (defaultSkillIds.length === 0) return availableSkills;

    return availableSkills.filter((skill) => {
      const candidates = [skill.id, skill.name].map(normalizeSkillName);
      return candidates.some((candidate) => defaultSkillIds.includes(candidate));
    });
  }

  return availableSkills.filter((skill) => {
    const candidates = [skill.id, skill.name].map(normalizeSkillName);
    return candidates.some((candidate) => normalizedSelected.includes(candidate));
  });
}
