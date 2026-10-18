import { AGENTS, type AgentId } from "@/data/mockChats";

export function AgentIndicator({ agent }: { agent: AgentId }) {
  const info = AGENTS[agent];
  return (
    <div className="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
      <span>Analyzed by</span>
      <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-secondary px-2.5 py-1 font-medium text-secondary-foreground">
        <span aria-hidden="true">{info.emoji}</span>
        {info.name}
      </span>
    </div>
  );
}
