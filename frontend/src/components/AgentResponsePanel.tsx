import { useEffect, useRef } from "react";
import { Bot, MessageCircle, Wrench } from "lucide-react";
import type { AgentChatMessage, AgentRunResponse, AgentRunStreamEvent } from "../types";

type AgentResponsePanelProps = {
  isOpen: boolean;
  messages: AgentChatMessage[];
  onToggle: () => void;
  response: AgentRunResponse | null;
  status: AgentRunStreamEvent["status"] | null;
};

function messageLabel(message: AgentChatMessage) {
  if (message.role === "user") return "You";
  if (message.role === "skill") return message.skillName ?? "Skill";
  if (message.role === "assistant") return "Agent";
  return "System";
}

export function AgentResponsePanel({ isOpen, messages, onToggle, response, status }: AgentResponsePanelProps) {
  const hasActivity = messages.length > 0 || Boolean(response);
  const isRunning = status === "running";
  const threadRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    const thread = threadRef.current;
    if (thread) {
      thread.scrollTop = thread.scrollHeight;
    }
  }, [isOpen, messages, status]);

  return (
    <aside className={`agent-response-dock${isOpen ? " open" : ""}`} aria-label="Agent response">
      {isOpen && (
        <section className="agent-response-panel" data-popover role="dialog" aria-label="Agent conversation">
          <div className="agent-response-header">
            <div>
              <span>Base Agent</span>
              <small>{isRunning ? "Working" : response?.status ?? status ?? "Idle"}</small>
            </div>
            <Bot size={18} strokeWidth={2} />
          </div>

          <div className="agent-chat-thread" aria-live="polite" ref={threadRef}>
            {!hasActivity && (
              <div className="agent-chat-empty">
                <MessageCircle size={18} strokeWidth={2} />
                <p>No agent activity yet.</p>
              </div>
            )}
            {messages.map((message) => (
              <article className={`agent-chat-message ${message.role}`} key={message.id}>
                <div className="agent-chat-avatar" aria-hidden="true">
                  {message.role === "skill" ? <Wrench size={14} strokeWidth={2} /> : <MessageCircle size={14} strokeWidth={2} />}
                </div>
                <div className="agent-chat-bubble">
                  <div className="agent-chat-meta">
                    <span>{messageLabel(message)}</span>
                    {message.status && <small>{message.status}</small>}
                  </div>
                  <p>{message.text}</p>
                </div>
              </article>
            ))}
            {isRunning && (
              <article className="agent-chat-message system">
                <div className="agent-chat-avatar" aria-hidden="true">
                  <Bot size={14} strokeWidth={2} />
                </div>
                <div className="agent-chat-bubble typing">
                  <span />
                  <span />
                  <span />
                </div>
              </article>
            )}
          </div>

          {response?.question && response.question.options.length > 0 && (
            <div className="agent-response-options">
              {response.question.options.map((option) => (
                <span key={option.value}>{option.label ?? option.value}</span>
              ))}
            </div>
          )}

          {response && (response.skillRunIds.length > 0 || response.cardIds.length > 0) && (
            <dl className="agent-response-details">
              {response.skillRunIds.length > 0 && (
                <>
                  <dt>Skill runs</dt>
                  <dd>{response.skillRunIds.join(", ")}</dd>
                </>
              )}
              {response.cardIds.length > 0 && (
                <>
                  <dt>Cards</dt>
                  <dd>{response.cardIds.join(", ")}</dd>
                </>
              )}
            </dl>
          )}
        </section>
      )}
      <button
        className={`agent-response-button icon-button${hasActivity ? " active" : ""}`}
        type="button"
        data-popover-trigger
        aria-label="Show agent conversation"
        aria-expanded={isOpen}
        onClick={onToggle}
      >
        <MessageCircle size={18} strokeWidth={2} />
        {isRunning && <span aria-hidden="true" />}
      </button>
    </aside>
  );
}
