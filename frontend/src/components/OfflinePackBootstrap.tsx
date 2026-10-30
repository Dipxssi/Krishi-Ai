import { useEffect } from "react";
import { ensureOfflinePackSynced } from "@/lib/offlinePack";

/** Quietly keep the offline knowledge pack current whenever the app is online. */
export function OfflinePackBootstrap() {
  useEffect(() => {
    let cancelled = false;

    const run = () => {
      if (cancelled) return;
      void ensureOfflinePackSynced();
    };

    // Let sign-in and the farm form use the network first. The pack is a
    // large JSON and used to download immediately on every visit.
    const requestIdle = window.requestIdleCallback?.bind(window);
    const idleHandle = requestIdle ? requestIdle(run, { timeout: 4000 }) : null;
    const timeoutHandle = idleHandle == null ? window.setTimeout(run, 2000) : null;
    window.addEventListener("online", run);
    const onVisible = () => {
      if (document.visibilityState === "visible") run();
    };
    document.addEventListener("visibilitychange", onVisible);

    return () => {
      cancelled = true;
      if (idleHandle != null) window.cancelIdleCallback(idleHandle);
      if (timeoutHandle != null) window.clearTimeout(timeoutHandle);
      window.removeEventListener("online", run);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, []);

  return null;
}
