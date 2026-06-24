import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { describe, expect, test } from "bun:test";
import { resolve } from "node:path";

import {
  agents,
  buildAgentPrompt,
  directPiToolForSkill,
  findNextSkillQuestion,
  formatAvailableAgentModels,
  mergeRequestAnswers,
  parseSkillParamsJson,
  selectSkillsForAgent,
  skillParamsFromGrokBuildText,
  selectDescribeImageReference,
  shouldExposeDescribeLokiImageTool,
  validateIdeogram4ParamsJson,
  validateReferencePromptPlaceholders,
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

  test("selects Video Director default production skills in auto mode", () => {
    const skills = [
      makeSkill({ id: "video-director-os", name: "video-director-os" }),
      makeSkill({ id: "imagegen", name: "imagegen" }),
      makeSkill({ id: "comfy-videoedit", name: "comfy-videoedit" }),
      makeSkill({ id: "openrouter-seedance-video", name: "openrouter-seedance-video" }),
      makeSkill({ id: "grok-imagine-video", name: "grok-imagine-video" }),
      makeSkill({ id: "unrelated", name: "unrelated" }),
    ];

    const selected = selectSkillsForAgent(skills, ["auto"], "video-director").map((skill) => skill.id);

    expect(selected).toContain("video-director-os");
    expect(selected).toContain("imagegen");
    expect(selected).toContain("comfy-videoedit");
    expect(selected).toContain("openrouter-seedance-video");
    expect(selected).toContain("grok-imagine-video");
    expect(selected).not.toContain("unrelated");
    expect(agents.find((agent) => agent.id === "video-director")?.name).toBe("Video Director");
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

  test("ideogram4 params validation rejects incomplete structured params", () => {
    const errors = validateIdeogram4ParamsJson({
      prompt: "Premium poster",
      paramsJson: JSON.stringify({
        mode: "t2i",
        qualityProfile: "Default",
        aspectRatio: "1:1",
        styleArtStyle: "poster art",
        background: "plain studio background",
        objects: [{ bbox: [120, 120, 880, 880], description: "centered subject" }],
      }),
    });

    expect(errors.join(" ")).toContain("styleAesthetics");
    expect(errors.join(" ")).toContain("styleLighting");
    expect(errors.join(" ")).toContain("styleMedium");
  });

  test("ideogram4 params validation accepts complete structured params", () => {
    const errors = validateIdeogram4ParamsJson({
      prompt: "Premium poster",
      paramsJson: JSON.stringify({
        mode: "t2i",
        qualityProfile: "Default",
        aspectRatio: "1:1",
        styleAesthetics: "bold clean graphic design, high detail",
        styleLighting: "flat even studio lighting",
        styleMedium: "illustration",
        styleArtStyle: "poster art",
        background: "plain studio background",
        objects: [{ bbox: [120, 120, 880, 880], description: "centered subject" }],
      }),
    });

    expect(errors).toEqual([]);
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

  test("explicit local Comfy image prompt does not steer adult requests into plain-text refusals", () => {
    const request: AgentRunRequest = {
      prompt: "create an adult fantasy pinup illustration",
      agentId: "base-agent",
      model: "GPT-5.4 mini (openai-codex)",
      skills: ["comfy-image-generate"],
      selectedCards: [],
      context: {},
    };

    const prompt = buildAgentPrompt(
      request,
      [makeSkill({ id: "comfy-image-generate", name: "comfy-image-generate" })],
      "pi-tools",
    );

    expect(prompt).toContain("adult/NSFW visual intent is a valid local model prompt");
    expect(prompt).toContain("Do not answer with refusal text");
    expect(prompt).toContain("do not replace it with a clothed or softer substitute");
    expect(prompt).toContain("Otherwise invoke exactly one selected Loki skill tool");
  });

  test("agent prompt tells reference image skills to use describe_loki_image", () => {
    const request: AgentRunRequest = {
      prompt: "make a new image from this reference",
      agentId: "base-agent",
      model: "GPT-5.4 mini (openai-codex)",
      skills: ["comfy-image-generate"],
      selectedCards: ["card_1"],
      context: {
        localMediaReferences: [
          {
            kind: "image",
            artifactUrl: "/api/artifacts/imports/reference.png",
            path: "/home/victor/dev/loki-creator/.loki/imports/reference.png",
            source: "selected-card-media-asset",
            cardId: "card_1",
          },
        ],
      },
    };

    const prompt = buildAgentPrompt(
      request,
      [makeSkill({ id: "comfy-image-generate", name: "comfy-image-generate" })],
      "pi-tools",
    );

    expect(prompt).toContain("Image description fallback");
    expect(prompt).toContain("call describe_loki_image");
  });

  test("describe_loki_image exposure and selection use local image references", () => {
    const request: AgentRunRequest = {
      prompt: "describe selected",
      agentId: "base-agent",
      model: "GPT-5.4 mini (openai-codex)",
      skills: ["comfy-image-generate"],
      selectedCards: ["card_1", "card_2"],
      context: {
        localMediaReferences: [
          {
            kind: "image",
            artifactUrl: "/api/artifacts/imports/first.png",
            path: "/home/victor/dev/loki-creator/.loki/imports/first.png",
            source: "selected-card-media-asset",
            cardId: "card_1",
          },
          {
            kind: "image",
            artifactUrl: "/api/artifacts/imports/second.png",
            path: "/home/victor/dev/loki-creator/.loki/imports/second.png",
            source: "selected-card-media-asset",
            cardId: "card_2",
          },
        ],
      },
    };

    expect(shouldExposeDescribeLokiImageTool(request)).toBe(true);
    expect(selectDescribeImageReference(request, {})?.artifactUrl).toBe("/api/artifacts/imports/first.png");
    expect(selectDescribeImageReference(request, { cardId: "card_2" })?.artifactUrl).toBe("/api/artifacts/imports/second.png");
    expect(selectDescribeImageReference(request, { artifactUrl: "/api/artifacts/imports/second.png" })?.cardId).toBe("card_2");
    expect(shouldExposeDescribeLokiImageTool({ ...request, context: { localMediaReferences: [] } })).toBe(false);
  });

  test("reference placeholder guard rejects ungrounded r2i prompts", () => {
    const request: AgentRunRequest = {
      prompt: "make a new image from this reference",
      agentId: "base-agent",
      model: "GPT-5.4 mini (openai-codex)",
      skills: ["comfy-image-generate"],
      selectedCards: ["card_1"],
      context: {
        localMediaReferences: [
          {
            kind: "image",
            artifactUrl: "/api/artifacts/imports/reference.png",
            path: "/home/victor/dev/loki-creator/.loki/imports/reference.png",
            source: "selected-card-media-asset",
            cardId: "card_1",
          },
        ],
      },
    };

    const errors = validateReferencePromptPlaceholders(
      request,
      makeSkill({ id: "comfy-image-generate", name: "comfy-image-generate" }),
      {
        prompt: "Create a new image based on the selected image.",
        paramsJson: JSON.stringify({ mode: "r2i" }),
      },
    );

    expect(errors.join(" ")).toContain("Call describe_loki_image");
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

  test("Video Director prompt includes workflow, manual engine, memory, and prompt-only guard", () => {
    const request: AgentRunRequest = {
      prompt: "plan a 20 second short",
      agentId: "video-director",
      model: "GPT-5.4 mini (openai-codex)",
      skills: ["Auto"],
      selectedCards: [],
      projectId: "project-test",
      workflowId: "short-film",
      videoEngine: "prompt-only",
      phaseOverride: "plan",
      context: {
        projectId: "project-test",
        workflowId: "short-film",
        videoEngine: "prompt-only",
        phaseOverride: "plan",
      },
    };

    const prompt = buildAgentPrompt(request, [
      makeSkill({ id: "video-director-os", name: "video-director-os" }),
      makeSkill({ id: "openrouter-seedance-video", name: "openrouter-seedance-video" }),
      makeSkill({ id: "comfy-videoedit", name: "comfy-videoedit" }),
    ], "pi-tools");

    expect(prompt).toContain("Video Director operating system");
    expect(prompt).toContain("Current workflow: short-film");
    expect(prompt).toContain("Current video engine override: prompt-only");
    expect(prompt).toContain("Prompt only mode: ACTIVE");
    expect(prompt).toContain("Do not invoke image, video, audio, ffmpeg, Seedance, Grok, Comfy, or HyperFrames skills");
    expect(prompt).toContain("Seedance via OpenRouter means use openrouter-seedance-video");
    expect(prompt).toContain('paramsJson.editMode="bernini"');
    expect(prompt).toContain('paramsJson.modelProfile="wan22-bernini"');
    expect(prompt).toContain("Resolve conversational references from project memory");
    expect(prompt).toContain("If the user says \"opcion 6\"");
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

  test("Video Director persists memory before returning needs_input", async () => {
    const source = await readFile(new URL("./agentRunner.ts", import.meta.url), "utf8");

    expect(source).toContain("const memoryResponseText = [");
    expect(source).toContain("updateVideoDirectorMemory(runtimeRequest, memoryResponseText, runState)");
    expect(source).toContain("projectId.startsWith(\"video_director_session_\")");
    expect(source).toContain("packageVideoDirectorPromptOnlyCard(runtimeRequest, responseText, runState)");
    expect(source).toContain("videoDirectorPromptOnly: true");
  });
});
