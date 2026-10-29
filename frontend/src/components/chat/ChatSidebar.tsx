import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  BookOpen,
  Brain,
  LogOut,
  MessageSquare,
  MoreVertical,
  Plus,
  Search,
  Settings,
  Trash2,
} from "lucide-react";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { Logo } from "@/components/Logo";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { Conversation } from "@/data/mockChats";
import { initialsFromName, useAuthUser } from "@/hooks/useAuthUser";
import { useI18n } from "@/hooks/useI18n";
import { clearAuthSession } from "@/lib/authSession";
import { loadProfileMemory } from "@/lib/conversationMemory";
import { ensureOfflinePackSynced, getOfflinePackMeta, type OfflinePackMeta } from "@/lib/offlinePack";
import { cn } from "@/lib/utils";

interface ChatSidebarProps {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNewChat: () => void;
  onDelete: (id: string) => void;
  onClear: (id: string) => void;
  onOpenSettings: () => void;
}

export function ChatSidebar({
  conversations,
  activeId,
  onSelect,
  onNewChat,
  onDelete,
  onClear,
  onOpenSettings,
}: ChatSidebarProps) {
  const [query, setQuery] = useState("");
  const { t } = useI18n();
  const authUser = useAuthUser();
  const displayName = authUser?.name?.trim() || authUser?.email?.split("@")[0] || "Farmer";
  const displayEmail = authUser?.email || t("chat.notSignedIn");
  const initials = initialsFromName(displayName);
  const [packMeta, setPackMeta] = useState<OfflinePackMeta | null>(() => getOfflinePackMeta());
  const [memoryPreview, setMemoryPreview] = useState("");
  const filtered = conversations.filter((c) =>
    (c.title + " " + c.messages.map((m) => m.content).join(" "))
      .toLowerCase()
      .includes(query.trim().toLowerCase()),
  );

  useEffect(() => {
    setMemoryPreview(loadProfileMemory(authUser?.farmer_id));
    setPackMeta(getOfflinePackMeta());
    void ensureOfflinePackSynced().then(() => setPackMeta(getOfflinePackMeta()));
  }, [authUser?.farmer_id]);

  useEffect(() => {
    setMemoryPreview(loadProfileMemory(authUser?.farmer_id));
  }, [authUser?.farmer_id, conversations]);

  return (
    <div className="flex h-full min-w-0 flex-col overflow-x-hidden bg-sidebar text-sidebar-foreground">
      <div className="min-w-0 shrink-0 p-4">
        <div className="flex min-w-0 items-start justify-between gap-2">
          <div className="min-w-0 flex-1 overflow-hidden">
            <Logo tone="onDark" />
          </div>
          <LanguageSwitcher tone="dark" className="shrink-0" />
        </div>

        <button
          type="button"
          onClick={onNewChat}
          className="mt-4 flex w-full min-w-0 items-center justify-center gap-2 rounded-2xl bg-gradient-leaf px-4 py-3 text-sm font-semibold text-primary-foreground shadow-soft transition-opacity hover:opacity-95 focus-visible:ring-2 focus-visible:ring-sidebar-ring focus-visible:outline-none"
        >
          <Plus className="size-4 shrink-0" />
          <span className="truncate">{t("chat.new")}</span>
        </button>

        <div className="relative mt-4 min-w-0">
          <Search
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-sidebar-foreground/50"
            aria-hidden="true"
          />
          <label htmlFor="chat-search" className="sr-only">
            {t("chat.searchAria")}
          </label>
          <input
            id="chat-search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("chat.search")}
            className="w-full min-w-0 rounded-xl border border-sidebar-border bg-sidebar-accent/60 py-2.5 pr-3 pl-9 text-sm text-sidebar-foreground placeholder:text-sidebar-foreground/50 focus:border-sidebar-ring focus:outline-none"
          />
        </div>
      </div>

      <div className="min-h-0 min-w-0 flex-1 overflow-x-hidden overflow-y-auto px-3 pb-3">
        <p className="px-2 py-2 text-xs font-semibold tracking-wider text-sidebar-foreground/50 uppercase">
          {t("chat.recent")}
        </p>
        {filtered.length === 0 ? (
          <p className="px-2 py-6 text-sm text-sidebar-foreground/55">
            {conversations.length === 0 ? t("chat.empty") : t("chat.noMatch")}
          </p>
        ) : (
          <ul className="grid min-w-0 gap-1">
            {filtered.map((c) => (
              <li key={c.id} className="group relative min-w-0">
                <button
                  type="button"
                  onClick={() => onSelect(c.id)}
                  className={cn(
                    "flex w-full min-w-0 items-center gap-2.5 rounded-xl py-2.5 pr-10 pl-3 text-left text-sm transition-colors",
                    activeId === c.id
                      ? "bg-sidebar-accent text-sidebar-accent-foreground"
                      : "text-sidebar-foreground/80 hover:bg-sidebar-accent/60",
                  )}
                >
                  <MessageSquare className="size-4 shrink-0 opacity-70" aria-hidden="true" />
                  <span className="min-w-0 flex-1 truncate">{c.title}</span>
                </button>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button
                      type="button"
                      aria-label={t("chat.options", { title: c.title })}
                      className="absolute top-1/2 right-1 grid size-8 -translate-y-1/2 place-items-center rounded-lg text-sidebar-foreground/70 transition-colors hover:bg-sidebar-border/60 hover:text-sidebar-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring"
                    >
                      <MoreVertical className="size-4" />
                    </button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-48">
                    <DropdownMenuItem onClick={() => onClear(c.id)}>
                      <MessageSquare className="size-4" />
                      {t("chat.clear")}
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      className="text-destructive focus:text-destructive"
                      onClick={() => onDelete(c.id)}
                    >
                      <Trash2 className="size-4" />
                      {t("chat.delete")}
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="min-w-0 shrink-0 overflow-x-hidden border-t border-sidebar-border p-3">
        <button
          type="button"
          onClick={onOpenSettings}
          className="mb-2 w-full min-w-0 rounded-2xl border border-sidebar-border/80 bg-sidebar-accent/40 p-3 text-left transition-colors hover:bg-sidebar-accent/70"
        >
          <span className="flex items-center gap-2 text-xs font-semibold tracking-wide text-sidebar-foreground/80 uppercase">
            <BookOpen className="size-3.5 shrink-0" aria-hidden="true" />
            {t("settings.packTitle")}
          </span>
          <span className="mt-1 block truncate text-xs text-sidebar-foreground/65">
            {packMeta
              ? t("settings.packStatus", { version: packMeta.version, count: packMeta.entryCount })
              : t("settings.packMissing")}
          </span>
          <span className="mt-2 flex items-start gap-2 border-t border-sidebar-border/60 pt-2">
            <Brain className="mt-0.5 size-3.5 shrink-0 text-sidebar-foreground/70" aria-hidden="true" />
            <span className="min-w-0 flex-1">
              <span className="block text-xs font-semibold text-sidebar-foreground/80">
                {t("settings.memoryTitle")}
              </span>
              <span className="mt-0.5 line-clamp-2 block text-xs text-sidebar-foreground/60">
                {memoryPreview.trim() || t("settings.memoryEmpty")}
              </span>
            </span>
          </span>
        </button>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className="flex w-full min-w-0 items-center gap-3 rounded-2xl p-2 text-left transition-colors hover:bg-sidebar-accent/70"
            >
              <span className="grid size-9 shrink-0 place-items-center rounded-full bg-sidebar-primary text-xs font-bold text-sidebar-primary-foreground">
                {initials}
              </span>
              <span className="min-w-0 flex-1 overflow-hidden">
                <span className="block truncate text-sm font-semibold">{displayName}</span>
                <span className="block truncate text-xs text-sidebar-foreground/60">{displayEmail}</span>
              </span>
              <Settings className="size-4 shrink-0 text-sidebar-foreground/60" aria-hidden="true" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-56">
            <DropdownMenuLabel className="font-normal">
              <span className="block text-sm font-semibold text-foreground">{displayName}</span>
              <span className="block truncate text-xs text-muted-foreground">{displayEmail}</span>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={onOpenSettings}>
              <Settings className="size-4" />
              {t("chat.settings")}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="text-destructive focus:text-destructive" asChild>
              <Link
                to="/auth"
                onClick={() => {
                  clearAuthSession();
                }}
              >
                <LogOut className="size-4" />
                {t("chat.logout")}
              </Link>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
}
