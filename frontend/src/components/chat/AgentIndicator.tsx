import { AGENTS, type AgentId } from "@/data/mockChats";
import { useI18n } from "@/hooks/useI18n";
import type { MessageKey } from "@/lib/i18n";

const AGENT_NAME_KEY: Record<AgentId, MessageKey> = {
  crop: "agent.crop.name",
  disease: "agent.disease.name",
  finance: "agent.finance.name",
  general: "agent.general.name",
};

export function AgentIndicator({ agent }: { agent: AgentId }) {
  const { t } = useI18n();
  const info = AGENTS[agent];
  return (
    <div className="mb-2 flex min-w-0 flex-wrap items-center gap-2 text-xs text-muted-foreground">
      <span>{t("chat.analyzedBy")}</span>
      <span className="inline-flex max-w-full items-center gap-1.5 rounded-full border border-border bg-secondary px-2.5 py-1 font-medium text-secondary-foreground">
        <span aria-hidden="true">{info.emoji}</span>
        <span className="truncate">{t(AGENT_NAME_KEY[agent])}</span>
      </span>
    </div>
  );
}
