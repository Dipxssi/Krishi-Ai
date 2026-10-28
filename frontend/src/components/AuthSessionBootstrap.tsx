import { useEffect } from "react";
import { fetchMe } from "@/api";
import { clearAuthSession, getAccessToken, getAuthUser, persistAuthSession } from "@/lib/authSession";

/** Revalidate JWT on boot; clear stale local sessions. */
export function AuthSessionBootstrap() {
  useEffect(() => {
    const token = getAccessToken();
    if (!token) return;

    let cancelled = false;
    (async () => {
      try {
        const user = await fetchMe(token);
        if (cancelled) return;
        const existing = getAuthUser();
        if (!existing || existing.id !== user.id || existing.farmer_id !== user.farmer_id) {
          persistAuthSession(token, user);
        }
      } catch {
        if (!cancelled) clearAuthSession();
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  return null;
}
