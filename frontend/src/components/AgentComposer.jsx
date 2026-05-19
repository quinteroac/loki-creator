import { ArrowUp, Bot, Check, Layers, Paperclip, Search, Wrench } from "lucide-react";

export function AgentComposer({
  canvasNodes,
  filteredTools,
  instruction,
  onAttachFiles,
  onCreateAgent,
  onInstructionChange,
  onInstructionKeyDown,
  onSubmit,
  onToggleCard,
  onToggleTool,
  openMenu,
  selectedCards,
  selectedCardCount,
  selectedCardLabel,
  selectedToolCount,
  selectedTools,
  setOpenMenu,
  setToolSearch,
  status,
  toolButtonLabel,
  toolSearch,
  fileInputRef,
}) {
  return (
    <section className="composer-wrap" aria-label="Agent instructions">
      {openMenu === "agents" && (
        <div className="popover" data-popover aria-label="Agent options">
          <button type="button" onClick={onCreateAgent}>
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
                  onClick={() => onToggleTool(tool)}
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
                  onClick={() => onToggleCard(node.id)}
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

      <form className="composer" onSubmit={onSubmit}>
        <div className="composer-main">
          <textarea
            name="instruction"
            rows={1}
            value={instruction}
            onChange={(event) => onInstructionChange(event.target.value)}
            onKeyDown={onInstructionKeyDown}
            placeholder="Write to imagine"
            aria-label="Instruction for the agent"
          />

          <div className="composer-actions">
            <input ref={fileInputRef} type="file" hidden multiple onChange={onAttachFiles} />
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
  );
}
