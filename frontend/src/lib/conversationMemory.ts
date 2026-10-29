import { getAuthUser } from "@/lib/authSession";

const MAX_SUMMARY_CHARS = 400;

function memoryKey(farmerId: string): string {
  return `krishi-ai-conversation-memory:${farmerId}`;
}

/** Profile-level notes shown in Settings and seeded into new chats. */
export function loadProfileMemory(farmerId?: string): string {
  const id = farmerId || getAuthUser()?.farmer_id || "";
  if (!id) return "";
  try {
    return localStorage.getItem(memoryKey(id))?.trim() || "";
  } catch {
    return "";
  }
}

export function saveProfileMemory(notes: string, farmerId?: string): void {
  const id = farmerId || getAuthUser()?.farmer_id || "";
  if (!id) return;
  try {
    const cleaned = notes.trim().slice(0, MAX_SUMMARY_CHARS * 2);
    if (!cleaned) {
      localStorage.removeItem(memoryKey(id));
      return;
    }
    localStorage.setItem(memoryKey(id), cleaned);
  } catch {
    /* ignore */
  }
}

export function clearProfileMemory(farmerId?: string): void {
  saveProfileMemory("", farmerId);
}

function clip(text: string, max: number): string {
  const cleaned = text.replace(/\s+/g, " ").trim();
  if (cleaned.length <= max) return cleaned;
  return `${cleaned.slice(0, max - 1)}…`;
}

/** Build / refresh a short rolling summary after a Q&A turn. */
export function appendConversationSummary(
  previous: string | undefined,
  question: string,
  answer: string,
): string {
  const line = `• ${clip(question, 90)} → ${clip(answer, 140)}`;
  const parts = [...(previous ? previous.split("\n").map((p) => p.trim()).filter(Boolean) : []), line];
  // Keep newest lines within budget.
  let next = "";
  for (let i = parts.length - 1; i >= 0; i -= 1) {
    const candidate = next ? `${parts[i]}\n${next}` : parts[i];
    if (candidate.length > MAX_SUMMARY_CHARS && next) break;
    next = candidate.length > MAX_SUMMARY_CHARS ? clip(parts[i], MAX_SUMMARY_CHARS) : candidate;
  }
  return next;
}

/** Prefix the farmer question with memory so the API sees prior context. */
export function withMemoryContext(
  question: string,
  opts: { chatSummary?: string | null; profileNotes?: string | null },
): string {
  const blocks: string[] = [];
  const profileNotes = opts.profileNotes?.trim();
  const chatSummary = opts.chatSummary?.trim();
  if (profileNotes) {
    blocks.push(`Recent farm notes:\n${clip(profileNotes, MAX_SUMMARY_CHARS)}`);
  }
  if (chatSummary) {
    blocks.push(`This chat so far:\n${clip(chatSummary, MAX_SUMMARY_CHARS)}`);
  }
  if (blocks.length === 0) return question;
  return `${blocks.join("\n\n")}\n\nFarmer question:\n${question}`;
}
