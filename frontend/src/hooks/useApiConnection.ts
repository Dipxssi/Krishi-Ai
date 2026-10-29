import { useCallback, useEffect, useRef, useState } from "react";
import { probeApiReachable, type ApiReachability } from "@/lib/apiReachability";

export type ConnectionUiState = ApiReachability | "sending";

/**
 * Tracks whether the API answers /health. Prefer this over navigator.onLine.
 * Optional `sending` override comes from the outbox flusher.
 */
export function useApiConnection(options?: {
  sending?: boolean;
  pollMs?: number;
}) {
  const pollMs = options?.pollMs ?? 15_000;
  const [reachability, setReachability] = useState<ApiReachability>("checking");
  const inFlight = useRef(false);

  const refresh = useCallback(async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    try {
      const ok = await probeApiReachable();
      setReachability(ok ? "online" : "offline");
    } finally {
      inFlight.current = false;
    }
  }, []);

  useEffect(() => {
    void refresh();

    const onOnline = () => void refresh();
    const onOffline = () => setReachability("offline");
    const onVisible = () => {
      if (document.visibilityState === "visible") void refresh();
    };

    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);
    document.addEventListener("visibilitychange", onVisible);
    const timer = window.setInterval(() => void refresh(), pollMs);

    return () => {
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
      document.removeEventListener("visibilitychange", onVisible);
      window.clearInterval(timer);
    };
  }, [pollMs, refresh]);

  const status: ConnectionUiState = options?.sending
    ? "sending"
    : reachability;

  return { status, reachability, refresh };
}
