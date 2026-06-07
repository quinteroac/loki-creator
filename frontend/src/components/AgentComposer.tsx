import { ArrowUp, Check, Cpu, Layers, Paperclip, Search, Sparkles, Square, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { ChangeEvent, FormEvent, KeyboardEvent, RefObject } from "react";
import { formatFileSize } from "../lib/attachments";
import { getCardDisplaySubtitle, getCardDisplayTitle } from "../lib/cardDocuments";
import type {
  AgentAttachment,
  AgentModel,
  AgentQuestion,
  CodexImageResolution,
  ComfyAspectRatio,
  ComfyDuration,
  ComfyImageMode,
  ComfyImageProfile,
  ComfyResolution,
  ComfyTool,
  ComfyVideoMode,
  ComfyVideoProfile,
  ComposerMode,
  GeminiImageModel,
  GeminiImageResolution,
  GeneratedCard,
  GrokImageAspectRatio,
  GrokImageResolution,
  GrokTool,
  GrokVideoAspectRatio,
  GrokVideoDuration,
  GrokVideoResolution,
  SeedanceAspectRatio,
  SeedanceDuration,
} from "../types";

type AgentComposerProps = {
  attachments: AgentAttachment[];
  availableModels: AgentModel[];
  canvasNodes: GeneratedCard[];
  filteredSkills: string[];
  instruction: string;
  isSubmitting: boolean;
  isRunning: boolean;
  composerMode: ComposerMode;
  codexImageResolution: CodexImageResolution;
  comfyAspectRatio: ComfyAspectRatio;
  comfyDuration: ComfyDuration;
  comfyImageMode: ComfyImageMode;
  comfyImageProfile: ComfyImageProfile;
  comfyResolution: ComfyResolution;
  comfyTool: ComfyTool;
  comfyVideoMode: ComfyVideoMode;
  comfyVideoProfile: ComfyVideoProfile;
  geminiImageModel: GeminiImageModel;
  geminiImageResolution: GeminiImageResolution;
  grokImageAspectRatio: GrokImageAspectRatio;
  grokImageResolution: GrokImageResolution;
  grokTool: GrokTool;
  grokVideoAspectRatio: GrokVideoAspectRatio;
  grokVideoDuration: GrokVideoDuration;
  grokVideoResolution: GrokVideoResolution;
  onAttachFiles: (event: ChangeEvent<HTMLInputElement>) => void | Promise<void>;
  onCodexImageResolutionChange: (resolution: CodexImageResolution) => void;
  onComfyAspectRatioChange: (aspectRatio: ComfyAspectRatio) => void;
  onComfyDurationChange: (duration: ComfyDuration) => void;
  onComfyImageModeChange: (mode: ComfyImageMode) => void;
  onComfyImageProfileChange: (profile: ComfyImageProfile) => void;
  onComfyResolutionChange: (resolution: ComfyResolution) => void;
  onComfyToolChange: (tool: ComfyTool) => void;
  onComfyVideoModeChange: (mode: ComfyVideoMode) => void;
  onComfyVideoProfileChange: (profile: ComfyVideoProfile) => void;
  onGeminiImageModelChange: (model: GeminiImageModel) => void;
  onGeminiImageResolutionChange: (resolution: GeminiImageResolution) => void;
  onCreateAgent: () => void;
  onInstructionChange: (instruction: string) => void;
  onInstructionKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void;
  onQuestionOption: (answer: string) => void;
  onRemoveAttachment: (attachmentId: string) => void;
  onGrokImageAspectRatioChange: (aspectRatio: GrokImageAspectRatio) => void;
  onGrokImageResolutionChange: (resolution: GrokImageResolution) => void;
  onGrokToolChange: (tool: GrokTool) => void;
  onGrokVideoAspectRatioChange: (aspectRatio: GrokVideoAspectRatio) => void;
  onGrokVideoDurationChange: (duration: GrokVideoDuration) => void;
  onGrokVideoResolutionChange: (resolution: GrokVideoResolution) => void;
  onSelectModel: (model: string) => void;
  onSeedanceAspectRatioChange: (aspectRatio: SeedanceAspectRatio) => void;
  onSeedanceDurationChange: (duration: SeedanceDuration) => void;
  onSetComposerMode: (mode: ComposerMode) => void;
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
  codexImageResolution,
  comfyAspectRatio,
  comfyDuration,
  comfyImageMode,
  comfyImageProfile,
  comfyResolution,
  comfyTool,
  comfyVideoMode,
  comfyVideoProfile,
  geminiImageModel,
  geminiImageResolution,
  grokImageAspectRatio,
  grokImageResolution,
  grokTool,
  grokVideoAspectRatio,
  grokVideoDuration,
  grokVideoResolution,
  onAttachFiles,
  onCodexImageResolutionChange,
  onComfyAspectRatioChange,
  onComfyDurationChange,
  onComfyImageModeChange,
  onComfyImageProfileChange,
  onComfyResolutionChange,
  onComfyToolChange,
  onComfyVideoModeChange,
  onComfyVideoProfileChange,
  onGeminiImageModelChange,
  onGeminiImageResolutionChange,
  onCreateAgent,
  onInstructionChange,
  onInstructionKeyDown,
  onQuestionOption,
  onRemoveAttachment,
  onGrokImageAspectRatioChange,
  onGrokImageResolutionChange,
  onGrokToolChange,
  onGrokVideoAspectRatioChange,
  onGrokVideoDurationChange,
  onGrokVideoResolutionChange,
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
            <label className="composer-select-chip mode-select-chip">
              <span>Mode</span>
              <select
                value={composerMode}
                onChange={(event) => {
                  onSetComposerMode(event.target.value as ComposerMode);
                  setOpenMenu(null);
                }}
                aria-label="Composer mode"
              >
                <option value="agent">Agent</option>
                <option value="seedance">Seedance</option>
                <option value="grok">Grok</option>
                <option value="codex">Codex</option>
                <option value="gemini">Gemini</option>
                <option value="comfy">Comfy</option>
              </select>
            </label>
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
            {composerMode === "grok" && (
              <>
                <label className="composer-select-chip">
                  <span>Tool</span>
                  <select
                    value={grokTool}
                    onChange={(event) => onGrokToolChange(event.target.value as GrokTool)}
                    aria-label="Grok tool"
                  >
                    <option value="image">Grok Image</option>
                    <option value="video">Grok Video</option>
                  </select>
                </label>
                <label className="composer-select-chip">
                  <span>Frame</span>
                  <select
                    value={grokTool === "image" ? grokImageAspectRatio : grokVideoAspectRatio}
                    onChange={(event) => {
                      if (grokTool === "image") {
                        onGrokImageAspectRatioChange(event.target.value as GrokImageAspectRatio);
                      } else {
                        onGrokVideoAspectRatioChange(event.target.value as GrokVideoAspectRatio);
                      }
                    }}
                    aria-label="Grok aspect ratio"
                  >
                    <option value="1:1">1:1</option>
                    <option value="4:3">4:3</option>
                    <option value="16:9">16:9</option>
                    <option value="9:16">9:16</option>
                  </select>
                </label>
                <label className="composer-select-chip">
                  <span>Res</span>
                  <select
                    value={grokTool === "image" ? grokImageResolution : grokVideoResolution}
                    onChange={(event) => {
                      if (grokTool === "image") {
                        onGrokImageResolutionChange(event.target.value as GrokImageResolution);
                      } else {
                        onGrokVideoResolutionChange(event.target.value as GrokVideoResolution);
                      }
                    }}
                    aria-label="Grok resolution"
                  >
                    {grokTool === "image" ? (
                      <>
                        <option value="1k">1K</option>
                        <option value="2k">2K</option>
                      </>
                    ) : (
                      <>
                        <option value="720p">720p</option>
                        <option value="480p">480p</option>
                      </>
                    )}
                  </select>
                </label>
                {grokTool === "video" && (
                  <label className="composer-select-chip">
                    <span>Duration</span>
                    <select
                      value={grokVideoDuration}
                      onChange={(event) => onGrokVideoDurationChange(Number(event.target.value) as GrokVideoDuration)}
                      aria-label="Grok video duration"
                    >
                      <option value={5}>5s</option>
                      <option value={10}>10s</option>
                      <option value={15}>15s</option>
                    </select>
                  </label>
                )}
              </>
            )}
            {composerMode === "codex" && (
              <label className="composer-select-chip">
                <span>Res</span>
                <select
                  value={codexImageResolution}
                  onChange={(event) => onCodexImageResolutionChange(event.target.value as CodexImageResolution)}
                  aria-label="Codex image resolution"
                >
                  <option value="1024x1024">1024 square</option>
                  <option value="1536x1024">1536 landscape</option>
                  <option value="1024x1536">1536 portrait</option>
                  <option value="2048x2048">2K square</option>
                  <option value="2048x1152">2K landscape</option>
                  <option value="3840x2160">4K landscape</option>
                  <option value="2160x3840">4K portrait</option>
                  <option value="auto">Auto</option>
                </select>
              </label>
            )}
            {composerMode === "gemini" && (
              <>
                <label className="composer-select-chip">
                  <span>Model</span>
                  <select
                    value={geminiImageModel}
                    onChange={(event) => onGeminiImageModelChange(event.target.value as GeminiImageModel)}
                    aria-label="Gemini image model"
                  >
                    <option value="Gemini 3.5 Flash (Medium)">3.5 Flash M</option>
                    <option value="Gemini 3.5 Flash (High)">3.5 Flash H</option>
                    <option value="Gemini 3.5 Flash (Low)">3.5 Flash L</option>
                    <option value="Gemini 3.1 Pro (Low)">3.1 Pro L</option>
                    <option value="Gemini 3.1 Pro (High)">3.1 Pro H</option>
                    <option value="Claude Sonnet 4.6 (Thinking)">Sonnet 4.6</option>
                    <option value="Claude Opus 4.6 (Thinking)">Opus 4.6</option>
                    <option value="GPT-OSS 120B (Medium)">GPT-OSS 120B</option>
                  </select>
                </label>
                <label className="composer-select-chip">
                  <span>Res</span>
                  <select
                    value={geminiImageResolution}
                    onChange={(event) => onGeminiImageResolutionChange(event.target.value as GeminiImageResolution)}
                    aria-label="Gemini image resolution"
                  >
                    <option value="1024x1024">1024 square</option>
                    <option value="1536x1024">1536 landscape</option>
                    <option value="1024x1536">1536 portrait</option>
                    <option value="2048x2048">2K square</option>
                    <option value="2048x1152">2K landscape</option>
                    <option value="3840x2160">4K landscape</option>
                    <option value="2160x3840">4K portrait</option>
                    <option value="auto">Auto</option>
                  </select>
                </label>
              </>
            )}
            {composerMode === "comfy" && (
              <>
                <label className="composer-select-chip">
                  <span>Tool</span>
                  <select
                    value={comfyTool}
                    onChange={(event) => onComfyToolChange(event.target.value as ComfyTool)}
                    aria-label="Comfy tool"
                  >
                    <option value="image">Image</option>
                    <option value="video">Video</option>
                  </select>
                </label>
                {comfyTool === "image" ? (
                  <>
                    <label className="composer-select-chip">
                      <span>Mode</span>
                      <select
                        value={comfyImageMode}
                        onChange={(event) => onComfyImageModeChange(event.target.value as ComfyImageMode)}
                        aria-label="Comfy image mode"
                      >
                        <option value="generate">Generate</option>
                        <option value="edit">Edit</option>
                        <option value="upscale">Upscale</option>
                      </select>
                    </label>
                    {comfyImageMode !== "upscale" && (
                      <label className="composer-select-chip">
                        <span>Profile</span>
                        <select
                          value={comfyImageProfile}
                          onChange={(event) => onComfyImageProfileChange(event.target.value as ComfyImageProfile)}
                          aria-label="Comfy image profile"
                        >
                          <option value="anima-base">Anima</option>
                          <option value="qwen-edit2511">Qwen Edit</option>
                          <option value="flux-klein-9b-snofs">Flux Klein</option>
                        </select>
                      </label>
                    )}
                  </>
                ) : (
                  <>
                    <label className="composer-select-chip">
                      <span>Profile</span>
                      <select
                        value={comfyVideoProfile}
                        onChange={(event) => onComfyVideoProfileChange(event.target.value as ComfyVideoProfile)}
                        aria-label="Comfy video profile"
                      >
                        <option value="ltx23-10eros">LTX 10Eros</option>
                        <option value="ltx23-dasiwa-golden-lace-v3">LTX Dasiwa</option>
                        <option value="wan22-i2v">WAN 2.2</option>
                        <option value="wan22-dasiwa-tastysin-i2v">WAN Tastysin</option>
                        <option value="wan22-dasiwa-boundbite-i2v">WAN Boundbite</option>
                      </select>
                    </label>
                    <label className="composer-select-chip">
                      <span>Mode</span>
                      <select
                        value={comfyVideoMode}
                        onChange={(event) => onComfyVideoModeChange(event.target.value as ComfyVideoMode)}
                        aria-label="Comfy video mode"
                      >
                        <option value="t2v">Text</option>
                        <option value="i2v">Image</option>
                        <option value="flf2v">First/Last</option>
                        <option value="wan22-i2v">WAN Image</option>
                        <option value="wan22-flf2v">WAN First/Last</option>
                      </select>
                    </label>
                  </>
                )}
                <label className="composer-select-chip">
                  <span>Frame</span>
                  <select
                    value={comfyAspectRatio}
                    onChange={(event) => onComfyAspectRatioChange(event.target.value as ComfyAspectRatio)}
                    aria-label="Comfy aspect ratio"
                  >
                    <option value="1:1">1:1</option>
                    <option value="4:3">4:3</option>
                    <option value="16:9">16:9</option>
                    <option value="9:16">9:16</option>
                  </select>
                </label>
                {comfyTool === "video" && (
                  <>
                    <label className="composer-select-chip">
                      <span>Res</span>
                      <select
                        value={comfyResolution}
                        onChange={(event) => onComfyResolutionChange(event.target.value as ComfyResolution)}
                        aria-label="Comfy video resolution"
                      >
                        <option value="360p">360p</option>
                        <option value="480p">480p</option>
                        <option value="720p">720p</option>
                        <option value="1080p">1080p</option>
                      </select>
                    </label>
                    <label className="composer-select-chip">
                      <span>Duration</span>
                      <select
                        value={comfyDuration}
                        onChange={(event) => onComfyDurationChange(Number(event.target.value) as ComfyDuration)}
                        aria-label="Comfy video duration"
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
              </>
            )}
            {composerMode === "agent" && (
              <>
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
              </>
            )}
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
