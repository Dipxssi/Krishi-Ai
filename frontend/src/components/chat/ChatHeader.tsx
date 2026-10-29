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
}

export function ChatHeader({
  onOpenSidebar,
  onNewChat,
  onOpenSettings,
  connectionStatus = "checking",
  pendingCount = 0,
}: ChatHeaderProps) {
  const { t } = useI18n();

  const connectionLabel = () => {
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
    if (connectionStatus === "online") return "bg-primary";
    if (connectionStatus === "sending") return "bg-amber-500 animate-pulse";
    if (connectionStatus === "checking") return "bg-muted-foreground/50";
    return "bg-destructive";
  };

  return (
    <header className="flex items-center gap-2 border-b border-border bg-background/85 px-3 py-2.5 backdrop-blur sm:gap-3 sm:px-6 sm:py-3">
      <button
        type="button"
        onClick={onOpenSidebar}
        aria-label={t("chat.openSidebar")}
        className="grid size-9 place-items-center rounded-xl border border-border text-foreground hover:bg-muted sm:size-10 lg:hidden"
      >
        <Menu className="size-5" />
      </button>

      <span className="grid size-8 shrink-0 place-items-center rounded-2xl bg-gradient-leaf shadow-soft sm:size-9">
        <Sprout className="size-4 text-primary-foreground sm:size-5" aria-hidden="true" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold text-foreground">Krishi AI</p>
        <p className="flex min-w-0 items-center gap-1.5 text-xs text-muted-foreground">
          <span
            aria-hidden="true"
            className={cn("size-1.5 shrink-0 rounded-full", connectionDotClass())}
          />
          <span className="truncate">{connectionLabel()}</span>
        </p>
      </div>

      <div className="ml-auto flex shrink-0 items-center gap-0.5 sm:gap-1">
        <LanguageSwitcher className="hidden sm:inline-flex" />
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
