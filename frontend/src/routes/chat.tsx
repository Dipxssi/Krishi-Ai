import { useEffect, useMemo, useRef, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Sprout } from "lucide-react";
import { toast } from "sonner";
import { ChatHeader } from "@/components/chat/ChatHeader";
import { ChatInput } from "@/components/chat/ChatInput";
import { ChatMessage } from "@/components/chat/ChatMessage";
import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { SettingsModal } from "@/components/chat/SettingsModal";
import { SuggestedPrompt } from "@/components/chat/SuggestedPrompt";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import {
  MOCK_CONVERSATIONS,
  newId,
  type Conversation,
  type ChatMessageData,
} from "@/data/mockChats";
import { SUGGESTED_PROMPTS, getMockResponse } from "@/data/mockResponses";

export const Route = createFileRoute("/chat")({
  head: () => ({
    meta: [
      { title: "Krishi AI Assistant — Chat Dashboard" },
      {
        name: "description",
        content:
          "Chat with Krishi AI's specialist agents about crops, diseases, pests and agricultural finance.",
      },
      { property: "og:title", content: "Krishi AI Assistant — Chat Dashboard" },
      {
        property: "og:description",
        content: "Ask farming and finance questions and get guidance from specialized AI agents.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: ChatPage,
});

const STORAGE_KEY = "krishi-ai-conversations";

function titleFrom(text: string) {
  const clean = text.trim().replace(/\s+/g, " ");
  return clean.length > 42 ? `${clean.slice(0, 42)}…` : clean;
}

function ChatPage() {
  const [conversations, setConversations] = useState<Conversation[]>(MOCK_CONVERSATIONS);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [thinking, setThinking] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Load frontend-only history (no backend).
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as Conversation[];
        if (Array.isArray(parsed) && parsed.length > 0) setConversations(parsed);
      }
    } catch {
      /* ignore malformed demo data */
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
    } catch {
      /* storage unavailable */
    }
  }, [conversations]);

  const active = useMemo(
    () => conversations.find((c) => c.id === activeId) ?? null,
    [conversations, activeId],
  );
  const messages = active?.messages ?? [];

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, thinking]);

  const updateConversation = (id: string, update: (c: Conversation) => Conversation) =>
    setConversations((prev) => prev.map((c) => (c.id === id ? update(c) : c)));

  const respond = (conversationId: string, question: string, variant = 0) => {
    setThinking(true);
    window.setTimeout(() => {
      const { agent, content } = getMockResponse(question, variant);
      const reply: ChatMessageData = { id: newId(), role: "assistant", content, agent };
      updateConversation(conversationId, (c) => ({
        ...c,
        updatedAt: Date.now(),
        messages: [...c.messages, reply],
      }));
      setThinking(false);
    }, 1100);
  };

  const handleSend = (text: string) => {
    const userMessage: ChatMessageData = { id: newId(), role: "user", content: text };

    if (!active) {
      const conversation: Conversation = {
        id: newId(),
        title: titleFrom(text),
        updatedAt: Date.now(),
        messages: [userMessage],
      };
      setConversations((prev) => [conversation, ...prev]);
      setActiveId(conversation.id);
      respond(conversation.id, text);
      return;
    }

    updateConversation(active.id, (c) => ({
      ...c,
      title: c.messages.length === 0 ? titleFrom(text) : c.title,
      updatedAt: Date.now(),
      messages: [...c.messages, userMessage],
    }));
    respond(active.id, text);
  };

  const handleNewChat = () => {
    setActiveId(null);
    setSidebarOpen(false);
    toast.success("Started a new chat");
  };

  const handleSelect = (id: string) => {
    setActiveId(id);
    setSidebarOpen(false);
  };

  const handleDelete = (id: string) => {
    setConversations((prev) => prev.filter((c) => c.id !== id));
    if (activeId === id) setActiveId(null);
    toast.success("Conversation deleted");
  };

  const handleClear = (id: string) => {
    updateConversation(id, (c) => ({ ...c, messages: [] }));
    toast.success("Conversation cleared");
  };

  const handleRegenerate = () => {
    if (!active) return;
    const lastUser = [...active.messages].reverse().find((m) => m.role === "user");
    if (!lastUser) return;
    updateConversation(active.id, (c) => {
      const trimmed = [...c.messages];
      if (trimmed[trimmed.length - 1]?.role === "assistant") trimmed.pop();
      return { ...c, messages: trimmed };
    });
    respond(active.id, lastUser.content, 1);
    toast("Regenerating response…");
  };

  const handleFeedback = (messageId: string, value: "up" | "down") => {
    if (!active) return;
    updateConversation(active.id, (c) => ({
      ...c,
      messages: c.messages.map((m) =>
        m.id === messageId ? { ...m, feedback: m.feedback === value ? undefined : value } : m,
      ),
    }));
    toast.success(value === "up" ? "Thanks for the feedback!" : "Feedback noted");
  };

  const sidebar = (
    <ChatSidebar
      conversations={conversations}
      activeId={activeId}
      onSelect={handleSelect}
      onNewChat={handleNewChat}
      onDelete={handleDelete}
      onClear={handleClear}
      onOpenSettings={() => setSettingsOpen(true)}
    />
  );

  const lastMessage = messages[messages.length - 1];

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <aside className="hidden w-[280px] shrink-0 lg:block">{sidebar}</aside>

      <Sheet open={sidebarOpen} onOpenChange={setSidebarOpen}>
        <SheetContent side="left" className="w-[300px] border-none bg-sidebar p-0">
          <SheetTitle className="sr-only">Conversations</SheetTitle>
          {sidebar}
        </SheetContent>
      </Sheet>

      <main className="flex min-w-0 flex-1 flex-col">
        <ChatHeader
          onOpenSidebar={() => setSidebarOpen(true)}
          onNewChat={handleNewChat}
          onOpenSettings={() => setSettingsOpen(true)}
        />

        <div className="min-h-0 flex-1 overflow-y-auto scroll-smooth px-4 py-6 sm:px-6">
          {messages.length === 0 ? (
            <div className="mx-auto flex h-full max-w-3xl animate-in fade-in flex-col justify-center py-10 duration-500">
              <div className="text-center">
                <span className="mx-auto grid size-16 place-items-center rounded-3xl bg-gradient-leaf shadow-lift">
                  <Sprout className="size-8 text-primary-foreground" aria-hidden="true" />
                </span>
                <h1 className="mt-6 text-2xl font-semibold text-foreground sm:text-3xl">
                  How can Krishi AI help you today?
                </h1>
                <p className="mx-auto mt-3 max-w-xl text-sm text-muted-foreground sm:text-base">
                  Ask me about crops, diseases, farming practices, agricultural finance, loans, or
                  other farming problems.
                </p>
              </div>
              <div className="mt-9 grid gap-3 sm:grid-cols-2">
                {SUGGESTED_PROMPTS.map((p) => (
                  <SuggestedPrompt
                    key={p.text}
                    emoji={p.emoji}
                    text={p.text}
                    onSelect={handleSend}
                  />
                ))}
              </div>
            </div>
          ) : (
            <div className="mx-auto grid max-w-3xl gap-7">
              {messages.map((m) => (
                <ChatMessage
                  key={m.id}
                  message={m}
                  onRegenerate={
                    m.role === "assistant" && m.id === lastMessage?.id ? handleRegenerate : undefined
                  }
                  onFeedback={
                    m.role === "assistant" ? (value) => handleFeedback(m.id, value) : undefined
                  }
                />
              ))}

              {thinking && (
                <div className="flex animate-in fade-in items-center gap-3">
                  <span className="grid size-9 shrink-0 place-items-center rounded-full bg-gradient-leaf">
                    <Sprout className="size-4 text-primary-foreground" aria-hidden="true" />
                  </span>
                  <div className="flex items-center gap-2 rounded-2xl border border-border bg-card px-4 py-3 shadow-soft">
                    <span className="flex gap-1" aria-hidden="true">
                      {[0, 150, 300].map((delay) => (
                        <span
                          key={delay}
                          className="size-2 animate-bounce rounded-full bg-primary"
                          style={{ animationDelay: `${delay}ms` }}
                        />
                      ))}
                    </span>
                    <span className="text-sm text-muted-foreground">Krishi AI is thinking…</span>
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        <ChatInput onSend={handleSend} disabled={thinking} />
      </main>

      <SettingsModal
        open={settingsOpen}
        onOpenChange={setSettingsOpen}
        onClearAll={() => {
          setConversations([]);
          setActiveId(null);
        }}
      />
    </div>
  );
}
