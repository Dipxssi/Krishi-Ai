import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Sprout } from "lucide-react";
import { toast } from "sonner";
import { askAdvice, getFarmer, submitFeedback, type QueryResponse } from "@/api";
import { getAccessToken, isOfflineSession, setOfflineSession } from "@/lib/authSession";
import { buildOfflineAdvice } from "@/lib/offlineAdvisor";
import { AdviceDetailsPanel } from "@/components/chat/AdviceDetailsPanel";
import { ChatHeader } from "@/components/chat/ChatHeader";
import { ChatInput } from "@/components/chat/ChatInput";
import { ChatMessage } from "@/components/chat/ChatMessage";
import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { MemoryPanel } from "@/components/chat/MemoryPanel";
import { SettingsPanel } from "@/components/chat/SettingsPanel";
import { SuggestedPrompt } from "@/components/chat/SuggestedPrompt";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { newId, type Conversation, type ChatMessageData } from "@/data/mockChats";
import { useApiConnection } from "@/hooks/useApiConnection";
import { useAuthUser } from "@/hooks/useAuthUser";
import { useI18n } from "@/hooks/useI18n";
import { useOutboxFlush } from "@/hooks/useOutboxFlush";
import { isNetworkFailure, isUnauthorizedError } from "@/lib/apiReachability";
import {
  loadConversations,
  saveConversations,
} from "@/lib/conversationStorage";
import {
  appendConversationSummary,
  loadProfileMemory,
  saveProfileMemory,
  withMemoryContext,
} from "@/lib/conversationMemory";
import {
  clearRemoteConversations,
  mergeConversations,
  pushConversationsToServer,
  removeRemoteConversation,
  syncConversationsFromServer,
} from "@/lib/conversationSync";
import { isFarmProfileComplete, loadFarmProfile, saveFarmProfileLocal } from "@/lib/farmProfile";
import { formatAdviceMessage, mapAgentsToUi } from "@/lib/formatAdvice";
import { enqueueOutboxItem } from "@/lib/queryOutbox";

function titleFrom(text: string) {
  const clean = text.trim().replace(/\s+/g, " ");
  return clean.length > 42 ? `${clean.slice(0, 42)}…` : clean;
}

