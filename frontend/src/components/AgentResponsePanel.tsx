import { MessageCircle } from "lucide-react";
import type { AgentRunResponse } from "../types";

type AgentResponsePanelProps = {
  isOpen: boolean;
  onToggle: () => void;
  response: AgentRunResponse | null;
};

export function AgentResponsePanel({ isOpen, onToggle, response }: AgentResponsePanelProps) {
  if (!response) {
    return null;
  }

  return (
    <aside className="agent-response-dock" aria-label="Agent response">
      {isOpen && (
        <div className="agent-response-popover" data-popover role="dialog" aria-label="Latest agent response">
          <div className="agent-response-header">
            <span>{response.agentId === "tool-builder" ? "Tool Builder" : "Base Agent"}</span>
            <small>{response.status}</small>
          </div>
          <p>{response.responseText}</p>
          {(response.toolJobIds.length > 0 || response.cardIds.length > 0) && (
            <dl>
              {response.toolJobIds.length > 0 && (
                <>
                  <dt>Jobs</dt>
                  <dd>{response.toolJobIds.join(", ")}</dd>
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
        </div>
      )}
      <button
        className="agent-response-button icon-button"
        type="button"
        data-popover-trigger
        aria-label="Show agent response"
        aria-expanded={isOpen}
        onClick={onToggle}
      >
        <MessageCircle size={18} strokeWidth={2} />
      </button>
    </aside>
  );
}
