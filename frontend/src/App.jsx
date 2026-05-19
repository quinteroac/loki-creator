import { useEffect, useRef, useState } from "react";
import { ArrowUp, Bot, Check, Layers, Paperclip, Search, Wrench } from "lucide-react";

const API_URL = import.meta.env.VITE_API_URL ?? "";

const canvasNodes = [
];

const availableTools = [
  "Auto",
  "Image",
  "Video",
  "SFX",
  "Voice",
  "Music",
  "3D Asset",
  "Gaussian Splat",
  "World Generation",
  "HTML 5 Canva",
];

export function App() {
  const [instruction, setInstruction] = useState("");
  const [selectedTools, setSelectedTools] = useState(["Auto"]);
  const [selectedCards, setSelectedCards] = useState([]);
  const [toolSearch, setToolSearch] = useState("");
  const [selectedNodeId] = useState(null);
  const [openMenu, setOpenMenu] = useState(null);
  const [status, setStatus] = useState("");
  const fileInputRef = useRef(null);

  const selectedNode = canvasNodes.find((node) => node.id === selectedNodeId);
  const filteredTools = availableTools.filter((tool) =>
    tool.toLowerCase().includes(toolSearch.trim().toLowerCase()),
  );
  const toolButtonLabel = selectedTools[0] ?? "Auto";
  const selectedToolCount = selectedTools.length;
  const selectedCardItems = canvasNodes.filter((node) => selectedCards.includes(node.id));
  const selectedCardLabel = selectedCardItems[0]?.title ?? selectedCardItems[0]?.id ?? "Selected cards";
  const selectedCardCount = selectedCards.length;

  async function submitInstruction(event) {
    event.preventDefault();
    const text = instruction.trim();

    if (!text) {
      setStatus("Write an instruction before sending it to the agent.");
      return;
    }

    try {
      const response = await fetch(`${API_URL}/api/instructions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          instruction: text,
          tool: toolButtonLabel,
          tools: selectedTools,
          selectedCards,
          selectedElement: selectedNode?.title ?? null,
        }),
      });

      if (!response.ok) {
        throw new Error("Instruction request failed");
      }

      setInstruction("");
      setStatus(`Instruction sent with ${selectedTools.join(", ")}.`);
    } catch {
      setStatus("Could not connect to the backend.");
    }
  }

  function handleKeyDown(event) {
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

  function toggleTool(tool) {
    if (tool === "Auto") {
      setSelectedTools(["Auto"]);
      return;
    }

    setSelectedTools((currentTools) => {
      const withoutAuto = currentTools.filter((currentTool) => currentTool !== "Auto");

      if (withoutAuto.includes(tool)) {
        const nextTools = withoutAuto.filter((currentTool) => currentTool !== tool);
        return nextTools.length > 0 ? nextTools : ["Auto"];
      }

      return [...withoutAuto, tool];
    });
  }

  function toggleCard(cardId) {
    setSelectedCards((currentCards) => {
      if (currentCards.includes(cardId)) {
        return currentCards.filter((currentCard) => currentCard !== cardId);
      }

      return [...currentCards, cardId];
    });
  }

  useEffect(() => {
    if (!openMenu) return undefined;

    function closeOpenMenu(event) {
      const target = event.target;

      if (!(target instanceof Element)) return;
      if (target.closest("[data-popover]") || target.closest("[data-popover-trigger]")) return;

      setOpenMenu(null);
    }

    function closeOpenMenuWithKeyboard(event) {
      if (event.key === "Escape") {
        setOpenMenu(null);
      }
    }

    document.addEventListener("pointerdown", closeOpenMenu);
    document.addEventListener("keydown", closeOpenMenuWithKeyboard);

    return () => {
      document.removeEventListener("pointerdown", closeOpenMenu);
      document.removeEventListener("keydown", closeOpenMenuWithKeyboard);
    };
  }, [openMenu]);

  return (
    <main className="workspace" aria-label="Loki workspace">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Loki Creator">
          <span className="brand-mark" aria-hidden="true">
            L
          </span>
          <span>Loki Creator</span>
        </a>
        <div className="project-switcher" aria-label="Current project">
          <span className="project-dot" aria-hidden="true" />
          <span>Untitled project</span>
        </div>
        <button className="button-secondary compact" type="button">
          Share
        </button>
      </header>

      <section className="canvas-shell" aria-label="Creative canvas">
        <div className="canvas" id="creativeCanvas" tabIndex={0}>
          <div className="canvas-selection-note">
            {selectedNode ? `${selectedNode.title} selected` : "No selection"}
          </div>
        </div>
      </section>

      <section className="composer-wrap" aria-label="Agent instructions">
        {openMenu === "agents" && (
          <div className="popover" data-popover aria-label="Agent options">
            <button
              type="button"
              onClick={() => {
                setStatus("Agent creation is coming soon.");
                setOpenMenu(null);
              }}
            >
              + New Agent
            </button>
          </div>
        )}

        {openMenu === "tool-picker" && (
          <div className="popover tools-popover" data-popover aria-label="Select tools">
            <label className="tool-search">
              <Search size={14} strokeWidth={2} />
              <input
                type="search"
                value={toolSearch}
                onChange={(event) => setToolSearch(event.target.value)}
                placeholder="Search tools"
                aria-label="Search tools"
                autoFocus
              />
            </label>
            <div className="tool-list">
              {filteredTools.map((tool) => {
                const isSelected = selectedTools.includes(tool);

                return (
                  <button
                    className={`tool-option ${isSelected ? "selected" : ""}`}
                    key={tool}
                    type="button"
                    onClick={() => toggleTool(tool)}
                  >
                    <span>{tool}</span>
                    {isSelected && <Check size={14} strokeWidth={2} />}
                  </button>
                );
              })}
              {filteredTools.length === 0 && <p className="tool-empty">No matching tools</p>}
            </div>
          </div>
        )}

        {openMenu === "elements" && (
          <div className="popover elements-popover" data-popover aria-label="Canvas elements">
            <button type="button" onClick={() => setOpenMenu(null)}>
              No canvas elements yet
            </button>
          </div>
        )}

        {openMenu === "selected-cards" && (
          <div className="popover cards-popover" data-popover aria-label="Selected cards">
            <div className="tool-list">
              {canvasNodes.map((node) => {
                const isSelected = selectedCards.includes(node.id);

                return (
                  <button
                    className={`tool-option ${isSelected ? "selected" : ""}`}
                    key={node.id}
                    type="button"
                    onClick={() => toggleCard(node.id)}
                  >
                    <span>{node.id}</span>
                    {isSelected && <Check size={14} strokeWidth={2} />}
                  </button>
                );
              })}
              {canvasNodes.length === 0 && <p className="tool-empty">No cards in canvas</p>}
            </div>
          </div>
        )}

        <form className="composer" onSubmit={submitInstruction}>
          <div className="composer-main">
            <textarea
              name="instruction"
              rows={1}
              value={instruction}
              onChange={(event) => setInstruction(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Write to imagine"
              aria-label="Instruction for the agent"
            />

            <div className="composer-actions">
              <input ref={fileInputRef} type="file" hidden multiple onChange={handleFiles} />
              <button
                className="chat-chip"
                type="button"
                data-popover-trigger
                aria-expanded={openMenu === "agents"}
                onClick={() => setOpenMenu(openMenu === "agents" ? null : "agents")}
              >
                <Bot size={14} strokeWidth={2} />
                <span>Agent</span>
              </button>
              <button
                className="chat-chip"
                type="button"
                data-popover-trigger
                aria-expanded={openMenu === "tool-picker"}
                onClick={() => setOpenMenu(openMenu === "tool-picker" ? null : "tool-picker")}
              >
                <Wrench size={14} strokeWidth={2} />
                <span>{toolButtonLabel}</span>
                {selectedToolCount > 1 && <small>{selectedToolCount}</small>}
              </button>
              <button
                className="chat-chip"
                type="button"
                data-popover-trigger
                aria-expanded={openMenu === "selected-cards"}
                onClick={() => setOpenMenu(openMenu === "selected-cards" ? null : "selected-cards")}
              >
                <Layers size={14} strokeWidth={2} />
                <span>{selectedCardLabel}</span>
                {selectedCardCount > 1 && <small>{selectedCardCount}</small>}
              </button>
              <button
                className="chat-chip"
                type="button"
                aria-label="Attach file"
                title="Attach"
                onClick={() => fileInputRef.current?.click()}
              >
                <Paperclip size={14} strokeWidth={2} />
                <span>Attach</span>
              </button>
            </div>
          </div>

          <button className="send-orb" type="submit" aria-label="Send instruction">
            <ArrowUp size={20} strokeWidth={2} />
          </button>
        </form>
        <p className="composer-status" aria-live="polite">
          {status}
        </p>
      </section>
    </main>
  );
}
