import { Menu, MessageSquarePlus, Settings, Sprout } from "lucide-react";

interface ChatHeaderProps {
  onOpenSidebar: () => void;
  onNewChat: () => void;
  onOpenSettings: () => void;
}

export function ChatHeader({ onOpenSidebar, onNewChat, onOpenSettings }: ChatHeaderProps) {
  return (
    <header className="flex items-center gap-3 border-b border-border bg-background/85 px-4 py-3 backdrop-blur sm:px-6">
      <button
        type="button"
        onClick={onOpenSidebar}
        aria-label="Open conversations"
        className="grid size-10 place-items-center rounded-xl border border-border text-foreground hover:bg-muted lg:hidden"
      >
        <Menu className="size-5" />
      </button>

      <span className="grid size-9 place-items-center rounded-2xl bg-gradient-leaf shadow-soft">
        <Sprout className="size-5 text-primary-foreground" aria-hidden="true" />
      </span>
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold text-foreground">Krishi AI</p>
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <span aria-hidden="true" className="size-1.5 rounded-full bg-primary" />
          AI Agricultural Assistant
        </p>
      </div>

      <div className="ml-auto flex items-center gap-1">
        <button
          type="button"
          onClick={onNewChat}
          aria-label="Start a new chat"
          title="New chat"
          className="grid size-10 place-items-center rounded-xl text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <MessageSquarePlus className="size-5" />
        </button>
        <button
          type="button"
          onClick={onOpenSettings}
          aria-label="Open settings"
          title="Settings"
          className="grid size-10 place-items-center rounded-xl text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <Settings className="size-5" />
        </button>
      </div>
    </header>
  );
}
