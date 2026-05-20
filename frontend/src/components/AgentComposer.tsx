import { ArrowUp, Bot, Check, Cpu, Layers, Paperclip, Search, Wrench } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { ChangeEvent, FormEvent, KeyboardEvent, RefObject } from "react";
import { getCardDisplaySubtitle, getCardDisplayTitle } from "../lib/cardDocuments";
import type { AgentModel, GeneratedCard } from "../types";

type AgentComposerProps = {
  availableModels: AgentModel[];
  canvasNodes: GeneratedCard[];
  filteredTools: string[];
  instruction: string;
  onAttachFiles: (event: ChangeEvent<HTMLInputElement>) => void;
  onCreateAgent: () => void;
  onInstructionChange: (instruction: string) => void;
  onInstructionKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void;
  onSelectModel: (model: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onToggleCard: (cardId: string) => void;
  onToggleTool: (tool: string) => void;
  openMenu: string | null;
  selectedCards: string[];
  selectedCardCount: number;
  selectedCardLabel: string;
  selectedModel: string;
  selectedToolCount: number;
  selectedTools: string[];
  setOpenMenu: (openMenu: string | null) => void;
  setToolSearch: (toolSearch: string) => void;
  status: string;
  toolButtonLabel: string;
  toolSearch: string;
  fileInputRef: RefObject<HTMLInputElement | null>;
};

export function AgentComposer({
  availableModels,
  canvasNodes,
  filteredTools,
  instruction,
  onAttachFiles,
  onCreateAgent,
  onInstructionChange,
  onInstructionKeyDown,
  onSelectModel,
  onSubmit,
  onToggleCard,
  onToggleTool,
  openMenu,
  selectedCards,
  selectedCardCount,
  selectedCardLabel,
  selectedModel,
  selectedToolCount,
  selectedTools,
  setOpenMenu,
  setToolSearch,
  status,
  toolButtonLabel,
  toolSearch,
  fileInputRef,
}: AgentComposerProps) {
  const [modelSearch, setModelSearch] = useState("");
  const filteredModels = useMemo(() => {
    const query = modelSearch.trim().toLowerCase();

    if (!query) return availableModels;

    return availableModels.filter((model) =>
      [model.label, model.name, model.provider, model.id].some((value) => value.toLowerCase().includes(query)),
    );
  }, [availableModels, modelSearch]);

  useEffect(() => {
    if (openMenu !== "model-picker") {
      setModelSearch("");
    }
  }, [openMenu]);

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
            {filteredTools.length === 0 && (
              <p className="tool-empty">{toolSearch.trim() ? "No matching tools" : "No tools available"}</p>
            )}
          </div>
        </div>
      )}

      {openMenu === "model-picker" && (
        <div className="popover model-popover" data-popover aria-label="Select model">
          <label className="tool-search">
            <Search size={14} strokeWidth={2} />
            <input
              type="search"
              value={modelSearch}
              onChange={(event) => setModelSearch(event.target.value)}
              placeholder="Search models"
              aria-label="Search models"
              autoFocus
            />
          </label>
          <div className="tool-list">
            {filteredModels.map((model) => {
              const isSelected = selectedModel === model.label;

              return (
                <button
                  className={`tool-option ${isSelected ? "selected" : ""}`}
                  key={`${model.provider}:${model.id}`}
                  type="button"
                  onClick={() => onSelectModel(model.label)}
                >
                  <span>{model.label}</span>
                  {isSelected && <Check size={14} strokeWidth={2} />}
                </button>
              );
            })}
            {filteredModels.length === 0 && (
              <p className="tool-empty">{modelSearch.trim() ? "No matching models" : "No models available"}</p>
            )}
          </div>
        </div>
      )}

      {openMenu === "selected-cards" && (
        <div className="popover cards-popover" data-popover aria-label="Selected cards">
          <div className="tool-list">
            {canvasNodes.map((node) => {
              const isSelected = selectedCards.includes(node.id);
              const title = getCardDisplayTitle(node);
              const subtitle = getCardDisplaySubtitle(node);

              return (
                <button
                  className={`tool-option card-option ${isSelected ? "selected" : ""}`}
                  key={node.id}
                  type="button"
                  onClick={() => onToggleCard(node.id)}
                >
                  <span>
                    <strong>{title}</strong>
                    {subtitle && <small>{subtitle}</small>}
                  </span>
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
              aria-expanded={openMenu === "model-picker"}
              onClick={() => setOpenMenu(openMenu === "model-picker" ? null : "model-picker")}
            >
              <Cpu size={14} strokeWidth={2} />
              <span>{selectedModel}</span>
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
