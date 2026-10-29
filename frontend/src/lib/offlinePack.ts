/** Downloadable offline knowledge pack (Phase 3). Stored in IndexedDB. */

export type OfflinePackEntry = {
  id: string;
  keywords: string[];
  title: string;
  answer: string;
  lang?: string;
  /** Crop slug when tip is crop-specific (from backend crops.json). */
  crop?: string | null;
  source?: string;
};

export type OfflinePack = {
  version: string;
  updatedAt: string;
  entries: OfflinePackEntry[];
  /** Reserved for a future on-device model URL / id. */
  modelHint?: string | null;
};

const DB_NAME = "krishi-ai-offline-pack";
const DB_VERSION = 1;
const STORE = "packs";
const PACK_ID = "default";
const META_KEY = "krishi-ai-offline-pack-meta";

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onerror = () => reject(request.error ?? new Error("IndexedDB open failed"));
    request.onsuccess = () => resolve(request.result);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: "id" });
      }
    };
  });
}

export type OfflinePackMeta = {
  version: string;
  updatedAt: string;
  entryCount: number;
  downloadedAt: number;
};

export function getOfflinePackMeta(): OfflinePackMeta | null {
  try {
    const raw = localStorage.getItem(META_KEY);
    return raw ? (JSON.parse(raw) as OfflinePackMeta) : null;
  } catch {
    return null;
  }
}

function setOfflinePackMeta(meta: OfflinePackMeta): void {
  localStorage.setItem(META_KEY, JSON.stringify(meta));
}

export async function loadOfflinePack(): Promise<OfflinePack | null> {
  const db = await openDb();
  try {
    const tx = db.transaction(STORE, "readonly");
    const req = tx.objectStore(STORE).get(PACK_ID);
    const row = await new Promise<{ id: string; pack: OfflinePack } | undefined>((resolve, reject) => {
      req.onsuccess = () => resolve(req.result as { id: string; pack: OfflinePack } | undefined);
      req.onerror = () => reject(req.error ?? new Error("pack get failed"));
    });
    return row?.pack ?? null;
  } finally {
    db.close();
  }
}

export async function saveOfflinePack(pack: OfflinePack): Promise<void> {
  const db = await openDb();
  try {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).put({ id: PACK_ID, pack });
    await new Promise<void>((resolve, reject) => {
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error ?? new Error("pack save failed"));
    });
    setOfflinePackMeta({
      version: pack.version,
      updatedAt: pack.updatedAt,
      entryCount: pack.entries.length,
      downloadedAt: Date.now(),
    });
  } finally {
    db.close();
  }
}

export async function clearOfflinePack(): Promise<void> {
  const db = await openDb();
  try {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).delete(PACK_ID);
    await new Promise<void>((resolve, reject) => {
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error ?? new Error("pack clear failed"));
    });
    localStorage.removeItem(META_KEY);
  } finally {
    db.close();
  }
}

/** Fetch the curated pack from the app origin (must be online once). */
export async function downloadOfflinePack(url = "/offline-pack/v1.json"): Promise<OfflinePack> {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`Could not download offline pack (${res.status})`);
  const pack = (await res.json()) as OfflinePack;
  if (!pack?.version || !Array.isArray(pack.entries)) {
    throw new Error("Invalid offline pack format");
  }
  await saveOfflinePack(pack);
  return pack;
}

export function rankPackEntries(
  question: string,
  pack: OfflinePack,
  locale?: string | null,
  preferredCrop?: string | null,
): OfflinePackEntry[] {
  const q = question.toLowerCase();
  const tokens = q.split(/[^\p{L}\p{N}]+/u).filter((t) => t.length > 2);
  const crop = (preferredCrop || "").trim().toLowerCase();
  const scored = pack.entries.map((entry) => {
    let score = 0;
    for (const kw of entry.keywords) {
      const k = kw.toLowerCase();
      if (q.includes(k)) score += 3;
      for (const t of tokens) {
        if (k.includes(t) || t.includes(k)) score += 1;
      }
    }
    if (crop && entry.crop) {
      if (entry.crop.toLowerCase() === crop) score += 8;
      else if (q.includes(entry.crop.toLowerCase())) score += 4;
    } else if (crop && !entry.crop && score > 0) {
      // Slight preference for general tips when nothing crop-specific matched hard.
      score += 0.5;
    }
    if (locale && entry.lang && entry.lang !== locale.slice(0, 2) && entry.lang !== "en") {
      score *= 0.7;
    }
    return { entry, score };
  });
  return scored
    .filter((s) => s.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 3)
    .map((s) => s.entry);
}
