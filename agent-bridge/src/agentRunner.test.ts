import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { describe, expect, test } from "bun:test";
import { resolve } from "node:path";

import {
  buildAgentPrompt,
  directPiToolForSkill,
  findNextSkillQuestion,
  mergeRequestAnswers,
  parseSkillParamsJson,
  selectSkillsForAgent,
} from "./agentRunner";
import { collectLocalMediaReferences, resolveLocalArtifactPath } from "./mediaReferences";
import { repoRoot } from "./config";
import type { AgentRunRequest, LokiSkill } from "./types";

function makeSkill(overrides: Partial<LokiSkill>): LokiSkill {
  return {
    id: "imagegen",
    name: "imagegen",
    description: "Generate images",
    path: "backend/skills/imagegen",
    origin: "built-in",
    capabilities: [],
    arguments: [],
    ...overrides,
  };
}

describe("agent bridge contracts", () => {
  test("selects the base agent default skill in auto mode", () => {
    const imagegen = makeSkill({ id: "imagegen", name: "imagegen" });
    const music = makeSkill({ id: "comfy-musicgen", name: "comfy-musicgen" });

    expect(selectSkillsForAgent([imagegen, music], ["auto"], "base-agent")).toEqual([imagegen]);
  });

  test("resolves explicit selected skills by id or name", () => {
    const imagegen = makeSkill({ id: "imagegen", name: "Image Gen" });
    const cleanup = makeSkill({ id: "media-cleanup", name: "Media Cleanup" });

    expect(selectSkillsForAgent([imagegen, cleanup], ["media-cleanup"], "base-agent")).toEqual([cleanup]);
    expect(selectSkillsForAgent([imagegen, cleanup], ["Image Gen"], "base-agent")).toEqual([imagegen]);
  });

  test("asks required skill arguments in declared order and honors dependsOn", () => {
    const skill = makeSkill({
      id: "comfy-videogen",
      arguments: [
        {
          id: "resolution",
          label: "Resolution",
          type: "choice",
          required: true,
          askWhen: "always",
          dependsOn: { mode: "advanced" },
          options: [{ value: "720p" }],
          order: 2,
        },
        {
          id: "mode",
          label: "Mode",
          type: "choice",
          required: true,
          askWhen: "always",
          options: [{ value: "basic" }, { value: "advanced" }],
          order: 1,
        },
      ],
    });

    expect(findNextSkillQuestion([skill], {})?.id).toBe("comfy-videogen.mode");
    expect(findNextSkillQuestion([skill], { mode: "advanced" })?.id).toBe("comfy-videogen.resolution");
    expect(findNextSkillQuestion([skill], { mode: "basic" })).toBeNull();
  });

  test("invalid paramsJson fails instead of silently becoming empty params", () => {
    expect(() => parseSkillParamsJson("{bad json")).toThrow();
    expect(() => parseSkillParamsJson("[]")).toThrow("paramsJson must be a JSON object.");
  });

  test("direct Pi tool routing is explicit", () => {
    expect(directPiToolForSkill(makeSkill({ id: "imagegen" }))).toBeUndefined();
    expect(directPiToolForSkill(makeSkill({ id: "comfy-image-generate" }))).toBeUndefined();
  });

  test("merges request answers without dropping explicit collected args", () => {
    expect(mergeRequestAnswers({ aspectRatio: "1:1" }, { duration: "5" })).toEqual({
      aspectRatio: "1:1",
      duration: "5",
    });
  });

  test("agent prompt preserves explicit skill invocation requirements", () => {
    const request: AgentRunRequest = {
      prompt: "create an image",
      agentId: "base-agent",
      model: "GPT-5.4 mini (openai-codex)",
      skills: ["imagegen"],
      selectedCards: [],
      context: {},
    };

    const prompt = buildAgentPrompt(request, [makeSkill({ id: "imagegen", name: "imagegen" })], "pi-tools");

    expect(prompt).toContain("The user selected these skills explicitly");
    expect(prompt).toContain("For imagegen, call loki_skill_imagegen");
  });

  test("imagegen prompt treats selected images as edit targets for edit requests", () => {
    const request: AgentRunRequest = {
      prompt: "change the shirt to red",
      agentId: "base-agent",
      model: "GPT-5.4 mini (openai-codex)",
      skills: ["imagegen"],
      selectedCards: ["card_1"],
      selectedCardSnapshots: [
        {
          id: "card_1",
          name: "portrait",
          displayTitle: "Portrait",
          prompt: "original portrait",
          html: "<img />",
          mediaAssets: [
            {
              kind: "image",
              src: "/api/artifacts/skills/imagegen/input.png",
              mimeType: "image/png",
            },
          ],
        },
      ],
      context: {},
    };

    const prompt = buildAgentPrompt(request, [makeSkill({ id: "imagegen", name: "imagegen" })], "pi-tools");

    expect(prompt).toContain("Imagegen selected-image edit contract");
    expect(prompt).toContain("selected local artifact path as the edit target");
    expect(prompt).toContain("Do not generate a fresh unrelated image");
    expect(prompt).toContain("Do not downgrade an edit request into reference generation");
  });

  test("local media references resolve only Loki artifacts", async () => {
    const artifactPath = resolve(repoRoot, ".loki/test-agent-bridge-media/input.png");
    const artifactUrl = "/api/artifacts/test-agent-bridge-media/input.png";
    await mkdir(resolve(repoRoot, ".loki/test-agent-bridge-media"), { recursive: true });
    await writeFile(artifactPath, "png");

    try {
      expect(resolveLocalArtifactPath(artifactUrl)).toBe(artifactPath);
      await expect(collectLocalMediaReferences({
        prompt: "edit",
        model: "GPT-5.4 mini (openai-codex)",
        skills: ["imagegen"],
        selectedCards: ["card_1"],
        context: {},
        selectedCardSnapshots: [
          {
            id: "card_1",
            name: "input",
            displayTitle: "Input",
            prompt: "",
            html: "<img />",
            mediaAssets: [{ kind: "image", src: artifactUrl, dataUrl: "data:image/png;base64,Zm9v" }],
          },
        ],
      })).resolves.toMatchObject([
        {
          kind: "image",
          artifactUrl,
          path: artifactPath,
          source: "selected-card-media-asset",
        },
      ]);
      expect(() => resolveLocalArtifactPath("data:image/png;base64,Zm9v")).toThrow("must be a Loki artifact URL");
    } finally {
      await rm(resolve(repoRoot, ".loki/test-agent-bridge-media"), { recursive: true, force: true });
    }
  });

  test("runner does not include text-freeform skill execution fallback", async () => {
    const source = await readFile(new URL("./agentRunner.ts", import.meta.url), "utf8");

    expect(source).not.toContain("runSelectedSkillFromAgentReasoning");
    expect(source).not.toContain("extractFallbackParamsFromAgentText");
    expect(source).not.toContain("extractOperationalPromptFromAgentText");
  });
});
