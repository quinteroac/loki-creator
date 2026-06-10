import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent, FormEvent, KeyboardEvent } from "react";
import { agentRunEventsUrl, createAgentRun, listAgentModels, stopAgentRun } from "./api/agentRuns";
import { importArtifact } from "./api/artifacts";
import { generateCodexImage } from "./api/codexImage";
import { generateComfy } from "./api/comfyGeneration";
import { generateGeminiImage } from "./api/geminiImage";
import { generateGrokImage, generateGrokVideo } from "./api/grokImagine";
import { generateSeedanceVideo } from "./api/seedanceVideo";
import { listSkillRuns, waitForSkillRun } from "./api/skillRuns";
import { listSkills } from "./api/skills";
import { AgentComposer } from "./components/AgentComposer";
import { AgentResponsePanel } from "./components/AgentResponsePanel";
import { CanvasStage } from "./components/CanvasStage";
import { ProjectManager } from "./components/ProjectManager";
import { Topbar } from "./components/Topbar";
import { initialCanvasNodes, initialCardDocuments } from "./data/workspace";
import { useDismissablePopover } from "./hooks/useDismissablePopover";
import { useProjects } from "./hooks/useProjects";
import {
  assignUniqueDisplayTitles,
  createBboxCardDocument,
  createCardDocumentForEditedArtifact,
  createCardDocumentForImportedArtifact,
  createCanvasNodeForDocument,
  createNoteCardDocument,
  createSelectedCardSnapshots,
  getCardDisplayTitle,
  getCardHeight,
  getFileDimensions,
  normalizeCardDocument,
  updateNoteCardDocumentText,
  updateBboxCardDocument,
  renameCardDocument,
  type CardPreviewCapture,
} from "./lib/cardDocuments";
import {
  filterBySearch,
  getFirstSelectedCardLabel,
  toggleExclusiveAutoSelection,
  toggleMultiSelection,
} from "./lib/selection";
import { mergeSelectedCardIds, resolveMentionedCardIds } from "./lib/cardMentions";
import { dedupeCanvasNodesByDocumentId } from "./lib/projects";
import type { BboxCardData } from "./lib/bboxCards";
import type {
  AgentAttachment,
  AgentChatMessage,
  AgentModel,
  AgentQuestion,
  AgentRunRequest,
  AgentRunResponse,
  AgentRunStreamEvent,
  CanvasNode,
  CanvasNodeFrame,
  CardDocument,
  CodexImageResolution,
  ComfyAspectRatio,
  ComfyDuration,
  ComfyImageMode,
  ComfyImageProfile,
  ComfyResolution,
  ComfyTool,
  ComfyVideoMode,
  ComfyVideoProfile,
  ComposerMode,
  EditedMediaArtifact,
  GeminiImageModel,
  GeminiImageResolution,
  GeneratedCard,
  GrokImageAspectRatio,
  GrokImageResolution,
  GrokTool,
  GrokVideoAspectRatio,
  GrokVideoDuration,
  GrokVideoResolution,
  SeedanceAspectRatio,
  SeedanceDuration,
  SelectedCardPreview,
  SkillRun,
} from "./types";

const fallbackModels: AgentModel[] = [
  {
    id: "loki-default",
    provider: "loki",
    name: "Loki Default",
    label: "Loki Default",
  },
];
const preferredAgentModelId = "gpt-5.4-mini";

function createClientId(prefix: string) {
  const randomId = globalThis.crypto?.randomUUID?.().replaceAll("-", "")
    ?? `${Date.now().toString(36)}${Math.random().toString(16).slice(2)}`;
  return `${prefix}_${randomId}`;
}

