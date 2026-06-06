import type { AgentQuestion, LokiSkill, LokiSkillArgument } from "./types";

export function normalizeAnswerValue(value: unknown) {
  return typeof value === "string" ? value.trim() : "";
}

function createArgumentQuestion(skill: LokiSkill, argument: LokiSkillArgument): AgentQuestion {
  return {
    id: `${skill.id}.${argument.id}`,
    text: argument.description ? `${argument.label}: ${argument.description}` : argument.label,
    inputType: argument.type === "choice" ? "choice" : "text",
    options: (argument.options ?? []).map((option) => ({
      value: String(option.value),
      label: option.label ?? option.value,
      description: option.description ?? null,
    })),
    skillId: skill.id,
    argumentId: argument.id,
  };
}

function argumentDependsOnMatches(argument: LokiSkillArgument, collectedArgs: Record<string, string>) {
  const dependencies = argument.dependsOn ?? {};
  return Object.entries(dependencies).every(([argumentId, expectedValue]) => (
    normalizeAnswerValue(collectedArgs[argumentId]) === String(expectedValue)
  ));
}

export function findNextSkillQuestion(selectedSkills: LokiSkill[], collectedArgs: Record<string, string>) {
  const candidates = selectedSkills
    .flatMap((skill) => (skill.arguments ?? []).map((argument) => ({ skill, argument })))
    .filter(({ argument }) => (argument.required || argument.askWhen === "always") && argumentDependsOnMatches(argument, collectedArgs))
    .sort((left, right) => {
      const orderDelta = (left.argument.order ?? 0) - (right.argument.order ?? 0);
      if (orderDelta !== 0) return orderDelta;
      return `${left.skill.id}.${left.argument.id}`.localeCompare(`${right.skill.id}.${right.argument.id}`);
    });

  for (const { skill, argument } of candidates) {
    const existingValue = normalizeAnswerValue(collectedArgs[argument.id]);
    const validChoice = argument.type !== "choice"
      || argument.options.length === 0
      || argument.options.some((option) => option.value === existingValue);
    if (!existingValue || !validChoice) {
      return createArgumentQuestion(skill, argument);
    }
  }

  return null;
}

export function mergeRequestAnswers(
  collectedArgs: Record<string, string>,
  answers?: Record<string, string>,
) {
  for (const [key, value] of Object.entries(answers ?? {})) {
    const answer = normalizeAnswerValue(value);
    if (answer) {
      collectedArgs[key] = answer;
    }
  }

  return collectedArgs;
}
