import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent, FormEvent, KeyboardEvent } from "react";
import { createAgentRun, listAgentModels } from "./api/agentRuns";
import { listToolJobs, waitForToolJob } from "./api/toolJobs";
import { listTools } from "./api/tools";
import { AgentComposer } from "./components/AgentComposer";
import { AgentResponsePanel } from "./components/AgentResponsePanel";
import { CanvasStage } from "./components/CanvasStage";
import { Topbar } from "./components/Topbar";
import { initialCanvasNodes, initialCardDocuments } from "./data/workspace";
import { useDismissablePopover } from "./hooks/useDismissablePopover";
import {
  assignUniqueDisplayTitles,
  createCanvasNodeForDocument,
  getCardDisplayTitle,
  normalizeCardDocument,
  renameCardDocument,
} from "./lib/cardDocuments";
import {
  filterBySearch,
  getFirstSelectedCardLabel,
  toggleExclusiveAutoSelection,
  toggleMultiSelection,
} from "./lib/selection";
import type { AgentModel, AgentRunResponse, CanvasNodeFrame, CardDocument, ToolJob } from "./types";

const fallbackModels: AgentModel[] = [
  {
    id: "loki-default",
    provider: "loki",
    name: "Loki Default",
    label: "Loki Default",
  },
];

