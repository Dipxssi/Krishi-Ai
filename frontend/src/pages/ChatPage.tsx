import { useEffect, useMemo, useRef, useState } from "react";
import { Sprout } from "lucide-react";
import { toast } from "sonner";
import { askAdvice, saveFarmer, submitFeedback, type QueryResponse } from "@/api";
import { AdviceDetailsPanel } from "@/components/chat/AdviceDetailsPanel";
import { ChatHeader } from "@/components/chat/ChatHeader";
import { ChatInput } from "@/components/chat/ChatInput";
import { ChatMessage } from "@/components/chat/ChatMessage";
import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { SettingsPanel } from "@/components/chat/SettingsPanel";
import { SuggestedPrompt } from "@/components/chat/SuggestedPrompt";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { newId, type Conversation, type ChatMessageData } from "@/data/mockChats";
import { SUGGESTED_PROMPTS } from "@/data/mockResponses";
import { loadFarmProfile } from "@/lib/farmProfile";
import { formatAdviceMessage, mapAgentsToUi } from "@/lib/formatAdvice";

const STORAGE_KEY = "krishi-ai-conversations";

function titleFrom(text: string) {
  const clean = text.trim().replace(/\s+/g, " ");
  return clean.length > 42 ? `${clean.slice(0, 42)}…` : clean;
}

export function ChatPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [thinking, setThinking] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [detailsResult, setDetailsResult] = useState<QueryResponse | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as Conversation[];
        if (Array.isArray(parsed) && parsed.length > 0) setConversations(parsed);
      }
    } catch {
      /* ignore malformed data */
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

  const ensureFarmer = async () => {
    const profile = loadFarmProfile();
    await saveFarmer(profile);
    return profile;
  };

  const respond = async (conversationId: string, question: string, imageBase64?: string | null) => {
    setThinking(true);
    try {
      const profile = await ensureFarmer();
      const response = await askAdvice(
        profile.farmer_id,
        question,
        imageBase64,
        profile.crop,
        imageBase64 ? "mobilenetv3" : undefined,
      );
      const reply: ChatMessageData = {
        id: newId(),
        role: "assistant",
        content: formatAdviceMessage(response),
        agent: mapAgentsToUi(response.agents_used ?? []),
        requestId: response.request_id,
        queryResult: response,
      };
      updateConversation(conversationId, (c) => ({
        ...c,
        updatedAt: Date.now(),
        messages: [...c.messages, reply],
      }));
    } catch (error) {
      const message = error instanceof Error ? error.message : "Request failed";
      toast.error(message);
      const reply: ChatMessageData = {
        id: newId(),
        role: "assistant",
        content: `Sorry — I could not reach the Krishi AI backend.\n\n${message}\n\nCheck that the API is running and your farm profile is set in Settings.`,
        agent: "general",
      };
      updateConversation(conversationId, (c) => ({
        ...c,
        updatedAt: Date.now(),
        messages: [...c.messages, reply],
      }));
    } finally {
      setThinking(false);
    }
  };

  const handleSend = (text: string, imageBase64?: string | null) => {
    const userMessage: ChatMessageData = {
      id: newId(),
      role: "user",
      content: text,
      imagePreview: imageBase64 || undefined,
    };

    if (!active) {
      const conversation: Conversation = {
        id: newId(),
        title: titleFrom(text),
        updatedAt: Date.now(),
        messages: [userMessage],
      };
      setConversations((prev) => [conversation, ...prev]);
      setActiveId(conversation.id);
      void respond(conversation.id, text, imageBase64);
      return;
    }

    updateConversation(active.id, (c) => ({
      ...c,
      title: c.messages.length === 0 ? titleFrom(text) : c.title,
      updatedAt: Date.now(),
      messages: [...c.messages, userMessage],
    }));
    void respond(active.id, text, imageBase64);
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
    void respond(active.id, lastUser.content, lastUser.imagePreview);
    toast("Regenerating response…");
  };

  const handleFeedback = async (messageId: string, value: "up" | "down") => {
    if (!active) return;
    const message = active.messages.find((m) => m.id === messageId);
    updateConversation(active.id, (c) => ({
      ...c,
      messages: c.messages.map((m) =>
        m.id === messageId ? { ...m, feedback: m.feedback === value ? undefined : value } : m,
      ),
    }));
    if (message?.requestId && message.feedback !== value) {
      try {
        await submitFeedback(message.requestId, value === "up" ? 5 : 1);
      } catch {
        /* non-blocking */
      }
    }
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
                  Ask about crops, diseases, farming practices, finance — or attach a leaf photo for
                  MobileNetV3 diagnosis.
                </p>
              </div>
              <div className="mt-9 grid gap-3 sm:grid-cols-2">
                {SUGGESTED_PROMPTS.map((p) => (
                  <SuggestedPrompt
                    key={p.text}
                    emoji={p.emoji}
                    text={p.text}
                    onSelect={(text) => handleSend(text)}
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
                    m.role === "assistant" ? (value) => void handleFeedback(m.id, value) : undefined
                  }
                  onOpenDetails={
                    m.queryResult
                      ? () => {
                          setDetailsResult(m.queryResult ?? null);
                          setDetailsOpen(true);
                        }
                      : undefined
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

      <SettingsPanel
        open={settingsOpen}
        onOpenChange={setSettingsOpen}
        onClearAll={() => {
          setConversations([]);
          setActiveId(null);
        }}
      />

      <AdviceDetailsPanel
        result={detailsResult}
        open={detailsOpen}
        onOpenChange={setDetailsOpen}
      />
    </div>
  );
}
