import { Link } from "react-router-dom";
import { Menu, MessageSquarePlus, Radio, Settings, Sprout } from "lucide-react";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import type { ConnectionUiState } from "@/hooks/useApiConnection";
import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";

interface ChatHeaderProps {
  onOpenSidebar: () => void;
  onNewChat: () => void;
  onOpenSettings: () => void;
  connectionStatus?: ConnectionUiState;
  pendingCount?: number;
  /** Phase 1 Continue-as / no live JWT — always show Offline badge. */
  offlineSession?: boolean;
}

export function ChatHeader({
  onOpenSidebar,
  onNewChat,
  onOpenSettings,
  connectionStatus = "checking",
  pendingCount = 0,
  offlineSession = false,
}: ChatHeaderProps) {
  const { t } = useI18n();
  const showOffline = offlineSession || connectionStatus === "offline";

  const connectionLabel = () => {
    if (offlineSession && connectionStatus !== "sending") {
      return pendingCount > 0
        ? t("chat.conn.offlineN", { count: pendingCount })
        : t("chat.conn.offlineBadge");
    }
    if (connectionStatus === "sending") {
      return pendingCount > 0 ? t("chat.conn.sendingN", { count: pendingCount }) : t("chat.conn.sending");
    }
    if (connectionStatus === "offline") {
      return pendingCount > 0
        ? t("chat.conn.offlineN", { count: pendingCount })
        : t("chat.conn.offline");
    }
    if (connectionStatus === "checking") return t("chat.conn.checking");
    return pendingCount > 0 ? t("chat.conn.onlineN", { count: pendingCount }) : t("chat.conn.online");
  };

  const connectionDotClass = () => {
    if (showOffline && connectionStatus !== "sending") return "bg-amber-600";
    if (connectionStatus === "online") return "bg-primary";
    if (connectionStatus === "sending") return "bg-amber-500 animate-pulse";
    if (connectionStatus === "checking") return "bg-muted-foreground/50";
    return "bg-destructive";
  };

  const connectionChipClass = () => {
    if (showOffline && connectionStatus !== "sending") {
      return "border-amber-500/40 bg-amber-500/15 text-foreground";
    }
    if (connectionStatus === "online") return "border-primary/25 bg-primary/10 text-foreground";
    if (connectionStatus === "sending") return "border-amber-500/30 bg-amber-500/10 text-foreground";
    if (connectionStatus === "checking") return "border-border bg-muted/50 text-muted-foreground";
    return "border-destructive/30 bg-destructive/10 text-foreground";
  };

  return (
    <header className="flex min-w-0 items-center gap-2 overflow-x-hidden border-b border-border bg-background/90 px-3 py-2.5 backdrop-blur sm:gap-3 sm:px-5 sm:py-3">
      <button
        type="button"
        onClick={onOpenSidebar}
        aria-label={t("chat.openSidebar")}
        className="grid size-9 shrink-0 place-items-center rounded-xl border border-border text-foreground hover:bg-muted sm:size-10 lg:hidden"
      >
        <Menu className="size-5" />
      </button>

      <span className="grid size-8 shrink-0 place-items-center rounded-2xl bg-gradient-leaf shadow-soft sm:size-9">
        <Sprout className="size-4 text-primary-foreground sm:size-5" aria-hidden="true" />
      </span>

      <div className="min-w-0 flex-1 overflow-hidden">
        <p className="truncate text-sm font-semibold text-foreground sm:text-base">Krishi AI</p>
        <div
          className={cn(
            "mt-0.5 inline-flex max-w-full items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium sm:text-xs",
            connectionChipClass(),
          )}
          title={connectionLabel()}
        >
          <span
            aria-hidden="true"
            className={cn("size-1.5 shrink-0 rounded-full", connectionDotClass())}
          />
          <span className="min-w-0 truncate">{connectionLabel()}</span>
        </div>
      </div>

      <div className="ml-auto flex shrink-0 items-center gap-0.5 sm:gap-1">
        <LanguageSwitcher className="hidden max-w-[7.5rem] sm:inline-flex" />
        <Link
          to="/field-relay"
          aria-label={t("chat.fieldRelay")}
          title={t("chat.fieldRelay")}
          className="grid size-9 place-items-center rounded-xl text-muted-foreground hover:bg-muted hover:text-foreground sm:size-10"
        >
          <Radio className="size-5" />
        </Link>
        <button
          type="button"
          onClick={onNewChat}
          aria-label={t("chat.newAria")}
          title={t("chat.new")}
          className="grid size-9 place-items-center rounded-xl text-muted-foreground hover:bg-muted hover:text-foreground sm:size-10"
        >
          <MessageSquarePlus className="size-5" />
        </button>
        <button
          type="button"
          onClick={onOpenSettings}
          aria-label={t("chat.settingsAria")}
          title={t("chat.settings")}
          className="grid size-9 place-items-center rounded-xl text-muted-foreground hover:bg-muted hover:text-foreground sm:size-10"
        >
          <Settings className="size-5" />
        </button>
      </div>
    </header>
  );
}