export function App() {
  const [instruction, setInstruction] = useState("");
  const [cardDocuments, setCardDocuments] = useState(initialCardDocuments);
  const [canvasNodes, setCanvasNodes] = useState(initialCanvasNodes);
  const [availableTools, setAvailableTools] = useState<string[]>([]);
  const [visibleToolIds, setVisibleToolIds] = useState<Set<string>>(new Set());
  const [selectedTools, setSelectedTools] = useState(["Auto"]);
  const [availableModels, setAvailableModels] = useState<AgentModel[]>(fallbackModels);
  const [selectedModel, setSelectedModel] = useState(fallbackModels[0].label);
  const [selectedCards, setSelectedCards] = useState<string[]>([]);
  const [latestAgentResponse, setLatestAgentResponse] = useState<AgentRunResponse | null>(null);
  const [isAgentResponseOpen, setIsAgentResponseOpen] = useState(false);
  const [toolSearch, setToolSearch] = useState("");
  const [openMenu, setOpenMenu] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const processedJobIdsRef = useRef<Set<string>>(new Set());

  const closePopover = useCallback(() => setOpenMenu(null), []);
  useDismissablePopover(openMenu, closePopover);
  const closeAgentResponse = useCallback(() => setIsAgentResponseOpen(false), []);
  useDismissablePopover(isAgentResponseOpen ? "agent-response" : null, closeAgentResponse);

  useEffect(() => {
    let isMounted = true;

    async function loadTools() {
      try {
        const tools = await listTools();
        if (isMounted) {
          setAvailableTools(tools.map((tool) => tool.name));
          setVisibleToolIds(new Set(tools.map((tool) => tool.id)));
        }
      } catch {
        if (isMounted) {
          setAvailableTools([]);
          setVisibleToolIds(new Set());
        }
      }
    }

    loadTools();

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

  const addCardsFromJob = useCallback((job: ToolJob) => {
    if (processedJobIdsRef.current.has(job.id)) return;

    if (job.status !== "succeeded") return;

    processedJobIdsRef.current.add(job.id);
    if (!visibleToolIds.has(job.toolId)) return;

    const generatedCards = (job.result?.cards ?? []).filter((card) => {
      if (!card.sourceToolId) return true;
      return visibleToolIds.has(card.sourceToolId);
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

    setSelectedCards([generatedCards[0].id]);
  }, [visibleToolIds]);

  useEffect(() => {
    let isMounted = true;

    async function syncCompletedToolJobs() {
      try {
        const jobs = await listToolJobs({ status: "succeeded" });
        if (!isMounted) return;

        jobs.forEach(addCardsFromJob);
      } catch {
        // Job sync is best-effort; the next interval will reconcile completed jobs.
      }
    }

    syncCompletedToolJobs();
    const intervalId = window.setInterval(syncCompletedToolJobs, 1200);

    return () => {
      isMounted = false;
      window.clearInterval(intervalId);
    };
  }, [addCardsFromJob]);

  const documentsById = useMemo(
    () => Object.fromEntries(cardDocuments.map((document) => [document.id, document])),
    [cardDocuments],
  );
  const selectedDocument = cardDocuments.find((document) => document.id === selectedCards[0]);
  const filteredTools = filterBySearch(availableTools, toolSearch);
  const toolButtonLabel = selectedTools[0] ?? "Auto";
  const selectedCardLabel = getFirstSelectedCardLabel(cardDocuments, selectedCards, "Selected cards");

  async function submitInstruction(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = instruction.trim();

    if (!text) {
      setStatus("Write an instruction before sending it to the agent.");
      return;
    }

    try {
      setStatus("Running agent...");
      const agentRun = await createAgentRun({
        agentId: "base-agent",
        prompt: text,
        model: selectedModel,
        tools: selectedTools,
        selectedCards,
        context: {
          tools: selectedTools,
          model: selectedModel,
          agentId: "base-agent",
          selectedElement: selectedDocument ? getCardDisplayTitle(selectedDocument) : null,
        },
      });

      setLatestAgentResponse(agentRun);
      setIsAgentResponseOpen(false);

      if (agentRun.status === "failed") {
        setStatus(agentRun.error || "Agent run failed.");
        return;
      }

      for (const jobId of agentRun.toolJobIds) {
        const completedJob = await waitForToolJob(jobId);
        addCardsFromJob(completedJob);
      }

      setInstruction("");
      setStatus("Agent completed.");
    } catch {
      setStatus("Could not connect to the agent bridge.");
    }
  }

  function handleInstructionKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  function handleFiles(event: ChangeEvent<HTMLInputElement>) {
    const count = event.target.files?.length ?? 0;
    if (count > 0) {
      setStatus(count === 1 ? "1 file attached." : `${count} files attached.`);
    }
  }

  function handleCreateAgent() {
    setStatus("Agent creation is coming soon.");
    setOpenMenu(null);
  }

  function toggleTool(tool: string) {
    setSelectedTools((currentTools) => toggleExclusiveAutoSelection(currentTools, tool));
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

  function selectModel(model: string) {
    setSelectedModel(model);
    setOpenMenu(null);
  }

  return (
    <main className="workspace" aria-label="Loki workspace">
      <Topbar />
      <AgentResponsePanel
        isOpen={isAgentResponseOpen}
        onToggle={() => setIsAgentResponseOpen((current) => !current)}
        response={latestAgentResponse}
      />
      <CanvasStage
        documentsById={documentsById}
        nodes={canvasNodes}
        onRenameDocument={renameDocument}
        onToggleNode={toggleCanvasNode}
        onUpdateNodeFrame={updateCanvasNodeFrame}
        selectedDocument={selectedDocument}
        selectedIds={selectedCards}
      />
      <AgentComposer
        canvasNodes={cardDocuments}
        availableModels={availableModels}
        fileInputRef={fileInputRef}
        filteredTools={filteredTools}
        instruction={instruction}
        onAttachFiles={handleFiles}
        onCreateAgent={handleCreateAgent}
        onInstructionChange={setInstruction}
        onInstructionKeyDown={handleInstructionKeyDown}
        onSelectModel={selectModel}
        onSubmit={submitInstruction}
        onToggleCard={toggleCard}
        onToggleTool={toggleTool}
        openMenu={openMenu}
        selectedCards={selectedCards}
        selectedCardCount={selectedCards.length}
        selectedCardLabel={selectedCardLabel}
        selectedModel={selectedModel}
        selectedToolCount={selectedTools.length}
        selectedTools={selectedTools}
        setOpenMenu={setOpenMenu}
        setToolSearch={setToolSearch}
        status={status}
        toolButtonLabel={toolButtonLabel}
        toolSearch={toolSearch}
      />
    </main>
  );
}
