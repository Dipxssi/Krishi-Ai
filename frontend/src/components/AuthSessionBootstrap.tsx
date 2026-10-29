import { useEffect } from "react";
import { fetchMe } from "@/api";
import { probeApiReachable } from "@/lib/apiReachability";
import {
  clearAccessTokenOnly,
  continueOfflineAs,
  getAccessToken,
  getAuthUser,
  getLastCachedUser,
  isOfflineSession,
  persistAuthSession,
  setOfflineSession,
} from "@/lib/authSession";
import { hydrateFarmProfileFromServer } from "@/lib/farmProfile";

function rememberLastUser(user: { id: string; email: string; name: string; farmer_id: string }) {
  try {
    localStorage.setItem("krishi-ai-last-user", JSON.stringify(user));
  } catch {
    /* ignore */
  }
}

/** Revalidate JWT on boot; keep offline Continue-as when the API is unreachable. */
export function AuthSessionBootstrap() {
  useEffect(() => {
    let cancelled = false;

    (async () => {
      const token = getAccessToken();
      const reachable = await probeApiReachable();

      if (!token) {
        if (!cancelled && isOfflineSession() && (getAuthUser() || getLastCachedUser())) {
          continueOfflineAs(getAuthUser() || getLastCachedUser());
        }
        return;
      }

      if (!reachable) {
        if (!cancelled) {
          const user = getAuthUser() || getLastCachedUser();
          if (user) continueOfflineAs(user);
        }
        return;
      }

      try {
        const user = await fetchMe(token);
        if (cancelled) return;
        const existing = getAuthUser();
        if (!existing || existing.id !== user.id || existing.farmer_id !== user.farmer_id) {
          persistAuthSession(token, user);
        } else {
          setOfflineSession(false);
          rememberLastUser(user);
        }
        await hydrateFarmProfileFromServer();
      } catch (error) {
        if (cancelled) return;
        const message = error instanceof Error ? error.message.toLowerCase() : "";
        const unauthorized = message.includes("401") || message.includes("unauthorized");
        const last = getLastCachedUser() || getAuthUser();
        if (unauthorized) {
          if (last) rememberLastUser(last);
          clearAccessTokenOnly();
          try {
            localStorage.removeItem("krishi-ai-auth-user");
            localStorage.removeItem("krishi-ai-offline-session");
          } catch {
            /* ignore */
          }
          if (last) rememberLastUser(last);
        } else {
          const user = getAuthUser() || getLastCachedUser();
          if (user) continueOfflineAs(user);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const onOnline = () => {
      const token = getAccessToken();
      if (!token) return;
      void (async () => {
        try {
          const user = await fetchMe(token);
          persistAuthSession(token, user);
          await hydrateFarmProfileFromServer();
        } catch {
          /* keep offline until password login */
        }
      })();
    };
    window.addEventListener("online", onOnline);
    return () => window.removeEventListener("online", onOnline);
  }, []);

  return null;
}
