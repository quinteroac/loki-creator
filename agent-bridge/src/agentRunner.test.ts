import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { describe, expect, test } from "bun:test";
import { resolve } from "node:path";

import {
  buildAgentPrompt,
  directPiToolForSkill,
  findNextSkillQuestion,
  formatAvailableAgentModels,
  mergeRequestAnswers,
  parseSkillParamsJson,
  selectSkillsForAgent,
  skillParamsFromGrokBuildText,
  validateSelectedBboxGuidePropagation,
} from "./agentRunner";
import { collectLocalMediaReferences, resolveLocalArtifactPath } from "./mediaReferences";
import { repoRoot } from "./config";
import { getAgentRuntimeMode } from "./skillSelection";
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

function bboxRequest(): AgentRunRequest {
  return {
    prompt: "generate the scene using the selected boxes",
    agentId: "base-agent",
    model: "GPT-5.4 mini (openai-codex)",
    skills: ["ideogram4-image"],
    selectedCards: ["card_bbox"],
    selectedCardSnapshots: [
      {
        id: "card_bbox",
        name: "BBox",
        displayTitle: "BBox",
        prompt: "1 bbox, 1 with prompt on white canvas",
        html: "",
        metadata: {
          kind: "bbox",
          bboxData: {
            version: 1,
            canvas: { width: 1024, height: 1024, aspectRatio: "1:1" },
            source: null,
            boxes: [
              {
                id: "bbox_1",
                label: "Box 1",
                prompt: "black cat sitting on roof tiles",
                x: 0.1,
                y: 0.2,
                width: 0.3,
                height: 0.4,
                ideogramBbox: [200, 100, 600, 400],
              },
            ],
          },
        },
        structuredData: {
          kind: "bbox",
          compositionGuide: {
            version: 1,
            canvas: { width: 1024, height: 1024, aspectRatio: "1:1" },
            source: null,
            boxes: [
              {
                id: "bbox_1",
                label: "Box 1",
                prompt: "black cat sitting on roof tiles",
                normalized: { x: 0.1, y: 0.2, width: 0.3, height: 0.4 },
                ideogramBbox: [200, 100, 600, 400],
              },
            ],
          },
        },
      },
    ],
    context: {},
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

  test("agent model list hides providers reserved for direct generation flows", () => {
    expect(formatAvailableAgentModels([
      { id: "bytedance/seedance-2.0-fast", provider: "openrouter", name: "Seedance 2.0 Fast" },
      { id: "gpt-5.4-mini", provider: "openai-codex", name: "GPT-5.4 mini" },
      { id: "grok-build", provider: "pi-grok-build", name: "Grok Build" },
    ])).toEqual([
      {
        id: "gpt-5.4-mini",
        provider: "openai-codex",
        name: "GPT-5.4 mini",
        label: "GPT-5.4 mini (openai-codex)",
      },
      {
        id: "grok-build",
        provider: "pi-grok-build",
        name: "Grok Build",
        label: "Grok Build (pi-grok-build)",
      },
    ]);
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

  test("grok-build prompt asks for bridge-executable skill params", () => {
    const request: AgentRunRequest = {
      prompt: "create an image",
      agentId: "base-agent",
      model: "Grok Build (pi-grok-build)",
      skills: ["imagegen"],
      selectedCards: [],
      context: {},
    };

    const prompt = buildAgentPrompt(request, [makeSkill({ id: "imagegen", name: "imagegen" })], "grok-build-stdio");

    expect(prompt).toContain("Explicit user-selected project skills");
    expect(prompt).toContain("backend/skills/imagegen/SKILL.md");
    expect(prompt).not.toContain(".grok/skills");
    expect(prompt).toContain("finish with a concise final operational prompt and a JSON object of structured params");
    expect(prompt).toContain("the Loki bridge will execute it");
    expect(prompt).not.toContain("loki_skill_imagegen");
  });

  test("routes Grok-like agent models through the Grok stdio bridge", () => {
    expect(getAgentRuntimeMode({ id: "grok-4", provider: "xai", name: "Grok 4" })).toBe("grok-build-stdio");
    expect(getAgentRuntimeMode({ id: "xai/grok-code-fast", provider: "pi", name: "Grok Code Fast" })).toBe("grok-build-stdio");
    expect(getAgentRuntimeMode({ id: "gpt-5.4-mini", provider: "openai-codex", name: "GPT-5.4 mini" })).toBe("pi-tools");
  });

  test("extracts Grok Build final text into skill params", () => {
    const params = skillParamsFromGrokBuildText(`Use this exact image edit prompt.

\`\`\`json
{"prompt":"Only change the jacket to red. Preserve everything else.","params":{"aspectRatio":"1:1","modelProfile":"wan22-bernini-image"},"title":"Red jacket edit"}
\`\`\``);

    expect(params.prompt).toBe("Only change the jacket to red. Preserve everything else.");
    expect(params.title).toBe("Red jacket edit");
    expect(JSON.parse(params.paramsJson ?? "{}")).toEqual({
      aspectRatio: "1:1",
      modelProfile: "wan22-bernini-image",
    });
    expect(params.outputText).toContain("Use this exact image edit prompt");
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

  test("agent prompt exposes selected bbox composition guides as generation contracts", () => {
    const request = bboxRequest();

    const prompt = buildAgentPrompt(
      request,
      [makeSkill({ id: "ideogram4-image", name: "Ideogram 4 Image", description: "Generate Ideogram images" })],
      "pi-tools",
    );

    expect(prompt).toContain("Selected bbox composition guide contract");
    expect(prompt).toContain("authoritative layout contract");
    expect(prompt).toContain("structuredData");
    expect(prompt).toContain('"prompt": "black cat sitting on roof tiles"');
    expect(prompt).toContain('"ideogramBbox": [');
    expect(prompt).toContain("Do not invent replacement boxes");
    expect(prompt).toContain("silently ignore selected bbox cards");
    expect(prompt).toContain("fail or ask_user instead of generating without it");
    expect(prompt).toContain("Preserve every box's ideogramBbox");
  });

  test("bbox guide validation rejects skill calls that omit selected bbox contracts", () => {
    const errors = validateSelectedBboxGuidePropagation(bboxRequest(), {
      prompt: "draw a cat on a roof",
      paramsJson: JSON.stringify({ objects: [] }),
    });

    expect(errors.join("\n")).toContain("ideogramBbox [200,100,600,400] was not passed");
    expect(errors.join("\n")).toContain("prompt was not passed");
  });

  test("bbox guide validation accepts exact bbox coordinates and prompt in skill params", () => {
    const errors = validateSelectedBboxGuidePropagation(bboxRequest(), {
      prompt: "draw a black cat sitting on roof tiles in the selected box",
      paramsJson: JSON.stringify({
        objects: [
          {
            bbox: [200, 100, 600, 400],
            description: "black cat sitting on roof tiles",
          },
        ],
      }),
    });

    expect(errors).toEqual([]);
  });

  test("bbox guide validation reads bbox metadata when structuredData is absent", () => {
    const request = bboxRequest();
    delete request.selectedCardSnapshots?.[0]?.structuredData;

    const errors = validateSelectedBboxGuidePropagation(request, {
      prompt: "draw a black cat sitting on roof tiles",
      paramsJson: JSON.stringify({ objects: [{ bbox: [200, 100, 600, 400] }] }),
    });

    expect(errors).toEqual([]);
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
      const prompt = buildAgentPrompt({
        prompt: "edit",
        model: "GPT-5.4 mini (openai-codex)",
        skills: ["imagegen"],
        selectedCards: ["card_1"],
        context: {
          localMediaReferences: [
            {
              kind: "image",
              artifactUrl,
              path: artifactPath,
              source: "selected-card-media-asset",
              cardId: "card_1",
            },
          ],
        },
        selectedCardSnapshots: [
          {
            id: "card_1",
            name: "input",
            displayTitle: "Input",
            prompt: "",
            html: "<img />",
            mediaAssets: [{ kind: "image", src: artifactUrl }],
          },
        ],
      }, [makeSkill({ id: "imagegen", name: "imagegen" })], "pi-tools");
      expect(prompt).toContain(`path=${artifactPath}`);
      expect(prompt).toContain(`artifactUrl=${artifactUrl}`);
      expect(() => resolveLocalArtifactPath("data:image/png;base64,Zm9v")).toThrow("must be a Loki artifact URL");
    } finally {
      await rm(resolve(repoRoot, ".loki/test-agent-bridge-media"), { recursive: true, force: true });
    }
  });

  test("Grok Build bridge is scoped to selected skill final params", async () => {
    const source = await readFile(new URL("./agentRunner.ts", import.meta.url), "utf8");

    expect(source).toContain("runtimeMode === \"grok-build-stdio\"");
    expect(source).toContain("selectedSkills.length > 0");
    expect(source).toContain("chooseGrokBuildBridgeSkill");
    expect(source).toContain("skillParamsFromGrokBuildText");
  });
});
