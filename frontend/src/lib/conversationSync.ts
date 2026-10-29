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
  return {
    id: conversation.id,
    title: conversation.title,
    updatedAt: conversation.updatedAt,
    messages: conversation.messages
      .filter((m) => m.deliveryStatus !== "waiting" && m.deliveryStatus !== "sending")
      .map(sanitizeMessage),
  };
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

export function mergeConversations(local: Conversation[], remote: Conversation[]): Conversation[] {
  const byId = new Map<string, Conversation>();
  for (const item of remote) {
    if (item?.id) byId.set(item.id, item);
  }
  for (const item of local) {
    if (!item?.id) continue;
    const existing = byId.get(item.id);
    if (!existing || (item.updatedAt ?? 0) >= (existing.updatedAt ?? 0)) {
      byId.set(item.id, item);
    }
  }
  return Array.from(byId.values()).sort((a, b) => (b.updatedAt ?? 0) - (a.updatedAt ?? 0));
}

async function pushAllResilient(conversations: Conversation[]): Promise<void> {
  const payload = conversations.map(sanitizeConversationForSync);
  if (payload.length === 0) return;

  try {
    await pushRemoteConversations(payload);
    return;
  } catch (batchError) {
    console.warn("[krishi] batch conversation sync failed; retrying one-by-one", batchError);
  }

  // Partial success beats total failure (e.g. one oversized thread).
  const failures: string[] = [];
  for (const conversation of payload) {
    try {
      await pushRemoteConversation(conversation);
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
};

/** Pull server history, merge with this device, write both sides. */
export async function syncConversationsFromServer(farmerId: string): Promise<ConversationSyncResult> {
  const local = loadConversations(farmerId);
  let remote: Conversation[] = [];
  let pulled = false;

  try {
    remote = await fetchRemoteConversations();
    pulled = true;
  } catch (error) {
    console.warn("[krishi] could not fetch remote conversations", error);
  }

  const merged = pulled ? mergeConversations(local, remote) : local;
  saveConversations(farmerId, merged);

  let pushed = merged.length === 0;
  // Always attempt upload — even when GET failed — so history leaves this browser.
  if (merged.length > 0) {
    try {
      await pushAllResilient(merged);
      pushed = true;
    } catch (error) {
      console.warn("[krishi] could not push conversations after sync", error);
      pushed = false;
    }
  }

  return { conversations: merged, pulled, pushed };
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
