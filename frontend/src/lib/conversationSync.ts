import type { ChatMessageData, Conversation } from "@/data/mockChats";
import type { QueryResponse } from "@/api";
import {
  deleteAllRemoteConversations,
  deleteRemoteConversation,
  fetchRemoteConversations,
  pushRemoteConversation,
  pushRemoteConversations,
} from "@/api";
import { loadConversations, saveConversations } from "@/lib/conversationStorage";

/** Keep sync payloads small enough for Render/Neon — drop bulky diagnosis traces. */
function slimQueryResult(result: QueryResponse): QueryResponse {
  return {
    ...result,
    evidence: [],
    tool_traces: [],
    warnings: result.warnings?.slice(0, 8) ?? [],
    missing_context: result.missing_context?.slice(0, 8) ?? [],
  };
}

/** Drop bulky / transient fields before uploading. */
export function sanitizeConversationForSync(conversation: Conversation): Conversation {
  const next: Conversation = {
    id: conversation.id,
    title: conversation.title,
    updatedAt: conversation.updatedAt,
    messages: conversation.messages
      .filter(
        (m) =>
          m.deliveryStatus !== "waiting" &&
          m.deliveryStatus !== "sending" &&
          m.deliveryStatus !== "offline_draft" &&
          m.deliveryStatus !== "auth_required",
      )
      .map(sanitizeMessage),
  };
  if (conversation.summary?.trim()) next.summary = conversation.summary.trim();
  return next;
}

function sanitizeMessage(message: ChatMessageData): ChatMessageData {
  const next: ChatMessageData = {
    id: message.id,
    role: message.role,
    content: message.content,
  };
  if (message.agent) next.agent = message.agent;
  if (message.feedback) next.feedback = message.feedback;
  if (message.requestId) next.requestId = message.requestId;
  if (message.queryResult) next.queryResult = slimQueryResult(message.queryResult);
  // Skip base64 leaf photos — too large for sync payloads.
  if (message.imagePreview && !message.imagePreview.startsWith("data:")) {
    next.imagePreview = message.imagePreview;
  }
  return next;
}

/**
 * Merge by id. The first list wins on equal/newer `updatedAt`
 * (pass in-memory / latest local first so a slow sync cannot wipe new chats).
 */
export function mergeConversations(preferred: Conversation[], other: Conversation[]): Conversation[] {
  const byId = new Map<string, Conversation>();
  for (const item of other) {
    if (item?.id) byId.set(item.id, item);
  }
  for (const item of preferred) {
    if (!item?.id) continue;
    const existing = byId.get(item.id);
    if (!existing || (item.updatedAt ?? 0) >= (existing.updatedAt ?? 0)) {
      byId.set(item.id, item);
    }
  }
  return Array.from(byId.values()).sort((a, b) => (b.updatedAt ?? 0) - (a.updatedAt ?? 0));
}

function isLikelyColdStartOrCors(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error);
  return (
    /failed to fetch/i.test(message) ||
    /networkerror/i.test(message) ||
    /load failed/i.test(message) ||
    /\b5\d\d\b/.test(message) ||
    /cors/i.test(message)
  );
}

async function sleep(ms: number): Promise<void> {
  await new Promise((resolve) => window.setTimeout(resolve, ms));
}

/** One retry after a short wait — covers Render free-tier cold starts that look like CORS. */
async function withColdStartRetry<T>(run: () => Promise<T>): Promise<T> {
  try {
    return await run();
  } catch (error) {
    if (!isLikelyColdStartOrCors(error)) throw error;
    await sleep(2500);
    return run();
  }
}

async function pushAllResilient(conversations: Conversation[]): Promise<void> {
  const payload = conversations.map(sanitizeConversationForSync);
  if (payload.length === 0) return;

  try {
    await withColdStartRetry(() => pushRemoteConversations(payload));
    return;
  } catch (batchError) {
    console.warn("[krishi] batch conversation sync failed; retrying one-by-one", batchError);
  }

  // Partial success beats total failure (e.g. one oversized thread).
  const failures: string[] = [];
  for (const conversation of payload) {
    try {
      await withColdStartRetry(() => pushRemoteConversation(conversation));
    } catch (error) {
      failures.push(conversation.id);
      console.warn("[krishi] failed to sync conversation", conversation.id, error);
    }
  }
  if (failures.length === payload.length) {
    throw new Error(`Could not sync any conversations (${failures.length} failed)`);
  }
}

export type ConversationSyncResult = {
  conversations: Conversation[];
  /** False when GET /conversations failed (offline or missing proxy/route). */
  pulled: boolean;
  /** False when local history could not be uploaded. */
  pushed: boolean;
  /** Set when the API looks like the wrong service (no /conversations). */
  wrongApi?: boolean;
};

function isMissingConversationsRoute(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error);
  return /\b404\b/.test(message) || /not found/i.test(message) || /non-JSON/i.test(message);
}

/** Pull server history, merge with this device, write both sides. */
export async function syncConversationsFromServer(farmerId: string): Promise<ConversationSyncResult> {
  let remote: Conversation[] = [];
  let pulled = false;
  let wrongApi = false;

  try {
    remote = await withColdStartRetry(() => fetchRemoteConversations());
    pulled = true;
  } catch (error) {
    console.warn("[krishi] could not fetch remote conversations", error);
    wrongApi = isMissingConversationsRoute(error);
  }

  // Re-read AFTER the network round-trip so chats typed while syncing are not lost.
  const localLatest = loadConversations(farmerId);
  const merged = pulled ? mergeConversations(localLatest, remote) : localLatest;
  saveConversations(farmerId, merged);

  let pushed = merged.length === 0;
  // Always attempt upload — even when GET failed — so history leaves this browser.
  if (merged.length > 0) {
    try {
      await pushAllResilient(merged);
      pushed = true;
      wrongApi = false;
    } catch (error) {
      console.warn("[krishi] could not push conversations after sync", error);
      pushed = false;
      if (isMissingConversationsRoute(error)) wrongApi = true;
    }
  }

  return { conversations: merged, pulled, pushed, wrongApi };
}

export async function pushConversationsToServer(conversations: Conversation[]): Promise<void> {
  await pushAllResilient(conversations);
}

export async function removeRemoteConversation(conversationId: string): Promise<void> {
  await deleteRemoteConversation(conversationId);
}

export async function clearRemoteConversations(): Promise<void> {
  await deleteAllRemoteConversations();
}
