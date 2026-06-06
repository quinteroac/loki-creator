import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent, FormEvent, KeyboardEvent } from "react";
import { agentRunEventsUrl, createAgentRun, listAgentModels, stopAgentRun } from "./api/agentRuns";
import { importArtifact } from "./api/artifacts";
import { listProjects, loadProject, saveProject } from "./api/projects";
import { listSkillRuns, waitForSkillRun } from "./api/skillRuns";
import { listSkills } from "./api/skills";
import { AgentComposer } from "./components/AgentComposer";
import { AgentResponsePanel } from "./components/AgentResponsePanel";
import { CanvasStage } from "./components/CanvasStage";
import { Topbar } from "./components/Topbar";
import { initialCanvasNodes, initialCardDocuments } from "./data/workspace";
import { useDismissablePopover } from "./hooks/useDismissablePopover";
import {
  assignUniqueDisplayTitles,
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
  renameCardDocument,
  type CardPreviewCapture,
} from "./lib/cardDocuments";
import {
  filterBySearch,
  getFirstSelectedCardLabel,
  toggleExclusiveAutoSelection,
  toggleMultiSelection,
} from "./lib/selection";
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
  EditedMediaArtifact,
  ProjectSummary,
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

function dedupeCanvasNodesByDocumentId(nodes: CanvasNode[]): CanvasNode[] {
  const seenDocumentIds = new Set<string>();
  let hasDuplicate = false;
  const dedupedNodes = nodes.filter((node) => {
    if (seenDocumentIds.has(node.cardDocumentId)) {
      hasDuplicate = true;
      return false;
    }

    seenDocumentIds.add(node.cardDocumentId);
    return true;
  });

  return hasDuplicate ? dedupedNodes : nodes;
}

