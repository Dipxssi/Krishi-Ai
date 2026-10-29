import { AGENTS, type AgentId } from "@/data/mockChats";

export function AgentIndicator({ agent }: { agent: AgentId }) {
  const info = AGENTS[agent];
  return (
    <div className="mb-2 flex min-w-0 flex-wrap items-center gap-2 text-xs text-muted-foreground">
      <span>Analyzed by</span>
      <span className="inline-flex max-w-full items-center gap-1.5 rounded-full border border-border bg-secondary px-2.5 py-1 font-medium text-secondary-foreground">
        <span aria-hidden="true">{info.emoji}</span>
        <span className="truncate">{info.name}</span>
      </span>
    </div>
  );
}
