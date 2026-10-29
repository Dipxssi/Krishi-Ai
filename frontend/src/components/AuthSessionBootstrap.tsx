import { useEffect } from "react";
import { fetchMe } from "@/api";
import { clearAuthSession, getAccessToken, getAuthUser, persistAuthSession } from "@/lib/authSession";
import { hydrateFarmProfileFromServer } from "@/lib/farmProfile";

/** Revalidate JWT on boot; clear stale local sessions; load this user's Neon profile. */
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
        await hydrateFarmProfileFromServer();
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