function createWorkspaceSnapshot(cardDocuments: CardDocument[], canvasNodes: CanvasNode[]) {
  return JSON.stringify({
    cardDocuments,
    canvasNodes: dedupeCanvasNodesByDocumentId(canvasNodes),
  });
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
  const [selectedCards, setSelectedCards] = useState<string[]>([]);
  const [attachments, setAttachments] = useState<AgentAttachment[]>([]);
  const [latestAgentResponse, setLatestAgentResponse] = useState<AgentRunResponse | null>(null);
  const [agentChatMessages, setAgentChatMessages] = useState<AgentChatMessage[]>([]);
  const [agentRunStatus, setAgentRunStatus] = useState<AgentRunStreamEvent["status"] | null>(null);
  const [agentRunStartedAt, setAgentRunStartedAt] = useState<number | null>(null);
  const [agentLastActivityAt, setAgentLastActivityAt] = useState<number | null>(null);
  const [agentClockTick, setAgentClockTick] = useState(0);
  const [pendingQuestion, setPendingQuestion] = useState<AgentQuestion | null>(null);
  const [pendingConversationId, setPendingConversationId] = useState<string | null>(null);
  const [pendingCollectedArgs, setPendingCollectedArgs] = useState<Record<string, string>>({});
  const [pendingAgentRequest, setPendingAgentRequest] = useState<AgentRunRequest | null>(null);
  const [isAgentResponseOpen, setIsAgentResponseOpen] = useState(false);
  const [isSaveProjectOpen, setIsSaveProjectOpen] = useState(false);
  const [projectNameDraft, setProjectNameDraft] = useState("");
  const [currentProjectId, setCurrentProjectId] = useState<string | null>(null);
  const [currentProjectName, setCurrentProjectName] = useState("Untitled project");
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [savedWorkspaceSnapshot, setSavedWorkspaceSnapshot] = useState(() =>
    createWorkspaceSnapshot(initialCardDocuments, initialCanvasNodes),
  );
  const [pendingProjectToOpenId, setPendingProjectToOpenId] = useState<string | null>(null);
  const [isNewProjectPending, setIsNewProjectPending] = useState(false);
  const [isUnsavedProjectDialogOpen, setIsUnsavedProjectDialogOpen] = useState(false);
  const [isProjectActionPending, setIsProjectActionPending] = useState(false);
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
          const userSkills = skills.filter((skill) => skill.visibility === "user");
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

    async function loadSavedProjects() {
      try {
        const savedProjects = await listProjects();
        if (isMounted) {
          setProjects(savedProjects);
        }
      } catch {
        if (isMounted) {
          setProjects([]);
        }
      }
    }

    loadSavedProjects();

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

  const addCardsFromRun = useCallback((run: SkillRun) => {
    if (!visibleSkillIds.has(run.skillId)) return;

    const generatedCards = (run.result?.cards ?? []).filter((card) => {
      if (processedCardIdsRef.current.has(card.id)) return false;
      if (!card.sourceSkillId) return true;
      return visibleSkillIds.has(card.sourceSkillId);
    }).map(normalizeCardDocument);
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

  }, [visibleSkillIds]);

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
  const currentWorkspaceSnapshot = useMemo(
    () => createWorkspaceSnapshot(cardDocuments, canvasNodes),
    [cardDocuments, canvasNodes],
  );
  const hasUnsavedProjectChanges = currentWorkspaceSnapshot !== savedWorkspaceSnapshot;
  const selectedDocument = cardDocuments.find((document) => document.id === selectedCards[0]);
  const filteredSkills = filterBySearch(availableSkills, skillSearch);
  const skillButtonLabel = selectedSkills[0] ?? "Auto";
  const selectedCardLabel = getFirstSelectedCardLabel(cardDocuments, selectedCards, "Selected cards");

  useEffect(() => {
    if (!hasUnsavedProjectChanges) return;

    function handleBeforeUnload(event: BeforeUnloadEvent) {
      event.preventDefault();
      event.returnValue = "";
    }

    window.addEventListener("beforeunload", handleBeforeUnload);

    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [hasUnsavedProjectChanges]);

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
      setInstruction("");
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

    setInstruction("");
    setAttachments([]);
    appendAgentStreamEvent({
      type: "done",
      status: "succeeded",
      message: "Agent completed.",
    });
    setStatus("Agent completed.");
  }

  async function buildAgentRequest(prompt: string): Promise<AgentRunRequest> {
    const selectedCardSnapshots = await createSelectedCardSnapshots(
      cardDocuments,
      selectedCards,
      previewCapturesRef.current,
    );

    return {
      agentId: "base-agent",
      prompt,
      model: selectedModel,
      skills: selectedSkills,
      selectedCards,
      selectedCardSnapshots,
      attachments,
      context: {
        skills: selectedSkills,
        model: selectedModel,
        agentId: "base-agent",
        selectedElement: selectedDocument ? getCardDisplayTitle(selectedDocument) : null,
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
      setInstruction("");
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
      setStatus("Write an instruction before sending it to the agent.");
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
    setSelectedCards((currentCards) => toggleMultiSelection(currentCards, cardId));
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

  function redoDocument(cardDocumentId: string) {
    const document = cardDocuments.find((candidate) => candidate.id === cardDocumentId);
    const prompt = document?.prompt.trim();

    if (!prompt) {
      setStatus("This card does not have a prompt to reuse.");
      return;
    }

    setInstruction(prompt);
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

  function openSaveProjectDialog() {
    setProjectNameDraft(currentProjectName === "Untitled project" ? "" : currentProjectName);
    setIsSaveProjectOpen(true);
    setIsUnsavedProjectDialogOpen(false);
    setOpenMenu(null);
  }

  async function toggleProjectMenu() {
    if (openMenu === "project-open") {
      setOpenMenu(null);
      return;
    }

    try {
      setProjects(await listProjects());
    } catch {
      setProjects([]);
      setStatus("Could not load projects.");
    }
    setOpenMenu("project-open");
  }

  function closeSaveProjectDialog() {
    setIsSaveProjectOpen(false);
    setPendingProjectToOpenId(null);
    setIsNewProjectPending(false);
  }

  async function persistCurrentProject(name: string) {
    if (!name) {
      setStatus("Name the project before saving.");
      return false;
    }

    try {
      setIsProjectActionPending(true);
      const cleanCanvasNodes = dedupeCanvasNodesByDocumentId(canvasNodes);
      const project = await saveProject({
        name,
        cardDocuments,
        canvasNodes: cleanCanvasNodes,
      });
      if (cleanCanvasNodes !== canvasNodes) {
        setCanvasNodes(cleanCanvasNodes);
      }
      setCurrentProjectId(project.id);
      setCurrentProjectName(project.name);
      setSavedWorkspaceSnapshot(createWorkspaceSnapshot(cardDocuments, cleanCanvasNodes));
      try {
        setProjects(await listProjects());
      } catch {
        // Project list refresh is best-effort after a successful save.
      }
      setStatus("Project saved.");
      return true;
    } catch {
      setStatus("Could not save project.");
      return false;
    } finally {
      setIsProjectActionPending(false);
    }
  }

  async function submitSaveProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = projectNameDraft.trim();
    const saved = await persistCurrentProject(name);
    if (!saved) return;

    setIsSaveProjectOpen(false);

    if (pendingProjectToOpenId) {
      const projectId = pendingProjectToOpenId;
      setPendingProjectToOpenId(null);
      await openProjectNow(projectId);
      return;
    }

    if (isNewProjectPending) {
      setIsNewProjectPending(false);
      createNewProjectNow();
    }
  }

  async function openProjectNow(projectId: string) {
    try {
      setIsProjectActionPending(true);
      const [project, runningRuns, completedRuns] = await Promise.all([
        loadProject(projectId),
        listSkillRuns({ status: "running" }),
        listSkillRuns({ status: "succeeded" }),
      ]);
      ignoreSkillRuns([...runningRuns, ...completedRuns]);
      hasSeededIgnoredSkillRunsRef.current = true;
      const projectDocuments = project.cardDocuments.map(normalizeCardDocument);
      const projectCanvasNodes = dedupeCanvasNodesByDocumentId(project.canvasNodes);
      processedCardIdsRef.current = new Set(projectDocuments.map((document) => document.id));

      setCardDocuments(projectDocuments);
      setCanvasNodes(projectCanvasNodes);
      setCurrentProjectId(project.id);
      setCurrentProjectName(project.name);
      setSavedWorkspaceSnapshot(createWorkspaceSnapshot(projectDocuments, projectCanvasNodes));
      setSelectedCards([]);
      setOpenMenu(null);
      setStatus("Project opened.");
    } catch {
      setStatus("Could not open project.");
    } finally {
      setIsProjectActionPending(false);
    }
  }

  async function openProject(projectId: string) {
    if (projectId === currentProjectId && !hasUnsavedProjectChanges) {
      setOpenMenu(null);
      return;
    }

    if (hasUnsavedProjectChanges) {
      setPendingProjectToOpenId(projectId);
      setIsUnsavedProjectDialogOpen(true);
      setOpenMenu(null);
      return;
    }

    await openProjectNow(projectId);
  }

  function createNewProjectNow() {
    const emptyCardDocuments: CardDocument[] = [];
    const emptyCanvasNodes: CanvasNode[] = [];

    processedCardIdsRef.current = new Set();
    previewCapturesRef.current.clear();
    setCardDocuments(emptyCardDocuments);
    setCanvasNodes(emptyCanvasNodes);
    setCurrentProjectId(null);
    setCurrentProjectName("Untitled project");
    setSavedWorkspaceSnapshot(createWorkspaceSnapshot(emptyCardDocuments, emptyCanvasNodes));
    setSelectedCards([]);
    setOpenMenu(null);
    setStatus("New project created.");
  }

  function createNewProject() {
    if (hasUnsavedProjectChanges) {
      setPendingProjectToOpenId(null);
      setIsNewProjectPending(true);
      setIsUnsavedProjectDialogOpen(true);
      setOpenMenu(null);
      return;
    }

    createNewProjectNow();
  }

  function cancelPendingProjectOpen() {
    setPendingProjectToOpenId(null);
    setIsNewProjectPending(false);
    setIsUnsavedProjectDialogOpen(false);
  }

  async function discardChangesAndOpenPendingProject() {
    if (isNewProjectPending) {
      setIsNewProjectPending(false);
      setIsUnsavedProjectDialogOpen(false);
      createNewProjectNow();
      return;
    }

    if (!pendingProjectToOpenId) {
      cancelPendingProjectOpen();
      return;
    }

    const projectId = pendingProjectToOpenId;
    setPendingProjectToOpenId(null);
    setIsUnsavedProjectDialogOpen(false);
    await openProjectNow(projectId);
  }

  async function saveChangesAndOpenPendingProject() {
    if (!pendingProjectToOpenId && !isNewProjectPending) {
      cancelPendingProjectOpen();
      return;
    }

    if (currentProjectName === "Untitled project") {
      setProjectNameDraft("");
      setIsUnsavedProjectDialogOpen(false);
      setIsSaveProjectOpen(true);
      return;
    }

    const saved = await persistCurrentProject(currentProjectName);
    if (!saved) return;

    if (isNewProjectPending) {
      setIsNewProjectPending(false);
      setIsUnsavedProjectDialogOpen(false);
      createNewProjectNow();
      return;
    }

    const projectId = pendingProjectToOpenId;
    if (!projectId) {
      cancelPendingProjectOpen();
      return;
    }

    setPendingProjectToOpenId(null);
    setIsUnsavedProjectDialogOpen(false);
    await openProjectNow(projectId);
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
        hasUnsavedChanges={hasUnsavedProjectChanges}
        isProjectMenuOpen={openMenu === "project-open"}
        onNewProject={createNewProject}
        onOpenProject={openProject}
        onSaveProject={openSaveProjectDialog}
        onToggleProjectMenu={toggleProjectMenu}
        projectName={currentProjectName}
        projects={projects}
      />
      {isSaveProjectOpen && (
        <div className="modal-backdrop" role="presentation">
          <form className="project-modal" onSubmit={submitSaveProject} aria-label="Save project">
            <h2>Save project</h2>
            <label htmlFor="projectNameInput">Project name</label>
            <input
              id="projectNameInput"
              className="project-name-input"
              value={projectNameDraft}
              onChange={(event) => setProjectNameDraft(event.target.value)}
              autoFocus
            />
            <div className="project-modal-actions">
              <button className="button-tertiary" type="button" onClick={closeSaveProjectDialog}>
                Cancel
              </button>
              <button className="button-primary" type="submit" disabled={isProjectActionPending}>
                Save
              </button>
            </div>
          </form>
        </div>
      )}
      {isUnsavedProjectDialogOpen && (
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
                onClick={cancelPendingProjectOpen}
                disabled={isProjectActionPending}
              >
                Cancel
              </button>
              <button
                className="button-secondary"
                type="button"
                onClick={discardChangesAndOpenPendingProject}
                disabled={isProjectActionPending}
              >
                Discard
              </button>
              <button
                className="button-primary"
                type="button"
                onClick={saveChangesAndOpenPendingProject}
                disabled={isProjectActionPending}
              >
                Save
              </button>
            </div>
          </section>
        </div>
      )}
      <AgentResponsePanel
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
        onCreateNote={createNote}
        onCreateEditedMediaArtifact={createCardFromEditedMediaArtifact}
        onDeleteDocument={deleteDocument}
        onRenameDocument={renameDocument}
        onRedoDocument={redoDocument}
        onRegisterPreviewCapture={registerPreviewCapture}
        onStatus={setStatus}
        onToggleNode={toggleCanvasNode}
        onUpdateDocumentPrompt={updateDocumentPrompt}
        onUpdateNodeFrame={updateCanvasNodeFrame}
        selectedIds={selectedCards}
      />
      <AgentComposer
        attachments={attachments}
        canvasNodes={cardDocuments}
        availableModels={availableModels}
        fileInputRef={fileInputRef}
        filteredSkills={filteredSkills}
        instruction={instruction}
        isRunning={agentRunStatus === "running"}
        onAttachFiles={handleFiles}
        onCreateAgent={handleCreateAgent}
        onInstructionChange={setInstruction}
        onInstructionKeyDown={handleInstructionKeyDown}
        onQuestionOption={answerPendingQuestion}
        onRemoveAttachment={removeAttachment}
        onSelectModel={selectModel}
        onStop={stopActiveAgentRun}
        onSubmit={submitInstruction}
        onToggleCard={toggleCard}
        onToggleSkill={toggleSkill}
        openMenu={openMenu}
        selectedCards={selectedCards}
        selectedCardCount={selectedCards.length}
        selectedCardLabel={selectedCardLabel}
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
