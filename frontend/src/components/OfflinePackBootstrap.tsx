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

    run();
    window.addEventListener("online", run);
    const onVisible = () => {
      if (document.visibilityState === "visible") run();
    };
    document.addEventListener("visibilitychange", onVisible);

    return () => {
      cancelled = true;
      window.removeEventListener("online", run);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, []);

  return null;
}
