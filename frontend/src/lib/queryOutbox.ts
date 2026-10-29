/** IndexedDB outbox for advice questions when the API is unreachable. */

const DB_NAME = "krishi-ai-outbox";
const DB_VERSION = 1;
const STORE = "pending";

export type OutboxStatus = "waiting" | "sending" | "auth_required" | "failed";

export type OutboxItem = {
  id: string;
  farmerId: string;
  conversationId: string;
  placeholderMessageId: string;
  query: string;
  imageBase64?: string | null;
  selectedCrop?: string | null;
  language?: string | null;
  createdAt: number;
  status: OutboxStatus;
  lastError?: string | null;
};

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onerror = () => reject(request.error ?? new Error("IndexedDB open failed"));
    request.onsuccess = () => resolve(request.result);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE)) {
        const store = db.createObjectStore(STORE, { keyPath: "id" });
        store.createIndex("by_created", "createdAt", { unique: false });
        store.createIndex("by_farmer", "farmerId", { unique: false });
      }
    };
  });
}

function txDone(tx: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error ?? new Error("IndexedDB transaction failed"));
    tx.onabort = () => reject(tx.error ?? new Error("IndexedDB transaction aborted"));
  });
}

export async function enqueueOutboxItem(
  item: Omit<OutboxItem, "createdAt" | "status"> & { status?: OutboxStatus },
): Promise<OutboxItem> {
  const full: OutboxItem = {
    ...item,
    createdAt: Date.now(),
    status: item.status ?? "waiting",
  };
  const db = await openDb();
  try {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).put(full);
    await txDone(tx);
    return full;
  } finally {
    db.close();
  }
}

export async function listOutboxItems(farmerId?: string): Promise<OutboxItem[]> {
  const db = await openDb();
  try {
    const tx = db.transaction(STORE, "readonly");
    const store = tx.objectStore(STORE);
    const request = farmerId
      ? store.index("by_farmer").getAll(farmerId)
      : store.getAll();
    const rows = await new Promise<OutboxItem[]>((resolve, reject) => {
      request.onsuccess = () => resolve((request.result as OutboxItem[]) ?? []);
      request.onerror = () => reject(request.error ?? new Error("IndexedDB getAll failed"));
    });
    await txDone(tx);
    return rows.sort((a, b) => a.createdAt - b.createdAt);
  } finally {
    db.close();
  }
}

export async function updateOutboxItem(
  id: string,
  patch: Partial<Pick<OutboxItem, "status" | "lastError">>,
): Promise<void> {
  const db = await openDb();
  try {
    const tx = db.transaction(STORE, "readwrite");
    const store = tx.objectStore(STORE);
    const existing = await new Promise<OutboxItem | undefined>((resolve, reject) => {
      const req = store.get(id);
      req.onsuccess = () => resolve(req.result as OutboxItem | undefined);
      req.onerror = () => reject(req.error ?? new Error("IndexedDB get failed"));
    });
    if (!existing) {
      await txDone(tx);
      return;
    }
    store.put({ ...existing, ...patch });
    await txDone(tx);
  } finally {
    db.close();
  }
}

export async function removeOutboxItem(id: string): Promise<void> {
  const db = await openDb();
  try {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).delete(id);
    await txDone(tx);
  } finally {
    db.close();
  }
}

export async function countWaiting(farmerId?: string): Promise<number> {
  const items = await listOutboxItems(farmerId);
  return items.filter((i) => i.status === "waiting" || i.status === "sending" || i.status === "auth_required")
    .length;
}
