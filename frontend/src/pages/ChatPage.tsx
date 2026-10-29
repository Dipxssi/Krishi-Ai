import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Sprout } from "lucide-react";
import { toast } from "sonner";
import { askAdvice, getFarmer, saveFarmer, submitFeedback, type QueryResponse } from "@/api";
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
import { useApiConnection } from "@/hooks/useApiConnection";
import { useAuthUser } from "@/hooks/useAuthUser";
import { useOutboxFlush } from "@/hooks/useOutboxFlush";
import { isNetworkFailure, isUnauthorizedError } from "@/lib/apiReachability";
import {
  loadConversations,
  saveConversations,
} from "@/lib/conversationStorage";
import { isFarmProfileComplete, loadFarmProfile, saveFarmProfileLocal } from "@/lib/farmProfile";
import { formatAdviceMessage, mapAgentsToUi } from "@/lib/formatAdvice";
import { enqueueOutboxItem } from "@/lib/queryOutbox";

function titleFrom(text: string) {
  const clean = text.trim().replace(/\s+/g, " ");
  return clean.length > 42 ? `${clean.slice(0, 42)}…` : clean;
}

export function ChatPage() {
  const user = useAuthUser();
  const farmerId = user?.farmer_id ?? "";
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [storageReady, setStorageReady] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [thinking, setThinking] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [detailsResult, setDetailsResult] = useState<QueryResponse | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const speechUtteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
  const speakingMessageRef = useRef<string | null>(null);
  const [speakingMessageId, setSpeakingMessageId] = useState<string | null>(null);

  useEffect(() => () => {
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
  }, []);

  const speak = (text: string, messageId: string) => {
    if (!("speechSynthesis" in window) || !("SpeechSynthesisUtterance" in window)) {
      toast.error("Speech playback is not supported by this browser.");
      return;
    }

    const synthesis = window.speechSynthesis;
    if (speakingMessageRef.current === messageId) {
      synthesis.cancel();
      speechUtteranceRef.current = null;
      speakingMessageRef.current = null;
      setSpeakingMessageId(null);
      return;
    }

    synthesis.cancel();
    speechUtteranceRef.current = null;
    speakingMessageRef.current = null;

    const utterance = new SpeechSynthesisUtterance(text);
    const language = /[\u0C80-\u0CFF]/u.test(text)
      ? "kn-IN"
      : /[\u0900-\u097F]/u.test(text)
        ? "hi-IN"
        : "en-IN";
    utterance.lang = language;

    const voices = synthesis.getVoices();
    const matchingVoice = voices.find((voice) => voice.lang.toLowerCase() === language.toLowerCase())
      ?? voices.find((voice) => voice.lang.toLowerCase().startsWith(language.slice(0, 2).toLowerCase()))
      ?? (language === "en-IN" ? voices.find((voice) => voice.lang.toLowerCase().startsWith("en")) : undefined);
    if (matchingVoice) {
      utterance.voice = matchingVoice;
    } else if (voices.length > 0) {
      toast.info(`No ${language} voice is installed. Using the device's default voice.`);
    }

    speechUtteranceRef.current = utterance;
    speakingMessageRef.current = messageId;
    setSpeakingMessageId(messageId);
    const finish = () => {
      if (speechUtteranceRef.current === utterance) {
        speechUtteranceRef.current = null;
        speakingMessageRef.current = null;
        setSpeakingMessageId(null);
      }
    };
    utterance.onend = finish;
    utterance.onerror = (event) => {
      finish();
      if (event.error !== "canceled" && event.error !== "interrupted") {
        toast.error("The device could not speak this response.");
      }
    };
    synthesis.speak(utterance);
  };

  // Load only this signed-in farmer's chats — never a shared browser key.
  useEffect(() => {
    setStorageReady(false);
    setActiveId(null);
    if (!farmerId) {
      setConversations([]);
      return;
    }
    setConversations(loadConversations(farmerId));
    setStorageReady(true);
  }, [farmerId]);

  useEffect(() => {
    if (!storageReady || !farmerId) return;
    saveConversations(farmerId, conversations);
  }, [conversations, farmerId, storageReady]);

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

  const applyAdviceReply = useCallback(
    (
      conversationId: string,
      response: QueryResponse,
      placeholderMessageId?: string,
    ) => {
      const reply: ChatMessageData = {
        id: placeholderMessageId ?? newId(),
        role: "assistant",
        content: formatAdviceMessage(response),
        agent: mapAgentsToUi(response.agents_used ?? []),
        requestId: response.request_id,
        queryResult: response,
      };
      updateConversation(conversationId, (c) => {
        const withoutPlaceholder = placeholderMessageId
          ? c.messages.filter((m) => m.id !== placeholderMessageId)
          : c.messages;
        return {
          ...c,
          updatedAt: Date.now(),
          messages: [...withoutPlaceholder, reply],
        };
      });
    },
    [],
  );

  const handleOutboxDelivered = useCallback(
    ({ item, response }: { item: { conversationId: string; placeholderMessageId: string }; response: QueryResponse }) => {
      applyAdviceReply(item.conversationId, response, item.placeholderMessageId);
      toast.success("Queued question answered");
    },
    [applyAdviceReply],
  );

  const { flushing, pendingCount, flush, refreshCount } = useOutboxFlush(
    farmerId,
    handleOutboxDelivered,
  );
  const { status: connectionStatus, refresh: refreshConnection } = useApiConnection({
    sending: flushing,
  });

  const ensureFarmer = async () => {
    let profile = loadFarmProfile();
    // Prefer this account's Neon row over any leftover local cache.
    if (!isFarmProfileComplete(profile) && farmerId) {
      try {
        profile = await getFarmer(farmerId);
        saveFarmProfileLocal(profile);
      } catch {
        /* keep local */
      }
    }
    if (profile.farmer_id && profile.farmer_id === farmerId) {
      try {
        await saveFarmer(profile);
      } catch {
        /* Offline or API down — local profile is enough to queue the question. */
      }
    }
    return profile;
  };

  const queueOffline = async (
    conversationId: string,
    question: string,
    profileFarmerId: string,
    imageBase64?: string | null,
    cropHint?: string | null,
    language?: string | null,
    status: "waiting" | "auth_required" = "waiting",
  ) => {
    const placeholderId = newId();
    const outboxId = newId();
    await enqueueOutboxItem({
      id: outboxId,
      farmerId: profileFarmerId,
      conversationId,
      placeholderMessageId: placeholderId,
      query: question,
      imageBase64: imageBase64 || null,
      selectedCrop: cropHint || null,
      language: language || null,
      status,
    });
    const reply: ChatMessageData = {
      id: placeholderId,
      role: "assistant",
      content:
        status === "auth_required"
          ? "Your question is saved on this phone. Sign in again when you have a connection, then it will send automatically."
          : "Your question is saved on this phone. When you join the shop WiFi (or any internet), Krishi AI will answer automatically.",
      agent: "general",
      deliveryStatus: status,
      outboxId,
    };
    updateConversation(conversationId, (c) => ({
      ...c,
      updatedAt: Date.now(),
      messages: [...c.messages, reply],
    }));
    await refreshCount();
    toast.message(
      status === "auth_required"
        ? "Saved — sign in when online"
        : "Saved offline — will send when connected",
    );
  };

  const respond = async (conversationId: string, question: string, imageBase64?: string | null, cropHint?: string | null) => {
    setThinking(true);
    try {
      const profile = await ensureFarmer();
      const response = await askAdvice(
        profile.farmer_id,
        question,
        imageBase64,
        cropHint || profile.crop || undefined,
        imageBase64 ? "mobilenetv3" : undefined,
        profile.preferred_language,
      );
      applyAdviceReply(conversationId, response);
      void refreshConnection();
    } catch (error) {
      const profile = loadFarmProfile();
      const fid = profile.farmer_id || farmerId;
      if (fid && isUnauthorizedError(error)) {
        await queueOffline(
          conversationId,
          question,
          fid,
          imageBase64,
          cropHint || profile.crop,
          profile.preferred_language,
          "auth_required",
        );
        return;
      }
      if (fid && isNetworkFailure(error)) {
        await queueOffline(
          conversationId,
          question,
          fid,
          imageBase64,
          cropHint || profile.crop,
          profile.preferred_language,
          "waiting",
        );
        void refreshConnection();
        return;
      }
      const message = error instanceof Error ? error.message : "Request failed";
      toast.error(message);
      const reply: ChatMessageData = {
        id: newId(),
        role: "assistant",
        content: `Sorry — I could not get advice right now.\n\n${message}\n\nCheck Settings for your farm profile, or open Field relay if you need shop WiFi.`,
        agent: "general",
      };
      updateConversation(conversationId, (c) => ({
        ...c,
        updatedAt: Date.now(),
        messages: [...c.messages, reply],
      }));
    } finally {
      setThinking(false);
      void flush();
    }
  };

  const handleSend = (text: string, imageBase64?: string | null, cropHint?: string | null) => {
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
      void respond(conversation.id, text, imageBase64, cropHint);
      return;
    }

    updateConversation(active.id, (c) => ({
      ...c,
      title: c.messages.length === 0 ? titleFrom(text) : c.title,
      updatedAt: Date.now(),
      messages: [...c.messages, userMessage],
    }));
    void respond(active.id, text, imageBase64, cropHint);
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
        <SheetContent
          side="left"
          className="w-[min(100vw,20rem)] max-w-full border-none bg-sidebar p-0"
        >
          <SheetTitle className="sr-only">Conversations</SheetTitle>
          {sidebar}
        </SheetContent>
      </Sheet>

      <main className="flex min-w-0 flex-1 flex-col">
        <ChatHeader
          onOpenSidebar={() => setSidebarOpen(true)}
          onNewChat={handleNewChat}
          onOpenSettings={() => setSettingsOpen(true)}
          connectionStatus={connectionStatus}
          pendingCount={pendingCount}
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
                  onSpeak={m.role === "assistant" ? () => speak(m.queryResult?.final_recommendation ?? m.content, m.id) : undefined}
                  isSpeaking={speakingMessageId === m.id}
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

        <ChatInput
          onSend={handleSend}
          disabled={thinking}
          preferredLanguage={loadFarmProfile().preferred_language}
        />
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
