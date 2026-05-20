import { useCallback, useEffect, useRef, useState } from "react";
import type { ChangeEvent, FormEvent, KeyboardEvent } from "react";
import { createAgentRun, listAgentModels } from "./api/agentRuns";
import { listToolJobs, waitForToolJob } from "./api/toolJobs";
import { listTools } from "./api/tools";
import { AgentComposer } from "./components/AgentComposer";
import { AgentResponsePanel } from "./components/AgentResponsePanel";
import { CanvasStage } from "./components/CanvasStage";
import { Topbar } from "./components/Topbar";
import { initialCanvasCards } from "./data/workspace";
import { useDismissablePopover } from "./hooks/useDismissablePopover";
import {
  filterBySearch,
  getFirstSelectedCardLabel,
  toggleExclusiveAutoSelection,
  toggleMultiSelection,
} from "./lib/selection";
import type { AgentModel, AgentRunResponse, GeneratedCard, ToolJob } from "./types";

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
  const [canvasCards, setCanvasCards] = useState(initialCanvasCards);
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
    });
    if (generatedCards.length === 0) return;

    setCanvasCards((currentCards: GeneratedCard[]) => {
      const currentCardIds = new Set(currentCards.map((card) => card.id));
      const newCards = generatedCards.filter((card) => !currentCardIds.has(card.id));
      return [...currentCards, ...newCards];
    });
    const firstGeneratedCard = generatedCards[0];
    if (firstGeneratedCard) {
      setSelectedCards([firstGeneratedCard.id]);
    }
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

  const selectedNode = canvasCards.find((card) => card.id === selectedCards[0]);
  const filteredTools = filterBySearch(availableTools, toolSearch);
  const toolButtonLabel = selectedTools[0] ?? "Auto";
  const selectedCardLabel = getFirstSelectedCardLabel(canvasCards, selectedCards, "Selected cards");

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
          selectedElement: selectedNode?.name ?? null,
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
        cards={canvasCards}
        onToggleCard={toggleCard}
        selectedCards={selectedCards}
        selectedNode={selectedNode}
      />
      <AgentComposer
        canvasNodes={canvasCards}
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
