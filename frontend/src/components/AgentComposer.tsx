import { ArrowUp, Bot, Check, Cpu, Film, Layers, Paperclip, Search, Sparkles, Square, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { ChangeEvent, FormEvent, KeyboardEvent, RefObject } from "react";
import { formatFileSize } from "../lib/attachments";
import { getCardDisplaySubtitle, getCardDisplayTitle } from "../lib/cardDocuments";
import type { AgentAttachment, AgentModel, AgentQuestion, GeneratedCard, SeedanceAspectRatio, SeedanceDuration } from "../types";

type AgentComposerProps = {
  attachments: AgentAttachment[];
  availableModels: AgentModel[];
  canvasNodes: GeneratedCard[];
  filteredSkills: string[];
  instruction: string;
  isSubmitting: boolean;
  isRunning: boolean;
  composerMode: "agent" | "seedance";
  onAttachFiles: (event: ChangeEvent<HTMLInputElement>) => void | Promise<void>;
  onCreateAgent: () => void;
  onInstructionChange: (instruction: string) => void;
  onInstructionKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void;
  onQuestionOption: (answer: string) => void;
  onRemoveAttachment: (attachmentId: string) => void;
  onSelectModel: (model: string) => void;
  onSeedanceAspectRatioChange: (aspectRatio: SeedanceAspectRatio) => void;
  onSeedanceDurationChange: (duration: SeedanceDuration) => void;
  onSetComposerMode: (mode: "agent" | "seedance") => void;
  onStop: () => void | Promise<void>;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onToggleCard: (cardId: string) => void;
  onToggleSkill: (skill: string) => void;
  openMenu: string | null;
  selectedCards: string[];
  selectedCardCount: number;
  selectedCardLabel: string;
  seedanceAspectRatio: SeedanceAspectRatio;
  seedanceDuration: SeedanceDuration;
  selectedModel: string;
  selectedSkillCount: number;
  selectedSkills: string[];
  setOpenMenu: (openMenu: string | null) => void;
  setSkillSearch: (skillSearch: string) => void;
  status: string;
  pendingQuestion: AgentQuestion | null;
  skillButtonLabel: string;
  skillSearch: string;
  fileInputRef: RefObject<HTMLInputElement | null>;
};

export function AgentComposer({
  attachments,
  availableModels,
  canvasNodes,
  filteredSkills,
  instruction,
  isSubmitting,
  isRunning,
  composerMode,
  onAttachFiles,
  onCreateAgent,
  onInstructionChange,
  onInstructionKeyDown,
  onQuestionOption,
  onRemoveAttachment,
  onSelectModel,
  onSeedanceAspectRatioChange,
  onSeedanceDurationChange,
  onSetComposerMode,
  onStop,
  onSubmit,
  onToggleCard,
  onToggleSkill,
  openMenu,
  selectedCards,
  selectedCardCount,
  selectedCardLabel,
  seedanceAspectRatio,
  seedanceDuration,
  selectedModel,
  selectedSkillCount,
  selectedSkills,
  setOpenMenu,
  setSkillSearch,
  status,
  pendingQuestion,
  skillButtonLabel,
  skillSearch,
  fileInputRef,
}: AgentComposerProps) {
  const [modelSearch, setModelSearch] = useState("");
  const [isPromptFocused, setIsPromptFocused] = useState(false);
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

      {openMenu === "skill-picker" && (
        <div className="popover picker-popover" data-popover aria-label="Select skills">
          <label className="picker-search">
            <Search size={14} strokeWidth={2} />
            <input
              type="search"
              value={skillSearch}
              onChange={(event) => setSkillSearch(event.target.value)}
              placeholder="Search skills"
              aria-label="Search skills"
              autoFocus
            />
          </label>
          <div className="picker-list">
            {filteredSkills.map((skill) => {
              const isSelected = selectedSkills.includes(skill);

              return (
                <button
                  className={`picker-option ${isSelected ? "selected" : ""}`}
                  key={skill}
                  type="button"
                  onClick={() => onToggleSkill(skill)}
                >
                  <span>{skill}</span>
                  {isSelected && <Check size={14} strokeWidth={2} />}
                </button>
              );
            })}
            {filteredSkills.length === 0 && (
              <p className="picker-empty">{skillSearch.trim() ? "No matching skills" : "No skills available"}</p>
            )}
          </div>
        </div>
      )}

      {openMenu === "model-picker" && (
        <div className="popover model-popover" data-popover aria-label="Select model">
          <label className="picker-search">
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
          <div className="picker-list">
            {filteredModels.map((model) => {
              const isSelected = selectedModel === model.label;

              return (
                <button
                  className={`picker-option ${isSelected ? "selected" : ""}`}
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
              <p className="picker-empty">{modelSearch.trim() ? "No matching models" : "No models available"}</p>
            )}
          </div>
        </div>
      )}

      {openMenu === "selected-cards" && (
        <div className="popover cards-popover" data-popover aria-label="Selected cards">
          <div className="picker-list">
            {canvasNodes.map((node) => {
              const isSelected = selectedCards.includes(node.id);
              const title = getCardDisplayTitle(node);
              const subtitle = getCardDisplaySubtitle(node);

              return (
                <button
                  className={`picker-option card-option ${isSelected ? "selected" : ""}`}
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
            {canvasNodes.length === 0 && <p className="picker-empty">No cards in canvas</p>}
          </div>
        </div>
      )}

      {pendingQuestion && (
        <div className="agent-question" aria-live="polite">
          <p>{pendingQuestion.text}</p>
          {pendingQuestion.options.length > 0 && (
            <div className="agent-question-options">
              {pendingQuestion.options.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => onQuestionOption(option.value)}
                  title={option.description ?? undefined}
                >
                  {option.label ?? option.value}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      <form className={`composer ${isPromptFocused ? "composer-prompt-focused" : ""}`} onSubmit={onSubmit}>
        <div className="composer-main">
          {attachments.length > 0 && (
            <div className="attachment-tray" aria-label="Attached files">
              {attachments.map((attachment) => (
                <span className={`attachment-chip ${attachment.omitted ? "omitted" : ""}`} key={attachment.id}>
                  <Paperclip size={13} strokeWidth={2} />
                  <span className="attachment-chip-label" title={attachment.name}>
                    {attachment.name}
                  </span>
                  <small>{attachment.omitted ? attachment.reason : formatFileSize(attachment.size)}</small>
                  <button
                    type="button"
                    aria-label={`Remove ${attachment.name}`}
                    title="Remove attachment"
                    onClick={() => onRemoveAttachment(attachment.id)}
                  >
                    <X size={12} strokeWidth={2.2} />
                  </button>
                </span>
              ))}
            </div>
          )}

          <textarea
            className="composer-prompt"
            name="instruction"
            rows={1}
            value={instruction}
            onChange={(event) => onInstructionChange(event.target.value)}
            onFocus={() => setIsPromptFocused(true)}
            onBlur={() => setIsPromptFocused(false)}
            onKeyDown={onInstructionKeyDown}
            placeholder={pendingQuestion ? "Answer the agent..." : "Write to imagine"}
            aria-label={pendingQuestion ? "Answer for the agent" : "Instruction for the agent"}
          />

          <div className="composer-actions">
            <input ref={fileInputRef} type="file" hidden multiple onChange={onAttachFiles} />
            <button
              className={`chat-chip agent-chip ${composerMode === "agent" ? "active" : ""}`}
              type="button"
              data-popover-trigger
              aria-expanded={openMenu === "agents"}
              onClick={() => {
                onSetComposerMode("agent");
                setOpenMenu(openMenu === "agents" ? null : "agents");
              }}
            >
              <Bot size={14} strokeWidth={2} />
              <span>Agent</span>
            </button>
            <button
              className={`chat-chip seedance-chip ${composerMode === "seedance" ? "active" : ""}`}
              type="button"
              onClick={() => {
                onSetComposerMode(composerMode === "seedance" ? "agent" : "seedance");
                setOpenMenu(null);
              }}
            >
              <Film size={14} strokeWidth={2} />
              <span>Seedance</span>
            </button>
            {composerMode === "seedance" && (
              <>
                <label className="composer-select-chip">
                  <span>Frame</span>
                  <select
                    value={seedanceAspectRatio}
                    onChange={(event) => onSeedanceAspectRatioChange(event.target.value as SeedanceAspectRatio)}
                    aria-label="Seedance aspect ratio"
                  >
                    <option value="16:9">16:9</option>
                    <option value="9:16">9:16</option>
                  </select>
                </label>
                <label className="composer-select-chip">
                  <span>Duration</span>
                  <select
                    value={seedanceDuration}
                    onChange={(event) => onSeedanceDurationChange(Number(event.target.value) as SeedanceDuration)}
                    aria-label="Seedance duration"
                  >
                    <option value={4}>4s</option>
                    <option value={5}>5s</option>
                    <option value={7}>7s</option>
                    <option value={10}>10s</option>
                    <option value={15}>15s</option>
                  </select>
                </label>
              </>
            )}
            <button
              className="chat-chip model-chip"
              type="button"
              data-popover-trigger
              aria-expanded={openMenu === "model-picker"}
              onClick={() => setOpenMenu(openMenu === "model-picker" ? null : "model-picker")}
            >
              <Cpu size={14} strokeWidth={2} />
              <span>{selectedModel}</span>
            </button>
            <button
              className="chat-chip skill-chip"
              type="button"
              data-popover-trigger
              aria-expanded={openMenu === "skill-picker"}
              onClick={() => setOpenMenu(openMenu === "skill-picker" ? null : "skill-picker")}
            >
              <Sparkles size={14} strokeWidth={2} />
              <span>{skillButtonLabel}</span>
              {selectedSkillCount > 1 && <small>{selectedSkillCount}</small>}
            </button>
            <button
              className="chat-chip selected-cards-chip"
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
              className="chat-chip attach-chip"
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

        <button
          className={`send-orb ${isRunning ? "stop-orb" : ""}`}
          type={isRunning ? "button" : "submit"}
          aria-label={isRunning ? "Stop agent run" : "Send instruction"}
          title={isRunning ? "Stop" : "Send"}
          onClick={isRunning ? onStop : undefined}
          disabled={!isRunning && isSubmitting}
        >
          {isRunning ? <Square size={17} fill="currentColor" strokeWidth={2.2} /> : <ArrowUp size={20} strokeWidth={2} />}
        </button>
      </form>
      <p className="composer-status" aria-live="polite">
        {status}
      </p>
    </section>
  );
}