export function ChatPage() {
  const { t } = useI18n();
  const user = useAuthUser();
  const farmerId = user?.farmer_id ?? "";
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [storageReady, setStorageReady] = useState(false);
  const skipNextConversationSave = useRef(false);
  const syncGeneration = useRef(0);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [thinking, setThinking] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [memoryOpen, setMemoryOpen] = useState(false);
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
      toast.error(t("chat.speakUnsupported"));
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
      toast.info(t("chat.speakNoVoice", { lang: language }));
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
        toast.error(t("chat.speakFail"));
      }
    };
    synthesis.speak(utterance);
  };

  // Load local cache, then merge with server so a new device gets full history.
  useEffect(() => {
    let cancelled = false;
    setStorageReady(false);
    setActiveId(null);
    if (!farmerId) {
      setConversations([]);
      return;
    }

    const runSync = async (quiet: boolean) => {
      const generation = ++syncGeneration.current;
      const result = await syncConversationsFromServer(farmerId);
      if (cancelled || generation !== syncGeneration.current) return;
      skipNextConversationSave.current = true;
      // Prefer in-memory chats so a slow sync cannot wipe messages typed during the fetch.
      setConversations((current) => mergeConversations(current, result.conversations));
      if (!quiet && !result.pushed && (result.conversations.length > 0 || result.wrongApi)) {
        toast.error(result.wrongApi ? t("chat.syncWrongApi") : t("chat.syncFail"));
      }
    };

    skipNextConversationSave.current = true;
    setConversations(loadConversations(farmerId));
    setStorageReady(true);
    void runSync(false);

    const onOnline = () => {
      void runSync(true);
    };
    const onVisible = () => {
      if (document.visibilityState === "visible") void runSync(true);
    };
    window.addEventListener("online", onOnline);
    document.addEventListener("visibilitychange", onVisible);

    return () => {
      cancelled = true;
      syncGeneration.current += 1;
      window.removeEventListener("online", onOnline);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [farmerId, t]);

  useEffect(() => {
    if (!storageReady || !farmerId) return;
    if (skipNextConversationSave.current) {
      skipNextConversationSave.current = false;
      return;
    }
    saveConversations(farmerId, conversations);
    const timer = window.setTimeout(() => {
      void pushConversationsToServer(conversations).catch((error) => {
        console.warn("[krishi] debounced conversation push failed", error);
      });
    }, 250);
    return () => window.clearTimeout(timer);
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
      askedQuestion?: string,
    ) => {
      updateConversation(conversationId, (c) => {
        const prior = placeholderMessageId
          ? c.messages.find((m) => m.id === placeholderMessageId)
          : undefined;
        const replacedOfflineDraft = prior?.deliveryStatus === "offline_draft";
        const withoutPlaceholder = placeholderMessageId
          ? c.messages.filter((m) => m.id !== placeholderMessageId)
          : c.messages;
        const reply: ChatMessageData = {
          id: placeholderMessageId ?? newId(),
          role: "assistant",
          content: formatAdviceMessage(response),
          agent: mapAgentsToUi(response.agents_used ?? []),
          requestId: response.request_id,
          queryResult: response,
          verifiedOnline: replacedOfflineDraft || undefined,
        };
        const lastUser =
          askedQuestion ||
          [...withoutPlaceholder].reverse().find((m) => m.role === "user")?.content ||
          response.query ||
          "";
        const summary = appendConversationSummary(
          c.summary,
          lastUser,
          response.final_recommendation || reply.content,
        );
        if (farmerId && summary) {
          saveProfileMemory(summary, farmerId);
        }
        return {
          ...c,
          summary,
          updatedAt: Date.now(),
          messages: [...withoutPlaceholder, reply],
        };
      });
    },
    [farmerId],
  );

  const handleOutboxDelivered = useCallback(
    ({ item, response }: { item: { conversationId: string; placeholderMessageId: string }; response: QueryResponse }) => {
      applyAdviceReply(item.conversationId, response, item.placeholderMessageId);
      toast.success(t("chat.queuedOk"));
    },
    [applyAdviceReply, t],
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
    offlineAdvice?: string | null,
  ) => {
    const placeholderId = newId();
    const outboxId = newId();
    const conversation =
      conversations.find((c) => c.id === conversationId) ||
      loadConversations(profileFarmerId).find((c) => c.id === conversationId);
    const queryForApi = withMemoryContext(question, {
      chatSummary: conversation?.summary,
      profileNotes: conversation?.summary ? null : loadProfileMemory(profileFarmerId),
    });
    await enqueueOutboxItem({
      id: outboxId,
      farmerId: profileFarmerId,
      conversationId,
      placeholderMessageId: placeholderId,
      query: queryForApi,
      imageBase64: imageBase64 || null,
      selectedCrop: cropHint || null,
      language: language || null,
      status,
    });
    const reply: ChatMessageData = {
      id: placeholderId,
      role: "assistant",
      content:
        offlineAdvice ||
        (status === "auth_required" ? t("chat.offlineAuthBody") : t("chat.offlineWaitBody")),
      agent: "general",
      deliveryStatus: offlineAdvice ? "offline_draft" : status,
      outboxId,
    };
    updateConversation(conversationId, (c) => {
      const summary = offlineAdvice
        ? appendConversationSummary(c.summary, question, offlineAdvice)
        : c.summary;
      if (profileFarmerId && summary) {
        saveProfileMemory(summary, profileFarmerId);
      }
      return {
        ...c,
        summary,
        updatedAt: Date.now(),
        messages: [...c.messages, reply],
      };
    });
    await refreshCount();
    toast.message(
      offlineAdvice
        ? t("chat.offlineDraftToast")
        : status === "auth_required"
          ? t("chat.offlineAuthToast")
          : t("chat.offlineWaitToast"),
    );
  };

  const respond = async (conversationId: string, question: string, imageBase64?: string | null, cropHint?: string | null) => {
    setThinking(true);
    try {
      const profile = await ensureFarmer();
      const conversation =
        conversations.find((c) => c.id === conversationId) ||
        loadConversations(profile.farmer_id || farmerId).find((c) => c.id === conversationId);
      const profileNotes = loadProfileMemory(profile.farmer_id);
      const queryForApi = withMemoryContext(question, {
        chatSummary: conversation?.summary,
        profileNotes: conversation?.summary ? null : profileNotes,
      });

      const token = getAccessToken();
      // Ask the API directly. A separate /health check added seconds and, when
      // it timed out, sent a real question into the offline queue.
      if (!token) {
        const fid = profile.farmer_id || farmerId;
        if (!fid) throw new Error(t("chat.requestFailed"));
        const advice = await buildOfflineAdvice(question);
        await queueOffline(
          conversationId,
          question,
          fid,
          imageBase64,
          cropHint || null,
          profile.preferred_language,
          "auth_required",
          advice.content,
        );
        void refreshConnection();
        return;
      }

      setOfflineSession(false);
      const response = await askAdvice(
        profile.farmer_id,
        queryForApi,
        imageBase64,
        cropHint || undefined,
        imageBase64 ? "mobilenetv3" : undefined,
        profile.preferred_language,
      );
      applyAdviceReply(conversationId, response, undefined, question);
      void refreshConnection();
    } catch (error) {
      const profile = loadFarmProfile();
      const fid = profile.farmer_id || farmerId;
      if (fid && isUnauthorizedError(error)) {
        const advice = await buildOfflineAdvice(question);
        await queueOffline(
          conversationId,
          question,
          fid,
          imageBase64,
          cropHint || null,
          profile.preferred_language,
          "auth_required",
          advice.content,
        );
        return;
      }
      if (fid && isNetworkFailure(error)) {
        const advice = await buildOfflineAdvice(question);
        await queueOffline(
          conversationId,
          question,
          fid,
          imageBase64,
          cropHint || null,
          profile.preferred_language,
          "waiting",
          advice.content,
        );
        void refreshConnection();
        return;
      }
      const message = error instanceof Error ? error.message : t("chat.requestFailed");
      toast.error(message);
      const reply: ChatMessageData = {
        id: newId(),
        role: "assistant",
        content: t("chat.errorBody", {
          prefix: t("chat.errorPrefix"),
          message,
          hint: t("chat.errorHint"),
        }),
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
    toast.success(t("chat.started"));
  };

  const handleSelect = (id: string) => {
    setActiveId(id);
    setSidebarOpen(false);
  };

  const handleDelete = (id: string) => {
    setConversations((prev) => prev.filter((c) => c.id !== id));
    if (activeId === id) setActiveId(null);
    void removeRemoteConversation(id).catch(() => {
      /* local delete still applied; next sync may reintroduce if push failed first */
    });
    toast.success(t("chat.deleted"));
  };

  const handleClear = (id: string) => {
    updateConversation(id, (c) => ({ ...c, messages: [] }));
    toast.success(t("chat.cleared"));
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
    toast(t("chat.regenerating"));
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
    toast.success(value === "up" ? t("chat.feedbackUp") : t("chat.feedbackDown"));
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
      <aside className="hidden w-[280px] shrink-0 overflow-hidden lg:block">{sidebar}</aside>

      <Sheet open={sidebarOpen} onOpenChange={setSidebarOpen}>
        <SheetContent
          side="left"
          className="w-[min(100vw,20rem)] max-w-full overflow-hidden border-none bg-sidebar p-0"
        >
          <SheetTitle className="sr-only">{t("chat.conversations")}</SheetTitle>
          {sidebar}
        </SheetContent>
      </Sheet>

      <main className="flex min-w-0 flex-1 flex-col">
        <ChatHeader
          onOpenSidebar={() => setSidebarOpen(true)}
          onNewChat={handleNewChat}
          onOpenMemory={() => setMemoryOpen(true)}
          onOpenSettings={() => setSettingsOpen(true)}
          connectionStatus={connectionStatus}
          pendingCount={pendingCount}
          offlineSession={isOfflineSession() || !getAccessToken()}
        />

        <div className="min-h-0 flex-1 overflow-y-auto scroll-smooth px-4 py-6 sm:px-6">
          {messages.length === 0 ? (
            <div className="mx-auto flex h-full max-w-3xl animate-in fade-in flex-col justify-center py-10 duration-500">
              <div className="text-center">
                <span className="mx-auto grid size-16 place-items-center rounded-3xl bg-gradient-leaf shadow-lift">
                  <Sprout className="size-8 text-primary-foreground" aria-hidden="true" />
                </span>
                <h1 className="mt-6 text-2xl font-semibold text-foreground sm:text-3xl">
                  {t("chat.hello")}
                </h1>
                <p className="mx-auto mt-3 max-w-xl text-sm text-muted-foreground sm:text-base">
                  {t("chat.helloBody")}
                </p>
              </div>
              <div className="mt-9 grid gap-3 sm:grid-cols-2">
                {[
                  { emoji: "🌾", text: t("chat.prompt1") },
                  { emoji: "🐛", text: t("chat.prompt2") },
                  { emoji: "💰", text: t("chat.prompt3") },
                  { emoji: "🌱", text: t("chat.prompt4") },
                ].map((p) => (
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
                    <span className="text-sm text-muted-foreground">{t("chat.thinking")}</span>
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

      <MemoryPanel open={memoryOpen} onOpenChange={setMemoryOpen} />

      <SettingsPanel
        open={settingsOpen}
        onOpenChange={setSettingsOpen}
        onClearAll={() => {
          setConversations([]);
          setActiveId(null);
          void clearRemoteConversations().catch(() => {
            /* local clear still applied */
          });
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
