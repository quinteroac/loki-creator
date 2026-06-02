import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent, FormEvent, KeyboardEvent } from "react";
import { agentRunEventsUrl, createAgentRun, listAgentModels } from "./api/agentRuns";
import { archiveArtifacts, importArtifact } from "./api/artifacts";
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
  createCardDocumentForImportedArtifact,
  createCanvasNodeForDocument,
  createSelectedCardSnapshots,
  getCardArtifactUrls,
  getCardDisplayTitle,
  getFileDimensions,
  normalizeCardDocument,
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
  CanvasNodeFrame,
  CardDocument,
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
  const [selectedCards, setSelectedCards] = useState<string[]>([]);
  const [attachments, setAttachments] = useState<AgentAttachment[]>([]);
  const [latestAgentResponse, setLatestAgentResponse] = useState<AgentRunResponse | null>(null);
  const [agentChatMessages, setAgentChatMessages] = useState<AgentChatMessage[]>([]);
  const [agentRunStatus, setAgentRunStatus] = useState<AgentRunStreamEvent["status"] | null>(null);
  const [pendingQuestion, setPendingQuestion] = useState<AgentQuestion | null>(null);
  const [pendingConversationId, setPendingConversationId] = useState<string | null>(null);
  const [pendingCollectedArgs, setPendingCollectedArgs] = useState<Record<string, string>>({});
  const [pendingAgentRequest, setPendingAgentRequest] = useState<AgentRunRequest | null>(null);
  const [isAgentResponseOpen, setIsAgentResponseOpen] = useState(false);
  const [isSaveProjectOpen, setIsSaveProjectOpen] = useState(false);
  const [projectNameDraft, setProjectNameDraft] = useState("");
  const [currentProjectName, setCurrentProjectName] = useState("Untitled project");
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [skillSearch, setSkillSearch] = useState("");
  const [openMenu, setOpenMenu] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const agentEventSourceRef = useRef<EventSource | null>(null);
  const processedRunIdsRef = useRef<Set<string>>(new Set());
  const previewCapturesRef = useRef<Map<string, CardPreviewCapture>>(new Map());

  const closePopover = useCallback(() => setOpenMenu(null), []);
  useDismissablePopover(openMenu, closePopover);
  const closeAgentResponse = useCallback(() => setIsAgentResponseOpen(false), []);
  useDismissablePopover(isAgentResponseOpen ? "agent-response" : null, closeAgentResponse);

  useEffect(() => () => agentEventSourceRef.current?.close(), []);

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
        setSelectedModel((currentModel) =>
          models.some((model) => model.label === currentModel) ? currentModel : models[0].label,
        );
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
    if (processedRunIdsRef.current.has(run.id)) return;

    if (run.status !== "succeeded") return;

    processedRunIdsRef.current.add(run.id);
    if (!visibleSkillIds.has(run.skillId)) return;

    const generatedCards = (run.result?.cards ?? []).filter((card) => {
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
        const runs = await listSkillRuns({ status: "succeeded" });
        if (!isMounted) return;

        runs.forEach(addCardsFromRun);
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
  const selectedDocument = cardDocuments.find((document) => document.id === selectedCards[0]);
  const filteredSkills = filterBySearch(availableSkills, skillSearch);
  const skillButtonLabel = selectedSkills[0] ?? "Auto";
  const selectedCardLabel = getFirstSelectedCardLabel(cardDocuments, selectedCards, "Selected cards");

  function appendAgentStreamEvent(event: AgentRunStreamEvent) {
    if (event.status) {
      setAgentRunStatus(event.status);
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
    };
  }

  async function handleAgentRunResponse(agentRun: AgentRunResponse, baseRequest: AgentRunRequest) {
    setLatestAgentResponse(agentRun);

    if (agentRun.status === "needs_input" && agentRun.question && agentRun.conversationId) {
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
      setStatus(agentRun.error || "Agent run failed.");
      return;
    }

    for (const runId of agentRun.skillRunIds) {
      const completedRun = await waitForSkillRun(runId);
      if (completedRun.status === "failed") {
        setStatus(completedRun.error || "Skill run failed.");
        return;
      }
      addCardsFromRun(completedRun);
    }

    setInstruction("");
    setAttachments([]);
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
      setPendingQuestion(answeredQuestion);
      setStatus(error instanceof Error ? error.message : "Could not connect to the agent bridge.");
    }
  }

  async function submitInstruction(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = instruction.trim();

    if (pendingQuestion) {
      await answerPendingQuestion(text);
      return;
    }

    if (!text) {
      setStatus("Write an instruction before sending it to the agent.");
      return;
    }

    try {
      setStatus("Running agent...");
      const streamId = createClientId("agent_run");
      const request = await buildAgentRequest(text);
      request.streamId = streamId;
      startAgentRunStream(streamId);
      const agentRun = await createAgentRun(request);
      await handleAgentRunResponse(agentRun, request);
    } catch (error) {
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

      setCardDocuments((currentDocuments) => {
        const newDocuments = assignUniqueDisplayTitles(importedDocuments, currentDocuments);
        setSelectedCards(newDocuments.map((document) => document.id));
        setCanvasNodes((currentNodes) => [
          ...currentNodes,
          ...newDocuments.map((document, index) =>
            createCanvasNodeForDocument(document, currentNodes.length + index, canvasWidth),
          ),
        ]);

        return [...currentDocuments, ...newDocuments];
      });
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
          ? {
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

  async function deleteDocument(cardDocumentId: string) {
    const document = cardDocuments.find((candidate) => candidate.id === cardDocumentId);
    const artifactUrls = document ? getCardArtifactUrls(document) : [];

    setCardDocuments((currentDocuments) => currentDocuments.filter((candidate) => candidate.id !== cardDocumentId));
    setCanvasNodes((currentNodes) => currentNodes.filter((node) => node.cardDocumentId !== cardDocumentId));
    setSelectedCards((currentCards) => currentCards.filter((selectedCardId) => selectedCardId !== cardDocumentId));
    previewCapturesRef.current.delete(cardDocumentId);
    setStatus("Card removed from canvas.");

    try {
      await archiveArtifacts(artifactUrls);
    } catch {
      setStatus("Card removed from canvas. Could not archive its files.");
    }
  }

  function openSaveProjectDialog() {
    setProjectNameDraft(currentProjectName === "Untitled project" ? "" : currentProjectName);
    setIsSaveProjectOpen(true);
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
  }

  async function submitSaveProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = projectNameDraft.trim();

    if (!name) {
      setStatus("Name the project before saving.");
      return;
    }

    try {
      const project = await saveProject({
        name,
        cardDocuments,
        canvasNodes,
      });
      setCurrentProjectName(project.name);
      setProjects(await listProjects());
      setIsSaveProjectOpen(false);
      setStatus("Project saved.");
    } catch {
      setStatus("Could not save project.");
    }
  }

  async function openProject(projectId: string) {
    try {
      const project = await loadProject(projectId);
      const completedRuns = await listSkillRuns({ status: "succeeded" });
      completedRuns.forEach((run) => processedRunIdsRef.current.add(run.id));

      setCardDocuments(project.cardDocuments.map(normalizeCardDocument));
      setCanvasNodes(project.canvasNodes);
      setCurrentProjectName(project.name);
      setSelectedCards([]);
      setOpenMenu(null);
      setStatus("Project opened.");
    } catch {
      setStatus("Could not open project.");
    }
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
        isProjectMenuOpen={openMenu === "project-open"}
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
              <button className="button-primary" type="submit">
                Save
              </button>
            </div>
          </form>
        </div>
      )}
      <AgentResponsePanel
        messages={agentChatMessages}
        isOpen={isAgentResponseOpen}
        onToggle={() => setIsAgentResponseOpen((current) => !current)}
        response={latestAgentResponse}
        status={agentRunStatus}
      />
      <CanvasStage
        documentsById={documentsById}
        nodes={canvasNodes}
        onDeleteDocument={deleteDocument}
        onRenameDocument={renameDocument}
        onRedoDocument={redoDocument}
        onRegisterPreviewCapture={registerPreviewCapture}
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
        onAttachFiles={handleFiles}
        onCreateAgent={handleCreateAgent}
        onInstructionChange={setInstruction}
        onInstructionKeyDown={handleInstructionKeyDown}
        onQuestionOption={answerPendingQuestion}
        onRemoveAttachment={removeAttachment}
        onSelectModel={selectModel}
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
