import { useState } from "react";
import { Link } from "react-router-dom";
import { LogOut, MessageSquare, MoreVertical, Plus, Search, Settings, Trash2 } from "lucide-react";
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
import { clearAuthSession } from "@/lib/authSession";
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
  const authUser = useAuthUser();
  const displayName = authUser?.name?.trim() || authUser?.email?.split("@")[0] || "Farmer";
  const displayEmail = authUser?.email || "Not signed in";
  const initials = initialsFromName(displayName);
  const filtered = conversations.filter((c) =>
    (c.title + " " + c.messages.map((m) => m.content).join(" "))
      .toLowerCase()
      .includes(query.trim().toLowerCase()),
  );

  return (
    <div className="flex h-full flex-col bg-sidebar text-sidebar-foreground">
      <div className="p-4">
        <Logo tone="onDark" />

        <button
          type="button"
          onClick={onNewChat}
          className="mt-4 flex w-full items-center justify-center gap-2 rounded-2xl bg-gradient-leaf px-4 py-3 text-sm font-semibold text-primary-foreground shadow-soft transition-opacity hover:opacity-95 focus-visible:ring-2 focus-visible:ring-sidebar-ring focus-visible:outline-none"
        >
          <Plus className="size-4" />
          New Chat
        </button>

        <div className="relative mt-4">
          <Search
            className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-sidebar-foreground/50"
            aria-hidden="true"
          />
          <label htmlFor="chat-search" className="sr-only">
            Search conversations
          </label>
          <input
            id="chat-search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search conversations"
            className="w-full rounded-xl border border-sidebar-border bg-sidebar-accent/60 py-2.5 pr-3 pl-9 text-sm text-sidebar-foreground placeholder:text-sidebar-foreground/50 focus:border-sidebar-ring focus:outline-none"
          />
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-3">
        <p className="px-2 py-2 text-xs font-semibold tracking-wider text-sidebar-foreground/50 uppercase">
          Recent Chats
        </p>
        {filtered.length === 0 ? (
          <p className="px-2 py-6 text-sm text-sidebar-foreground/55">
            {conversations.length === 0
              ? "No conversations yet. Start a new chat to see history here."
              : "No conversations match your search."}
          </p>
        ) : (
          <ul className="grid gap-1">
            {filtered.map((c) => (
              <li key={c.id} className="group relative">
                <button
                  type="button"
                  onClick={() => onSelect(c.id)}
                  className={cn(
                    "flex w-full items-center gap-2.5 rounded-xl py-2.5 pr-9 pl-3 text-left text-sm transition-colors",
                    activeId === c.id
                      ? "bg-sidebar-accent text-sidebar-accent-foreground"
                      : "text-sidebar-foreground/80 hover:bg-sidebar-accent/60",
                  )}
                >
                  <MessageSquare className="size-4 shrink-0 opacity-70" aria-hidden="true" />
                  <span className="truncate">{c.title}</span>
                </button>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button
                      type="button"
                      aria-label={`Options for ${c.title}`}
                      className="absolute top-1/2 right-1 grid size-7 -translate-y-1/2 place-items-center rounded-lg text-sidebar-foreground/60 opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100 hover:bg-sidebar-border/60 hover:text-sidebar-foreground"
                    >
                      <MoreVertical className="size-4" />
                    </button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="start" className="w-48">
                    <DropdownMenuItem onClick={() => onClear(c.id)}>
                      <MessageSquare className="size-4" />
                      Clear conversation
                    </DropdownMenuItem>
                    <DropdownMenuItem className="text-destructive focus:text-destructive" onClick={() => onDelete(c.id)}>
                      <Trash2 className="size-4" />
                      Delete conversation
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="border-t border-sidebar-border p-3">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className="flex w-full items-center gap-3 rounded-2xl p-2 text-left transition-colors hover:bg-sidebar-accent/70"
            >
              <span className="grid size-9 shrink-0 place-items-center rounded-full bg-sidebar-primary text-xs font-bold text-sidebar-primary-foreground">
                {initials}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-semibold">{displayName}</span>
                <span className="block truncate text-xs text-sidebar-foreground/60">{displayEmail}</span>
              </span>
              <Settings className="size-4 text-sidebar-foreground/60" aria-hidden="true" />
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
              Settings
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
                Log out
              </Link>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
}
