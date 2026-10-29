import type { Conversation } from "@/data/mockChats";

export const LEGACY_CONVERSATIONS_KEY = "krishi-ai-conversations";

export function conversationsStorageKey(farmerId: string): string {
  return `krishi-ai-conversations:${farmerId}`;
}

export function loadConversations(farmerId: string): Conversation[] {
  if (!farmerId) return [];
  try {
    const scoped = localStorage.getItem(conversationsStorageKey(farmerId));
    if (scoped) {
      const parsed = JSON.parse(scoped) as Conversation[];
      return Array.isArray(parsed) ? parsed : [];
    }

    // One-time migrate: only if legacy blob exists AND no scoped data yet.
    // Never assign another account's chats — drop the shared legacy key.
    localStorage.removeItem(LEGACY_CONVERSATIONS_KEY);
    return [];
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
