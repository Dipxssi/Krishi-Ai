import { useCallback, useEffect, useRef, useState } from "react";
import { askAdvice, type QueryResponse } from "@/api";
import { isNetworkFailure, isUnauthorizedError, probeApiReachable } from "@/lib/apiReachability";
import {
  listOutboxItems,
  removeOutboxItem,
  updateOutboxItem,
  type OutboxItem,
} from "@/lib/queryOutbox";

export type OutboxDelivery = {
  item: OutboxItem;
  response: QueryResponse;
};

/**
 * Flushes waiting outbox items one at a time when the API is reachable.
 */
export function useOutboxFlush(
  farmerId: string,
  onDelivered: (delivery: OutboxDelivery) => void,
) {
  const [flushing, setFlushing] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);
  const busy = useRef(false);
  const onDeliveredRef = useRef(onDelivered);
  onDeliveredRef.current = onDelivered;

  const refreshCount = useCallback(async () => {
    if (!farmerId) {
      setPendingCount(0);
      return;
    }
    const items = await listOutboxItems(farmerId);
    setPendingCount(
      items.filter((i) => i.status === "waiting" || i.status === "sending" || i.status === "auth_required")
        .length,
    );
  }, [farmerId]);

  const flush = useCallback(async () => {
    if (!farmerId || busy.current) return;
    busy.current = true;
    setFlushing(true);
    try {
      const reachable = await probeApiReachable();
      if (!reachable) return;

      const items = (await listOutboxItems(farmerId)).filter(
        (i) => i.status === "waiting" || i.status === "auth_required",
      );

      for (const item of items) {
        await updateOutboxItem(item.id, { status: "sending", lastError: null });
        await refreshCount();
        try {
          const response = await askAdvice(
            item.farmerId,
            item.query,
            item.imageBase64,
            item.selectedCrop,
            item.imageBase64 ? "mobilenetv3" : undefined,
            item.language,
          );
          await removeOutboxItem(item.id);
          onDeliveredRef.current({ item, response });
        } catch (error) {
          if (isUnauthorizedError(error)) {
            await updateOutboxItem(item.id, {
              status: "auth_required",
              lastError: "Sign in again when you have a connection.",
            });
            break;
          }
          if (isNetworkFailure(error)) {
            await updateOutboxItem(item.id, { status: "waiting", lastError: null });
            break;
          }
          const message = error instanceof Error ? error.message : "Request failed";
          await updateOutboxItem(item.id, { status: "failed", lastError: message });
        }
        await refreshCount();
      }
    } finally {
      busy.current = false;
      setFlushing(false);
      await refreshCount();
    }
  }, [farmerId, refreshCount]);

  useEffect(() => {
    void refreshCount();
  }, [refreshCount]);

  useEffect(() => {
    if (!farmerId) return;

    const run = () => void flush();
    run();

    const onOnline = () => run();
    const onVisible = () => {
      if (document.visibilityState === "visible") run();
    };

    window.addEventListener("online", onOnline);
    document.addEventListener("visibilitychange", onVisible);
    const timer = window.setInterval(run, 8_000);

    try {
      const registration = navigator.serviceWorker?.ready;
      void registration?.then((reg) => {
        const syncManager = (reg as ServiceWorkerRegistration & {
          sync?: { register: (tag: string) => Promise<void> };
        }).sync;
        void syncManager?.register("krishi-outbox-flush");
      });
    } catch {
      /* Background Sync optional */
    }

    return () => {
      window.removeEventListener("online", onOnline);
      document.removeEventListener("visibilitychange", onVisible);
      window.clearInterval(timer);
    };
  }, [farmerId, flush]);

  return { flushing, pendingCount, flush, refreshCount };
}
