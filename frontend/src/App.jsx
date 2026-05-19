import { useCallback, useEffect, useRef, useState } from "react";
import { createToolJob, listToolJobs, waitForToolJob } from "./api/toolJobs";
import { listTools } from "./api/tools";
import { AgentComposer } from "./components/AgentComposer";
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

export function App() {
  const [instruction, setInstruction] = useState("");
  const [canvasCards, setCanvasCards] = useState(initialCanvasCards);
  const [availableTools, setAvailableTools] = useState([]);
  const [selectedTools, setSelectedTools] = useState(["Auto"]);
  const [selectedCards, setSelectedCards] = useState([]);
  const [toolSearch, setToolSearch] = useState("");
  const [openMenu, setOpenMenu] = useState(null);
  const [status, setStatus] = useState("");
  const fileInputRef = useRef(null);
  const processedJobIdsRef = useRef(new Set());

  const closePopover = useCallback(() => setOpenMenu(null), []);
  useDismissablePopover(openMenu, closePopover);

  useEffect(() => {
    let isMounted = true;

    async function loadTools() {
      try {
        const tools = await listTools();
        if (isMounted) {
          setAvailableTools(tools.map((tool) => tool.name));
        }
      } catch {
        if (isMounted) {
          setAvailableTools([]);
        }
      }
    }

    loadTools();

    return () => {
      isMounted = false;
    };
  }, []);

  const addCardsFromJob = useCallback((job) => {
    if (processedJobIdsRef.current.has(job.id)) return;

    const generatedCards = job.result?.cards ?? [];
    if (job.status !== "succeeded" || generatedCards.length === 0) return;

    processedJobIdsRef.current.add(job.id);
    setCanvasCards((currentCards) => {
      const currentCardIds = new Set(currentCards.map((card) => card.id));
      const newCards = generatedCards.filter((card) => !currentCardIds.has(card.id));
      return [...currentCards, ...newCards];
    });
    setSelectedCards([generatedCards[0].id]);
  }, []);

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

  async function submitInstruction(event) {
    event.preventDefault();
    const text = instruction.trim();

    if (!text) {
      setStatus("Write an instruction before sending it to the agent.");
      return;
    }

    try {
      setStatus("Running tool job...");
      const createdJob = await createToolJob({
        toolId: toolButtonLabel,
        prompt: text,
        context: {
          tools: selectedTools,
          selectedElement: selectedNode?.name ?? null,
        },
        selectedCards,
        params: {},
      });
      const completedJob = await waitForToolJob(createdJob.id);

      if (completedJob.status === "failed") {
        setStatus(completedJob.error || "Tool job failed.");
        return;
      }

      addCardsFromJob(completedJob);

      setInstruction("");
      setStatus(`Tool job completed with ${selectedTools.join(", ")}.`);
    } catch {
      setStatus("Could not connect to the backend.");
    }
  }

  function handleInstructionKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form.requestSubmit();
    }
  }

  function handleFiles(event) {
    const count = event.target.files.length;
    if (count > 0) {
      setStatus(count === 1 ? "1 file attached." : `${count} files attached.`);
    }
  }

  function handleCreateAgent() {
    setStatus("Agent creation is coming soon.");
    setOpenMenu(null);
  }

  function toggleTool(tool) {
    setSelectedTools((currentTools) => toggleExclusiveAutoSelection(currentTools, tool));
  }

  function toggleCard(cardId) {
    setSelectedCards((currentCards) => toggleMultiSelection(currentCards, cardId));
  }

  return (
    <main className="workspace" aria-label="Loki workspace">
      <Topbar />
      <CanvasStage
        cards={canvasCards}
        onToggleCard={toggleCard}
        selectedCards={selectedCards}
        selectedNode={selectedNode}
      />
      <AgentComposer
        canvasNodes={canvasCards}
        fileInputRef={fileInputRef}
        filteredTools={filteredTools}
        instruction={instruction}
        onAttachFiles={handleFiles}
        onCreateAgent={handleCreateAgent}
        onInstructionChange={setInstruction}
        onInstructionKeyDown={handleInstructionKeyDown}
        onSubmit={submitInstruction}
        onToggleCard={toggleCard}
        onToggleTool={toggleTool}
        openMenu={openMenu}
        selectedCards={selectedCards}
        selectedCardCount={selectedCards.length}
        selectedCardLabel={selectedCardLabel}
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
