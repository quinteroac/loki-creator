import { useCallback, useRef, useState } from "react";
import { sendInstruction } from "./api/instructions";
import { AgentComposer } from "./components/AgentComposer";
import { CanvasStage } from "./components/CanvasStage";
import { Topbar } from "./components/Topbar";
import { availableTools, canvasNodes } from "./data/workspace";
import { useDismissablePopover } from "./hooks/useDismissablePopover";
import {
  filterBySearch,
  getFirstSelectedCardLabel,
  toggleExclusiveAutoSelection,
  toggleMultiSelection,
} from "./lib/selection";

export function App() {
  const [instruction, setInstruction] = useState("");
  const [selectedTools, setSelectedTools] = useState(["Auto"]);
  const [selectedCards, setSelectedCards] = useState([]);
  const [toolSearch, setToolSearch] = useState("");
  const [selectedNodeId] = useState(null);
  const [openMenu, setOpenMenu] = useState(null);
  const [status, setStatus] = useState("");
  const fileInputRef = useRef(null);

  const closePopover = useCallback(() => setOpenMenu(null), []);
  useDismissablePopover(openMenu, closePopover);

  const selectedNode = canvasNodes.find((node) => node.id === selectedNodeId);
  const filteredTools = filterBySearch(availableTools, toolSearch);
  const toolButtonLabel = selectedTools[0] ?? "Auto";
  const selectedCardLabel = getFirstSelectedCardLabel(canvasNodes, selectedCards, "Selected cards");

  async function submitInstruction(event) {
    event.preventDefault();
    const text = instruction.trim();

    if (!text) {
      setStatus("Write an instruction before sending it to the agent.");
      return;
    }

    try {
      await sendInstruction({
        instruction: text,
        tool: toolButtonLabel,
        tools: selectedTools,
        selectedCards,
        selectedElement: selectedNode?.title ?? null,
      });

      setInstruction("");
      setStatus(`Instruction sent with ${selectedTools.join(", ")}.`);
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
      <CanvasStage selectedNode={selectedNode} />
      <AgentComposer
        canvasNodes={canvasNodes}
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
