import type { ChatMessageData, Conversation } from "@/data/mockChats";
import {
  deleteAllRemoteConversations,
  deleteRemoteConversation,
  fetchRemoteConversations,
  pushRemoteConversations,
} from "@/api";
import { loadConversations, saveConversations } from "@/lib/conversationStorage";

/** Drop bulky / transient fields before uploading to Neon. */
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
  if (message.queryResult) next.queryResult = message.queryResult;
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

/** Pull server history, merge with this device, write both sides. */
export async function syncConversationsFromServer(farmerId: string): Promise<Conversation[]> {
  const local = loadConversations(farmerId);
  let remote: Conversation[] = [];
  try {
    remote = await fetchRemoteConversations();
  } catch {
    // Offline / API down — keep local only.
    return local;
  }

  const merged = mergeConversations(local, remote);
  saveConversations(farmerId, merged);

  try {
    await pushRemoteConversations(merged.map(sanitizeConversationForSync));
  } catch {
    /* local cache still updated */
  }

  return merged;
}

export async function pushConversationsToServer(conversations: Conversation[]): Promise<void> {
  await pushRemoteConversations(conversations.map(sanitizeConversationForSync));
}

export async function removeRemoteConversation(conversationId: string): Promise<void> {
  await deleteRemoteConversation(conversationId);
}

export async function clearRemoteConversations(): Promise<void> {
  await deleteAllRemoteConversations();
}