export function App() {
  const [instruction, setInstruction] = useState("");
  const [cardDocuments, setCardDocuments] = useState(initialCardDocuments);
  const [canvasNodes, setCanvasNodes] = useState(initialCanvasNodes);
  const [availableSkills, setAvailableSkills] = useState<string[]>([]);
  const [visibleSkillIds, setVisibleSkillIds] = useState<Set<string>>(new Set());
  const [selectedSkills, setSelectedSkills] = useState(["Auto"]);
  const [availableModels, setAvailableModels] = useState<AgentModel[]>(fallbackModels);
  const [selectedModel, setSelectedModel] = useState(fallbackModels[0].label);
  const [composerMode, setComposerMode] = useState<ComposerMode>("agent");
  const [seedanceAspectRatio, setSeedanceAspectRatio] = useState<SeedanceAspectRatio>("16:9");
  const [seedanceDuration, setSeedanceDuration] = useState<SeedanceDuration>(5);
  const [grokTool, setGrokTool] = useState<GrokTool>("image");
  const [grokImageAspectRatio, setGrokImageAspectRatio] = useState<GrokImageAspectRatio>("1:1");
  const [grokImageResolution, setGrokImageResolution] = useState<GrokImageResolution>("1k");
  const [grokVideoAspectRatio, setGrokVideoAspectRatio] = useState<GrokVideoAspectRatio>("16:9");
  const [grokVideoResolution, setGrokVideoResolution] = useState<GrokVideoResolution>("720p");
  const [grokVideoDuration, setGrokVideoDuration] = useState<GrokVideoDuration>(5);
  const [codexImageResolution, setCodexImageResolution] = useState<CodexImageResolution>("1024x1024");
  const [comfyTool, setComfyTool] = useState<ComfyTool>("image");
  const [comfyImageMode, setComfyImageMode] = useState<ComfyImageMode>("generate");
  const [comfyImageProfile, setComfyImageProfile] = useState<ComfyImageProfile>("anima-base");
  const [comfyVideoMode, setComfyVideoMode] = useState<ComfyVideoMode>("i2v");
  const [comfyVideoProfile, setComfyVideoProfile] = useState<ComfyVideoProfile>("ltx23-10eros");
  const [comfyAspectRatio, setComfyAspectRatio] = useState<ComfyAspectRatio>("16:9");
  const [comfyResolution, setComfyResolution] = useState<ComfyResolution>("480p");
  const [comfyDuration, setComfyDuration] = useState<ComfyDuration>(5);
  const [geminiImageResolution, setGeminiImageResolution] = useState<GeminiImageResolution>("1024x1024");
  const [geminiImageModel, setGeminiImageModel] = useState<GeminiImageModel>("Gemini 3.5 Flash (Medium)");
  const [selectedCards, setSelectedCards] = useState<string[]>([]);
  const [mentionedCardIds, setMentionedCardIds] = useState<string[]>([]);
  const [attachments, setAttachments] = useState<AgentAttachment[]>([]);
  const [latestAgentResponse, setLatestAgentResponse] = useState<AgentRunResponse | null>(null);
  const [agentChatMessages, setAgentChatMessages] = useState<AgentChatMessage[]>([]);
  const [agentActivityTitle, setAgentActivityTitle] = useState("Base Agent");
  const [agentRunStatus, setAgentRunStatus] = useState<AgentRunStreamEvent["status"] | null>(null);
  const [isDirectGenerating, setIsDirectGenerating] = useState(false);
  const [agentRunStartedAt, setAgentRunStartedAt] = useState<number | null>(null);
  const [agentLastActivityAt, setAgentLastActivityAt] = useState<number | null>(null);
  const [agentClockTick, setAgentClockTick] = useState(0);
  const [pendingQuestion, setPendingQuestion] = useState<AgentQuestion | null>(null);
  const [pendingConversationId, setPendingConversationId] = useState<string | null>(null);
  const [pendingCollectedArgs, setPendingCollectedArgs] = useState<Record<string, string>>({});
  const [pendingAgentRequest, setPendingAgentRequest] = useState<AgentRunRequest | null>(null);
  const [isAgentResponseOpen, setIsAgentResponseOpen] = useState(false);
  const [skillSearch, setSkillSearch] = useState("");
  const [openMenu, setOpenMenu] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const agentEventSourceRef = useRef<EventSource | null>(null);
  const activeAgentRunIdRef = useRef<string | null>(null);
  const agentRunStatusRef = useRef<AgentRunStreamEvent["status"] | null>(null);
  const stoppedAgentRunIdsRef = useRef<Set<string>>(new Set());
  const ignoredSkillRunIdsRef = useRef<Set<string>>(new Set());
  const hasSeededIgnoredSkillRunsRef = useRef(false);
  const processedCardIdsRef = useRef<Set<string>>(new Set());
  const previewCapturesRef = useRef<Map<string, CardPreviewCapture>>(new Map());

  const closePopover = useCallback(() => setOpenMenu(null), []);
  useDismissablePopover(openMenu, closePopover);
  const closeAgentResponse = useCallback(() => setIsAgentResponseOpen(false), []);
  useDismissablePopover(isAgentResponseOpen ? "agent-response" : null, closeAgentResponse);

  const projectsController = useProjects({
    cardDocuments,
    canvasNodes,
    onBeforeWorkspaceReplace: async () => {
      const [runningRuns, completedRuns] = await Promise.all([
        listSkillRuns({ status: "running" }),
        listSkillRuns({ status: "succeeded" }),
      ]);
      ignoreSkillRuns([...runningRuns, ...completedRuns]);
      hasSeededIgnoredSkillRunsRef.current = true;
    },
    onCanvasNodesNormalized: setCanvasNodes,
    onReplaceWorkspace: (projectDocuments, projectCanvasNodes) => {
      processedCardIdsRef.current = new Set(projectDocuments.map((document) => document.id));
      previewCapturesRef.current.clear();
      setCardDocuments(projectDocuments);
      setCanvasNodes(projectCanvasNodes);
      setSelectedCards([]);
      setOpenMenu(null);
    },
    onStatus: setStatus,
  });

  useEffect(() => () => agentEventSourceRef.current?.close(), []);

  useEffect(() => {
    setCanvasNodes((currentNodes) => dedupeCanvasNodesByDocumentId(currentNodes));
  }, [canvasNodes]);

  function ignoreSkillRuns(runs: SkillRun[]) {
    runs.forEach((run) => ignoredSkillRunIdsRef.current.add(run.id));
  }

  useEffect(() => {
    if (agentRunStatus !== "running") return;
    const intervalId = window.setInterval(() => setAgentClockTick((tick) => tick + 1), 1000);
    return () => window.clearInterval(intervalId);
  }, [agentRunStatus]);

  useEffect(() => {
    let isMounted = true;

    async function loadSkills() {
      try {
        const skills = await listSkills();
        if (isMounted) {
          const userSkills = skills.filter((skill) =>
            skill.visibility === "user" && !["grok-imagine-image", "grok-imagine-video"].includes(skill.id)
          );
          setAvailableSkills(userSkills.map((skill) => skill.name));
          setVisibleSkillIds(new Set(userSkills.map((skill) => skill.id)));
        }
      } catch {
        if (isMounted) {
          setAvailableSkills([]);
          setVisibleSkillIds(new Set());
        }
      }
    }

    loadSkills();

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    let isMounted = true;

    async function loadModels() {
      try {
        const models = await listAgentModels();
        if (!isMounted || models.length === 0) return;

        setAvailableModels(models);
        setSelectedModel((currentModel) => {
          const preferredModel = models.find((model) => model.id === preferredAgentModelId);
          const currentModelEntry = models.find((model) => model.label === currentModel);
          if (!currentModelEntry || currentModelEntry.id === "gpt-5.2" || currentModel === fallbackModels[0].label) {
            return preferredModel?.label ?? models[0].label;
          }
          return currentModel;
        });
      } catch {
        if (isMounted) {
          setAvailableModels(fallbackModels);
          setSelectedModel((currentModel) => currentModel || fallbackModels[0].label);
        }
      }
    }

    loadModels();

    return () => {
      isMounted = false;
    };
  }, []);

  const addGeneratedCards = useCallback((cards: GeneratedCard[]) => {
    const generatedCards = cards
      .filter((card) => !processedCardIdsRef.current.has(card.id))
      .map(normalizeCardDocument);
    if (generatedCards.length === 0) return;

    const canvasWidth = window.innerWidth;

    setCardDocuments((currentDocuments: CardDocument[]) => {
      const currentDocumentIds = new Set(currentDocuments.map((document) => document.id));
      const newDocuments = generatedCards.filter((document, index, documents) => {
        const isFirstOccurrence = documents.findIndex((candidate) => candidate.id === document.id) === index;
        return isFirstOccurrence && !currentDocumentIds.has(document.id);
      });
      if (newDocuments.length === 0) return currentDocuments;
      newDocuments.forEach((document) => processedCardIdsRef.current.add(document.id));

      return [...currentDocuments, ...assignUniqueDisplayTitles(newDocuments, currentDocuments)];
    });

    const newDocumentsForNodes = generatedCards.filter((document, index, documents) => {
      const isFirstOccurrence = documents.findIndex((candidate) => candidate.id === document.id) === index;
      return isFirstOccurrence;
    });

    setCanvasNodes((currentNodes) => {
      const currentDocumentIds = new Set(currentNodes.map((node) => node.cardDocumentId));
      const newNodes = newDocumentsForNodes
        .filter((document) => !currentDocumentIds.has(document.id))
        .map((document, index) => createCanvasNodeForDocument(document, currentNodes.length + index, canvasWidth));

      return newNodes.length > 0 ? [...currentNodes, ...newNodes] : currentNodes;
    });

  }, []);

  const addCardsFromRun = useCallback((run: SkillRun) => {
    if (!visibleSkillIds.has(run.skillId)) return;

    const generatedCards = (run.result?.cards ?? []).filter((card) => {
      if (!card.sourceSkillId) return true;
      return visibleSkillIds.has(card.sourceSkillId);
    });

    addGeneratedCards(generatedCards);
  }, [addGeneratedCards, visibleSkillIds]);

  useEffect(() => {
    let isMounted = true;

    async function syncCompletedSkillRuns() {
      try {
        const [runningRuns, completedRuns] = await Promise.all([
          listSkillRuns({ status: "running" }),
          listSkillRuns({ status: "succeeded" }),
        ]);
        if (!isMounted) return;

        const runs = [...runningRuns, ...completedRuns];
        if (!hasSeededIgnoredSkillRunsRef.current) {
          ignoreSkillRuns(runs);
          hasSeededIgnoredSkillRunsRef.current = true;
          return;
        }

        runs
          .filter((run) => !ignoredSkillRunIdsRef.current.has(run.id))
          .forEach(addCardsFromRun);
      } catch {
        // Run sync is best-effort; the next interval will reconcile completed runs.
      }
    }

    syncCompletedSkillRuns();
    const intervalId = window.setInterval(syncCompletedSkillRuns, 1200);

    return () => {
      isMounted = false;
      window.clearInterval(intervalId);
    };
  }, [addCardsFromRun]);

  const documentsById = useMemo(
    () => Object.fromEntries(cardDocuments.map((document) => [document.id, document])),
    [cardDocuments],
  );
  const filteredSkills = filterBySearch(availableSkills, skillSearch);
  const skillButtonLabel = selectedSkills[0] ?? "Auto";
  const selectedCardLabel = getFirstSelectedCardLabel(cardDocuments, selectedCards, "Selected cards");

  const syncReferencedCards = useCallback((cardIds: string[]) => {
    const nextMentionedCardIds = cardIds.filter((cardId, index) => cardIds.indexOf(cardId) === index);

    setMentionedCardIds((currentMentionedCardIds) => {
      setSelectedCards((currentSelectedCards) =>
        mergeSelectedCardIds(
          currentSelectedCards.filter((cardId) => !currentMentionedCardIds.includes(cardId)),
          nextMentionedCardIds,
        ),
      );

      return nextMentionedCardIds;
    });
  }, []);

  useEffect(() => {
    syncReferencedCards(resolveMentionedCardIds(cardDocuments, instruction));
  }, [cardDocuments, syncReferencedCards]);

  function setComposerInstruction(nextInstruction: string) {
    setInstruction(nextInstruction);
    syncReferencedCards(resolveMentionedCardIds(cardDocuments, nextInstruction));
  }

  function getEffectiveSelectedCardIds(prompt: string) {
    return mergeSelectedCardIds(selectedCards, resolveMentionedCardIds(cardDocuments, prompt));
  }

  function appendAgentStreamEvent(event: AgentRunStreamEvent) {
    setAgentLastActivityAt(Date.now());
    if (event.status) {
      agentRunStatusRef.current = event.status;
      setAgentRunStatus(event.status);
    }
    if (event.type === "done") {
      activeAgentRunIdRef.current = null;
    }

    const text = event.message?.trim();
    if (!text && event.type !== "assistant_delta") return;

    if (event.type === "assistant_delta") {
      setAgentChatMessages((currentMessages) => {
        const lastMessage = currentMessages[currentMessages.length - 1];
        if (lastMessage?.role === "assistant" && lastMessage.status === "running") {
          return [
            ...currentMessages.slice(0, -1),
            { ...lastMessage, text: `${lastMessage.text}${event.message ?? ""}` },
          ];
        }

        return [
          ...currentMessages,
          {
            id: createClientId("agent_message"),
            role: "assistant",
            text: event.message ?? "",
            status: "running",
            createdAt: Date.now(),
          },
        ];
      });
      return;
    }

    if (event.type === "thinking_delta") {
      setAgentChatMessages((currentMessages) => {
        const lastMessage = currentMessages[currentMessages.length - 1];
        if (lastMessage?.role === "thinking" && lastMessage.status === "running") {
          return [
            ...currentMessages.slice(0, -1),
            { ...lastMessage, text: `${lastMessage.text}${event.message ?? ""}` },
          ];
        }

        return [
          ...currentMessages,
          {
            id: createClientId("agent_message"),
            role: "thinking",
            text: event.message ?? "",
            status: "running",
            createdAt: Date.now(),
          },
        ];
      });
      return;
    }

    if (event.type === "tool_start" || event.type === "tool_update" || event.type === "tool_end") {
      setAgentChatMessages((currentMessages) => {
        const existingIndex = event.toolCallId
          ? currentMessages.findIndex((message) => message.toolCallId === event.toolCallId)
          : -1;
        const nextMessage: AgentChatMessage = {
          id: existingIndex >= 0 ? currentMessages[existingIndex].id : createClientId("agent_message"),
          role: "tool",
          text: text ?? "",
          status: event.status,
          toolName: event.toolName,
          toolCallId: event.toolCallId,
          createdAt: existingIndex >= 0 ? currentMessages[existingIndex].createdAt : Date.now(),
        };

        if (existingIndex >= 0) {
          return currentMessages.map((message, index) => (index === existingIndex ? nextMessage : message));
        }

        return [...currentMessages, nextMessage];
      });
      return;
    }

    const role: AgentChatMessage["role"] =
      event.type === "user"
        ? "user"
        : event.type === "skill"
          ? "skill"
          : event.type === "assistant_message"
            ? "assistant"
            : "system";

    setAgentChatMessages((currentMessages) => {
      if (event.type === "assistant_message") {
        const lastMessage = currentMessages[currentMessages.length - 1];
        if (lastMessage?.role === "assistant" && lastMessage.text.trim() === text) {
          return [...currentMessages.slice(0, -1), { ...lastMessage, status: event.status }];
        }
      }

      return [
        ...currentMessages,
        {
          id: createClientId("agent_message"),
          role,
          text: text ?? "",
          status: event.status,
          skillName: event.skillName,
          createdAt: Date.now(),
        },
      ];
    });
  }

  function startAgentRunStream(streamId: string) {
    agentEventSourceRef.current?.close();
    activeAgentRunIdRef.current = streamId;
    stoppedAgentRunIdsRef.current.delete(streamId);
    const now = Date.now();
    setAgentRunStartedAt(now);
    setAgentLastActivityAt(now);
    setAgentActivityTitle("Base Agent");
    agentRunStatusRef.current = "running";
    setAgentRunStatus("running");
    setAgentChatMessages([]);
    setIsAgentResponseOpen(true);

    const source = new EventSource(agentRunEventsUrl(streamId));
    agentEventSourceRef.current = source;
    source.onmessage = (message) => {
      try {
        const event = JSON.parse(message.data) as AgentRunStreamEvent;
        appendAgentStreamEvent(event);
        if (event.type === "done") {
          source.close();
          if (agentEventSourceRef.current === source) {
            agentEventSourceRef.current = null;
          }
        }
      } catch {
        appendAgentStreamEvent({ type: "error", status: "failed", message: "Could not read agent stream event." });
      }
    };
    source.onerror = () => {
      source.close();
      if (agentEventSourceRef.current === source) {
        agentEventSourceRef.current = null;
      }
      if (agentRunStatusRef.current === "running") {
        appendAgentStreamEvent({
          type: "status",
          status: "running",
          message: "Agent stream paused. Waiting for the final run response.",
        });
      }
    };
  }

  function getDirectGenerationActivity() {
    if (composerMode === "seedance") {
      return {
        title: "Seedance Video",
        runningStatus: "Generating Seedance video...",
        successStatus: "Seedance video generated.",
      };
    }
    if (composerMode === "codex") {
      return {
        title: "Codex Image",
        runningStatus: "Generating Codex image...",
        successStatus: "Codex image generated.",
      };
    }
    if (composerMode === "gemini") {
      return {
        title: "Gemini Image",
        runningStatus: "Generating Gemini image...",
        successStatus: "Gemini image generated.",
      };
    }
    if (composerMode === "comfy") {
      return {
        title: comfyTool === "image" ? "Comfy Image" : "Comfy Video",
        runningStatus: `Generating Comfy ${comfyTool}...`,
        successStatus: `Comfy ${comfyTool} generated.`,
      };
    }
    return {
      title: grokTool === "image" ? "Grok Image" : "Grok Video",
      runningStatus: `Generating Grok ${grokTool}...`,
      successStatus: `Grok ${grokTool} generated.`,
    };
  }

  function startDirectGenerationActivity(prompt: string, title: string) {
    agentEventSourceRef.current?.close();
    agentEventSourceRef.current = null;
    activeAgentRunIdRef.current = null;
    const now = Date.now();
    const toolCallId = createClientId("direct_tool");
    setLatestAgentResponse(null);
    setAgentRunStartedAt(now);
    setAgentLastActivityAt(now);
    setAgentActivityTitle(title);
    agentRunStatusRef.current = "running";
    setAgentRunStatus("running");
    setAgentChatMessages([]);
    setIsAgentResponseOpen(true);
    appendAgentStreamEvent({
      type: "user",
      status: "running",
      message: prompt,
    });
    appendAgentStreamEvent({
      type: "tool_start",
      status: "running",
      toolCallId,
      toolName: title,
      message: `${title} started.`,
    });
    return toolCallId;
  }

  async function handleAgentRunResponse(agentRun: AgentRunResponse, baseRequest: AgentRunRequest) {
    if (stoppedAgentRunIdsRef.current.has(agentRun.id) && agentRun.status !== "cancelled") {
      return;
    }

    setLatestAgentResponse(agentRun);
    agentRunStatusRef.current = agentRun.status;
    setAgentRunStatus(agentRun.status);
    setAgentLastActivityAt(Date.now());
    activeAgentRunIdRef.current = null;

    if (agentRun.status === "cancelled") {
      appendAgentStreamEvent({
        type: "done",
        status: "cancelled",
        message: "Agent run stopped.",
      });
      setStatus("Agent stopped.");
      return;
    }

    if (agentRun.status === "needs_input" && agentRun.question && agentRun.conversationId) {
      appendAgentStreamEvent({
        type: "question",
        status: "needs_input",
        message: agentRun.question.text,
      });
      for (const runId of agentRun.skillRunIds) {
        const completedRun = await waitForSkillRun(runId);
        addCardsFromRun(completedRun);
      }

      setPendingQuestion(agentRun.question);
      setPendingConversationId(agentRun.conversationId);
      setPendingCollectedArgs(agentRun.collectedArgs ?? {});
      setPendingAgentRequest(baseRequest);
      setComposerInstruction("");
      setStatus("Answer the agent question to continue.");
      return;
    }

    setPendingQuestion(null);
    setPendingConversationId(null);
    setPendingCollectedArgs({});
    setPendingAgentRequest(null);

    if (agentRun.status === "failed") {
      appendAgentStreamEvent({
        type: "error",
        status: "failed",
        message: agentRun.error || "Agent run failed.",
      });
      setStatus(agentRun.error || "Agent run failed.");
      return;
    }

    for (const runId of agentRun.skillRunIds) {
      const completedRun = await waitForSkillRun(runId);
      if (completedRun.status === "cancelled") {
        setStatus("Skill run stopped.");
        return;
      }
      if (completedRun.status === "failed") {
        setStatus(completedRun.error || "Skill run failed.");
        return;
      }
      addCardsFromRun(completedRun);
    }

    setComposerInstruction("");
    setAttachments([]);
    appendAgentStreamEvent({
      type: "done",
      status: "succeeded",
      message: "Agent completed.",
    });
    setStatus("Agent completed.");
  }

  async function buildAgentRequest(prompt: string): Promise<AgentRunRequest> {
    const effectiveSelectedCards = getEffectiveSelectedCardIds(prompt);
    const selectedCardSnapshots = await createSelectedCardSnapshots(
      cardDocuments,
      effectiveSelectedCards,
      previewCapturesRef.current,
    );
    const effectiveSelectedDocument = cardDocuments.find((document) => document.id === effectiveSelectedCards[0]);

    return {
      agentId: "base-agent",
      prompt,
      model: selectedModel,
      skills: selectedSkills,
      selectedCards: effectiveSelectedCards,
      selectedCardSnapshots,
      attachments,
      context: {
        skills: selectedSkills,
        model: selectedModel,
        agentId: "base-agent",
        selectedElement: effectiveSelectedDocument ? getCardDisplayTitle(effectiveSelectedDocument) : null,
        attachments,
      },
    };
  }

  async function answerPendingQuestion(answer: string) {
    const text = answer.trim();
    if (!pendingQuestion || !pendingConversationId || !pendingAgentRequest) return;
    if (!text) {
      setStatus("Answer the agent question before continuing.");
      return;
    }

    const answeredQuestion = pendingQuestion;
    const answerKey = pendingQuestion.argumentId ?? pendingQuestion.id;
    const streamId = createClientId("agent_run");
    const request: AgentRunRequest = {
      ...pendingAgentRequest,
      streamId,
      conversationId: pendingConversationId,
      answers: {
        [answerKey]: text,
        answer: text,
      },
      collectedArgs: pendingCollectedArgs,
    };

    try {
      setPendingQuestion(null);
      setComposerInstruction("");
      setStatus("Continuing agent...");
      startAgentRunStream(streamId);
      const agentRun = await createAgentRun(request);
      await handleAgentRunResponse(agentRun, request);
    } catch (error) {
      if (stoppedAgentRunIdsRef.current.has(streamId)) return;
      setPendingQuestion(answeredQuestion);
      setStatus(error instanceof Error ? error.message : "Could not connect to the agent bridge.");
    }
  }

  async function stopActiveAgentRun() {
    const streamId = activeAgentRunIdRef.current;
    if (!streamId || agentRunStatusRef.current !== "running") return;

    stoppedAgentRunIdsRef.current.add(streamId);
    setStatus("Stopping agent...");

    try {
      await stopAgentRun(streamId);
      agentEventSourceRef.current?.close();
      agentEventSourceRef.current = null;
      activeAgentRunIdRef.current = null;
      appendAgentStreamEvent({
        type: "done",
        status: "cancelled",
        message: "Agent run stopped.",
      });
      setStatus("Agent stopped.");
    } catch (error) {
      stoppedAgentRunIdsRef.current.delete(streamId);
      setStatus(error instanceof Error ? error.message : "Could not stop the agent run.");
    }
  }

  async function submitInstruction(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (isDirectGenerating) {
      setStatus("Direct generation is already running.");
      return;
    }

    if (agentRunStatusRef.current === "running") {
      await stopActiveAgentRun();
      return;
    }

    const text = instruction.trim();

    if (pendingQuestion) {
      await answerPendingQuestion(text);
      return;
    }

    if (!text) {
      setStatus(composerMode === "agent" ? "Write an instruction before sending it to the agent." : "Write a prompt before generating.");
      return;
    }

    if (composerMode === "seedance" || composerMode === "grok" || composerMode === "codex" || composerMode === "gemini" || composerMode === "comfy") {
      const activity = getDirectGenerationActivity();
      let toolCallId: string | null = null;
      try {
        setIsDirectGenerating(true);
        setStatus(activity.runningStatus);
        toolCallId = startDirectGenerationActivity(text, activity.title);
        appendAgentStreamEvent({
          type: "tool_update",
          status: "running",
          toolCallId,
          toolName: activity.title,
          message: "Resolving selected card artifacts.",
        });
        const effectiveSelectedCards = getEffectiveSelectedCardIds(text);
        const selectedCardSnapshots = await createSelectedCardSnapshots(
          cardDocuments,
          effectiveSelectedCards,
          previewCapturesRef.current,
        );
        appendAgentStreamEvent({
          type: "tool_update",
          status: "running",
          toolCallId,
          toolName: activity.title,
          message: "Calling direct generation endpoint.",
        });
        const result = composerMode === "seedance"
          ? await generateSeedanceVideo({
            prompt: text,
            aspectRatio: seedanceAspectRatio,
            duration: seedanceDuration,
            selectedCardSnapshots,
            attachments,
          })
          : composerMode === "codex"
            ? await generateCodexImage({
              prompt: text,
              resolution: codexImageResolution,
              selectedCardSnapshots,
              attachments,
            })
            : composerMode === "gemini"
              ? await generateGeminiImage({
                prompt: text,
                resolution: geminiImageResolution,
                model: geminiImageModel,
                selectedCardSnapshots,
                attachments,
              })
              : composerMode === "comfy"
                ? await generateComfy({
                  prompt: text,
                  tool: comfyTool,
                  imageMode: comfyImageMode,
                  videoMode: comfyVideoMode,
                  modelProfile: comfyTool === "image"
                    ? comfyImageMode === "upscale" ? "" : comfyImageProfile
                    : comfyVideoProfile,
                  aspectRatio: comfyAspectRatio,
                  resolution: comfyResolution,
                  duration: comfyDuration,
                  selectedCardSnapshots,
                  attachments,
                })
                : grokTool === "image"
                  ? await generateGrokImage({
                    prompt: text,
                    aspectRatio: grokImageAspectRatio,
                    resolution: grokImageResolution,
                    selectedCardSnapshots,
                    attachments,
                  })
                  : await generateGrokVideo({
                    prompt: text,
                    aspectRatio: grokVideoAspectRatio,
                    resolution: grokVideoResolution,
                    duration: grokVideoDuration,
                    selectedCardSnapshots,
                    attachments,
                  });
        addGeneratedCards(result.cards);
        setComposerInstruction("");
        setAttachments([]);
        appendAgentStreamEvent({
          type: "tool_end",
          status: "succeeded",
          toolCallId,
          toolName: activity.title,
          message: `${activity.title} returned ${result.cards.length} card${result.cards.length === 1 ? "" : "s"}.`,
        });
        appendAgentStreamEvent({
          type: "done",
          status: "succeeded",
          message: `${activity.title} completed.`,
        });
        setStatus(activity.successStatus);
      } catch (error) {
        const message = error instanceof Error ? error.message : "Could not generate.";
        if (toolCallId) {
          appendAgentStreamEvent({
            type: "tool_end",
            status: "failed",
            toolCallId,
            toolName: activity.title,
            message,
          });
        }
        appendAgentStreamEvent({
          type: "error",
          status: "failed",
          message,
        });
        setStatus(message);
      } finally {
        setIsDirectGenerating(false);
      }
      return;
    }

    const streamId = createClientId("agent_run");

    try {
      setStatus("Running agent...");
      const request = await buildAgentRequest(text);
      request.streamId = streamId;
      startAgentRunStream(streamId);
      const agentRun = await createAgentRun(request);
      await handleAgentRunResponse(agentRun, request);
    } catch (error) {
      if (stoppedAgentRunIdsRef.current.has(streamId)) return;
      setStatus(error instanceof Error ? error.message : "Could not connect to the agent bridge.");
    }
  }

  function handleInstructionKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  async function handleFiles(event: ChangeEvent<HTMLInputElement>) {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    try {
      const importedDocuments = await Promise.all(
        Array.from(files).map(async (file) => {
          const [artifact, dimensions] = await Promise.all([
            importArtifact(file),
            getFileDimensions(file),
          ]);

          return createCardDocumentForImportedArtifact(artifact, dimensions);
        }),
      );
      const canvasWidth = window.innerWidth;
      const importedDocumentIds = importedDocuments.map((document) => document.id);

      setCardDocuments((currentDocuments) => {
        const newDocuments = assignUniqueDisplayTitles(importedDocuments, currentDocuments);

        return [...currentDocuments, ...newDocuments];
      });
      setCanvasNodes((currentNodes) => {
        const currentDocumentIds = new Set(currentNodes.map((node) => node.cardDocumentId));
        const newDocuments = importedDocuments.filter((document) => !currentDocumentIds.has(document.id));

        return [
          ...currentNodes,
          ...newDocuments.map((document, index) =>
            createCanvasNodeForDocument(document, currentNodes.length + index, canvasWidth),
          ),
        ];
      });
      setSelectedCards(importedDocumentIds);
      setStatus(importedDocuments.length === 1 ? "1 file added to canvas." : `${importedDocuments.length} files added to canvas.`);
    } catch {
      setStatus("Could not add file to canvas.");
    } finally {
      event.target.value = "";
    }
  }

  function removeAttachment(attachmentId: string) {
    setAttachments((currentAttachments) => {
      const updatedAttachments = currentAttachments.filter((attachment) => attachment.id !== attachmentId);
      setPendingAgentRequest((currentRequest) =>
        currentRequest
          ? {
            ...currentRequest,
            attachments: updatedAttachments,
            context: { ...currentRequest.context, attachments: updatedAttachments },
          }
          : currentRequest,
      );

      return updatedAttachments;
    });
  }

  function handleCreateAgent() {
    setStatus("Agent creation is coming soon.");
    setOpenMenu(null);
  }

  function toggleSkill(skill: string) {
    setSelectedSkills((currentSkills) => toggleExclusiveAutoSelection(currentSkills, skill));
  }

  function toggleCard(cardId: string) {
    setSelectedCards((currentCards) =>
      mentionedCardIds.includes(cardId) && currentCards.includes(cardId)
        ? currentCards
        : toggleMultiSelection(currentCards, cardId),
    );
  }

  function toggleCanvasNode(nodeId: string) {
    const node = canvasNodes.find((candidate) => candidate.id === nodeId);
    if (node) {
      toggleCard(node.cardDocumentId);
    }
  }

  function updateCanvasNodeFrame(nodeId: string, frame: CanvasNodeFrame) {
    setCanvasNodes((currentNodes) =>
      currentNodes.map((node) => (node.id === nodeId ? { ...node, frame } : node)),
    );
  }

  function createCardFromEditedMediaArtifact(
    artifact: EditedMediaArtifact,
    sourceNodeId: string,
    placementOffset = 0,
  ) {
    const editedDocument = createCardDocumentForEditedArtifact(artifact);
    const sourceNode = canvasNodes.find((candidate) => candidate.id === sourceNodeId);
    const sourceDocument = sourceNode ? documentsById[sourceNode.cardDocumentId] : undefined;
    const defaultNode = createCanvasNodeForDocument(editedDocument, canvasNodes.length, window.innerWidth);
    const sourceHeight = sourceNode && sourceDocument
      ? getCardHeight(sourceNode.frame.width, sourceDocument, sourceNode.frame)
      : 0;
    const visibleOffset = Math.max(0, placementOffset) * 28;
    const editedNode: CanvasNode = {
      id: `node_${editedDocument.id}`,
      cardDocumentId: editedDocument.id,
      frame: sourceNode
        ? {
          ...defaultNode.frame,
          width: sourceNode.frame.width,
          x: sourceNode.frame.x + 32 + visibleOffset,
          y: sourceNode.frame.y + sourceHeight + 32 + visibleOffset,
        }
        : defaultNode.frame,
    };

    setCardDocuments((currentDocuments) => {
      const [document] = assignUniqueDisplayTitles([editedDocument], currentDocuments);

      return [...currentDocuments, document];
    });
    setCanvasNodes((currentNodes) => {
      if (currentNodes.some((node) => node.cardDocumentId === editedDocument.id)) return currentNodes;

      return [...currentNodes, editedNode];
    });
    setSelectedCards([editedDocument.id]);
  }

  function createNote(frame: CanvasNodeFrame) {
    const noteDocument = createNoteCardDocument();
    const noteNode = {
      id: `node_${noteDocument.id}`,
      cardDocumentId: noteDocument.id,
      frame,
    };

    setCardDocuments((currentDocuments) => {
      const [document] = assignUniqueDisplayTitles([noteDocument], currentDocuments);

      return [...currentDocuments, document];
    });
    setCanvasNodes((currentNodes) => {
      if (currentNodes.some((node) => node.cardDocumentId === noteDocument.id)) return currentNodes;

      return [...currentNodes, noteNode];
    });
    setSelectedCards([noteDocument.id]);
    setStatus("Note created.");
  }

  function createBbox(frame: CanvasNodeFrame) {
    const sourceDocument = selectedCards
      .map((cardId) => cardDocuments.find((document) => document.id === cardId))
      .find((document): document is CardDocument =>
        document?.metadata?.kind === "image" || document?.metadata?.kind === "video",
      );
    const bboxDocument = createBboxCardDocument({ sourceDocument });
    const documentWidth = bboxDocument.metadata?.width ?? 1024;
    const documentHeight = bboxDocument.metadata?.height ?? 1024;
    const bboxNode = {
      id: `node_${bboxDocument.id}`,
      cardDocumentId: bboxDocument.id,
      frame: {
        ...frame,
        height: frame.width * (documentHeight / documentWidth),
      },
    };

    setCardDocuments((currentDocuments) => {
      const [document] = assignUniqueDisplayTitles([bboxDocument], currentDocuments);

      return [...currentDocuments, document];
    });
    setCanvasNodes((currentNodes) => {
      if (currentNodes.some((node) => node.cardDocumentId === bboxDocument.id)) return currentNodes;

      return [...currentNodes, bboxNode];
    });
    setSelectedCards([bboxDocument.id]);
    setStatus(sourceDocument ? "BBox card created from selected media." : "BBox card created.");
  }

  function renameDocument(cardDocumentId: string, title: string) {
    setCardDocuments((currentDocuments) =>
      currentDocuments.map((document) =>
        document.id === cardDocumentId ? renameCardDocument(document, title) : document,
      ),
    );
  }

  function updateDocumentPrompt(cardDocumentId: string, prompt: string) {
    setCardDocuments((currentDocuments) =>
      currentDocuments.map((document) =>
        document.id === cardDocumentId
          ? document.metadata?.kind === "note"
            ? updateNoteCardDocumentText(document, prompt)
            : {
              ...document,
              prompt,
              metadata: {
                ...document.metadata,
                description: prompt,
              },
            }
          : document,
      ),
    );
  }

  function updateBboxData(cardDocumentId: string, data: BboxCardData) {
    setCardDocuments((currentDocuments) =>
      currentDocuments.map((document) =>
        document.id === cardDocumentId ? updateBboxCardDocument(document, data) : document,
      ),
    );
  }

  function redoDocument(cardDocumentId: string) {
    const document = cardDocuments.find((candidate) => candidate.id === cardDocumentId);
    const prompt = document?.prompt.trim();

    if (!prompt) {
      setStatus("This card does not have a prompt to reuse.");
      return;
    }

    setComposerInstruction(prompt);
    setPendingQuestion(null);
    setPendingConversationId(null);
    setPendingCollectedArgs({});
    setPendingAgentRequest(null);
    setStatus("Prompt loaded from card.");
  }

  function deleteDocument(cardDocumentId: string) {
    setCardDocuments((currentDocuments) => currentDocuments.filter((candidate) => candidate.id !== cardDocumentId));
    setCanvasNodes((currentNodes) => currentNodes.filter((node) => node.cardDocumentId !== cardDocumentId));
    setSelectedCards((currentCards) => currentCards.filter((selectedCardId) => selectedCardId !== cardDocumentId));
    previewCapturesRef.current.delete(cardDocumentId);
    setStatus("Card removed from canvas.");
  }

  const registerPreviewCapture = useCallback((cardDocumentId: string, capturePreview: () => SelectedCardPreview) => {
    previewCapturesRef.current.set(cardDocumentId, capturePreview);

    return () => {
      if (previewCapturesRef.current.get(cardDocumentId) === capturePreview) {
        previewCapturesRef.current.delete(cardDocumentId);
      }
    };
  }, []);

  function selectModel(model: string) {
    setSelectedModel(model);
    setOpenMenu(null);
  }

  return (
    <main className="workspace" aria-label="Loki workspace">
      <Topbar
        hasUnsavedChanges={projectsController.hasUnsavedProjectChanges}
        onNewProject={projectsController.createNewProject}
        onOpenProjectManager={projectsController.openProjectManager}
        onSaveProject={projectsController.openSaveProjectDialog}
        projectName={projectsController.currentProjectName}
      />
      {projectsController.isProjectManagerOpen && (
        <ProjectManager
          currentProjectId={projectsController.currentProjectId}
          isPending={projectsController.isProjectActionPending}
          onArchiveProject={projectsController.archiveProject}
          onClose={projectsController.closeProjectManager}
          onCreateNewProject={projectsController.createNewProject}
          onDeleteProjectForever={projectsController.deleteProjectForever}
          onDuplicateProject={projectsController.duplicateProject}
          onExportProject={projectsController.exportProject}
          onImportProject={projectsController.importProjectFile}
          onOpenProject={projectsController.openProject}
          onRenameProject={projectsController.renameProject}
          onRestoreProject={projectsController.restoreProject}
          onTrashProject={projectsController.trashProject}
          projects={projectsController.projects}
        />
      )}
      {projectsController.isSaveProjectOpen && (
        <div className="modal-backdrop" role="presentation">
          <form
            className="project-modal"
            onSubmit={(event) => {
              event.preventDefault();
              void projectsController.submitSaveProject();
            }}
            aria-label="Save project"
          >
            <h2>Save project</h2>
            <label htmlFor="projectNameInput">Project name</label>
            <input
              id="projectNameInput"
              className="project-name-input"
              value={projectsController.projectNameDraft}
              onChange={(event) => projectsController.setProjectNameDraft(event.target.value)}
              autoFocus
            />
            <div className="project-modal-actions">
              <button className="button-tertiary" type="button" onClick={projectsController.closeSaveProjectDialog}>
                Cancel
              </button>
              <button className="button-primary" type="submit" disabled={projectsController.isProjectActionPending}>
                Save
              </button>
            </div>
          </form>
        </div>
      )}
      {projectsController.isUnsavedProjectDialogOpen && (
        <div className="modal-backdrop" role="presentation">
          <section className="project-modal" aria-label="Unsaved changes">
            <h2>Unsaved changes</h2>
            <p>
              Save the current canvas before leaving it, or discard the changes from this session.
            </p>
            <div className="project-modal-actions">
              <button
                className="button-tertiary"
                type="button"
                onClick={projectsController.cancelPendingProjectAction}
                disabled={projectsController.isProjectActionPending}
              >
                Cancel
              </button>
              <button
                className="button-secondary"
                type="button"
                onClick={() => void projectsController.discardChangesAndRunPendingProjectAction()}
                disabled={projectsController.isProjectActionPending}
              >
                Discard
              </button>
              <button
                className="button-primary"
                type="button"
                onClick={() => void projectsController.saveChangesAndRunPendingProjectAction()}
                disabled={projectsController.isProjectActionPending}
              >
                Save
              </button>
            </div>
          </section>
        </div>
      )}
      <AgentResponsePanel
        activityTitle={agentActivityTitle}
        clockTick={agentClockTick}
        lastActivityAt={agentLastActivityAt}
        messages={agentChatMessages}
        isOpen={isAgentResponseOpen}
        onToggle={() => setIsAgentResponseOpen((current) => !current)}
        response={latestAgentResponse}
        runStartedAt={agentRunStartedAt}
        status={agentRunStatus}
      />
      <CanvasStage
        documentsById={documentsById}
        nodes={canvasNodes}
        onCreateBbox={createBbox}
        onCreateNote={createNote}
        onCreateEditedMediaArtifact={createCardFromEditedMediaArtifact}
        onDeleteDocument={deleteDocument}
        onRenameDocument={renameDocument}
        onRedoDocument={redoDocument}
        onRegisterPreviewCapture={registerPreviewCapture}
        onStatus={setStatus}
        onToggleNode={toggleCanvasNode}
        onUpdateDocumentPrompt={updateDocumentPrompt}
        onUpdateBboxData={updateBboxData}
        onUpdateNodeFrame={updateCanvasNodeFrame}
        selectedIds={selectedCards}
      />
      <AgentComposer
        attachments={attachments}
        canvasNodes={cardDocuments}
        codexImageResolution={codexImageResolution}
        comfyAspectRatio={comfyAspectRatio}
        comfyDuration={comfyDuration}
        comfyImageMode={comfyImageMode}
        comfyImageProfile={comfyImageProfile}
        comfyResolution={comfyResolution}
        comfyTool={comfyTool}
        comfyVideoMode={comfyVideoMode}
        comfyVideoProfile={comfyVideoProfile}
        geminiImageModel={geminiImageModel}
        geminiImageResolution={geminiImageResolution}
        availableModels={availableModels}
        fileInputRef={fileInputRef}
        filteredSkills={filteredSkills}
        instruction={instruction}
        isSubmitting={isDirectGenerating}
        isRunning={agentRunStatus === "running"}
        composerMode={composerMode}
        onAttachFiles={handleFiles}
        onCreateAgent={handleCreateAgent}
        onCodexImageResolutionChange={setCodexImageResolution}
        onComfyAspectRatioChange={setComfyAspectRatio}
        onComfyDurationChange={setComfyDuration}
        onComfyImageModeChange={setComfyImageMode}
        onComfyImageProfileChange={setComfyImageProfile}
        onComfyResolutionChange={setComfyResolution}
        onComfyToolChange={setComfyTool}
        onComfyVideoModeChange={setComfyVideoMode}
        onComfyVideoProfileChange={setComfyVideoProfile}
        onGeminiImageModelChange={setGeminiImageModel}
        onGeminiImageResolutionChange={setGeminiImageResolution}
        onInstructionChange={setComposerInstruction}
        onInstructionKeyDown={handleInstructionKeyDown}
        onQuestionOption={answerPendingQuestion}
        onReferencedCardsChange={syncReferencedCards}
        onRemoveAttachment={removeAttachment}
        grokImageAspectRatio={grokImageAspectRatio}
        grokImageResolution={grokImageResolution}
        grokTool={grokTool}
        grokVideoAspectRatio={grokVideoAspectRatio}
        grokVideoDuration={grokVideoDuration}
        grokVideoResolution={grokVideoResolution}
        onGrokImageAspectRatioChange={setGrokImageAspectRatio}
        onGrokImageResolutionChange={setGrokImageResolution}
        onGrokToolChange={setGrokTool}
        onGrokVideoAspectRatioChange={setGrokVideoAspectRatio}
        onGrokVideoDurationChange={setGrokVideoDuration}
        onGrokVideoResolutionChange={setGrokVideoResolution}
        onSeedanceAspectRatioChange={setSeedanceAspectRatio}
        onSeedanceDurationChange={setSeedanceDuration}
        onSelectModel={selectModel}
        onSetComposerMode={setComposerMode}
        onStop={stopActiveAgentRun}
        onSubmit={submitInstruction}
        onToggleCard={toggleCard}
        onToggleSkill={toggleSkill}
        openMenu={openMenu}
        selectedCards={selectedCards}
        selectedCardCount={selectedCards.length}
        selectedCardLabel={selectedCardLabel}
        seedanceAspectRatio={seedanceAspectRatio}
        seedanceDuration={seedanceDuration}
        selectedModel={selectedModel}
        selectedSkillCount={selectedSkills.length}
        selectedSkills={selectedSkills}
        setOpenMenu={setOpenMenu}
        setSkillSearch={setSkillSearch}
        status={status}
        pendingQuestion={pendingQuestion}
        skillButtonLabel={skillButtonLabel}
        skillSearch={skillSearch}
      />
    </main>
  );
}
