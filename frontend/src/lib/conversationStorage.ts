import type { Conversation } from "@/data/mockChats";

export const LEGACY_CONVERSATIONS_KEY = "krishi-ai-conversations";

export function conversationsStorageKey(farmerId: string): string {
  return `krishi-ai-conversations:${farmerId}`;
}

function parseConversationList(raw: string | null): Conversation[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw) as Conversation[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function loadConversations(farmerId: string): Conversation[] {
  if (!farmerId) return [];
  try {
    const scoped = parseConversationList(localStorage.getItem(conversationsStorageKey(farmerId)));
    if (scoped.length > 0) return scoped;

    // One-time migrate: claim legacy shared chats for this account when scoped store is empty.
    const legacy = parseConversationList(localStorage.getItem(LEGACY_CONVERSATIONS_KEY));
    if (legacy.length > 0) {
      localStorage.setItem(conversationsStorageKey(farmerId), JSON.stringify(legacy));
      localStorage.removeItem(LEGACY_CONVERSATIONS_KEY);
      return legacy;
    }

    localStorage.removeItem(LEGACY_CONVERSATIONS_KEY);
    return scoped;
  } catch {
    return [];
  }
}

export function saveConversations(farmerId: string, conversations: Conversation[]): void {
  if (!farmerId) return;
  try {
    localStorage.setItem(conversationsStorageKey(farmerId), JSON.stringify(conversations));
    localStorage.removeItem(LEGACY_CONVERSATIONS_KEY);
  } catch {
    /* storage unavailable */
  }
}

export function clearLegacyConversationStorage(): void {
  try {
    localStorage.removeItem(LEGACY_CONVERSATIONS_KEY);
  } catch {
    /* ignore */
  }
}
