/** Probe whether the KrishiAi API is reachable (not just navigator.onLine). */

const API_BASE = import.meta.env.VITE_API_URL ?? "";

export type ApiReachability = "checking" | "online" | "offline";

/**
 * A sleeping host (Render/Neon) often needs 20–40s for the first request.
 * Aborting /health at 5s painted "Network is unavailable" while sign-in was
 * still waiting, and the abort could cancel the wake-up the real request needed.
 */
export const API_PROBE_TIMEOUT_MS = 20_000;
export const API_WAKE_TIMEOUT_MS = 45_000;

/** True when the browser reports a network. Missing `navigator` counts as online. */
export function browserIsOnline(): boolean {
  return typeof navigator === "undefined" || navigator.onLine !== false;
}

export async function probeApiReachable(timeoutMs = API_PROBE_TIMEOUT_MS): Promise<boolean> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${API_BASE}/health`, {
      method: "GET",
      cache: "no-store",
      signal: controller.signal,
    });
    return res.ok;
  } catch {
    return false;
  } finally {
    window.clearTimeout(timer);
  }
}

let wakeInFlight: Promise<boolean> | null = null;

/**
 * One long /health so the auth screen can wake a sleeping API while the
 * person fills the form. Callers share the same request — a second short
 * probe used to abort the wake and start it over on Sign In.
 */
export function warmApi(timeoutMs = API_WAKE_TIMEOUT_MS): Promise<boolean> {
  if (!wakeInFlight) {
    wakeInFlight = probeApiReachable(timeoutMs).finally(() => {
      wakeInFlight = null;
    });
  }
  return wakeInFlight;
}

/** True when the error looks like a transport failure, not an HTTP 4xx/5xx from the API. */
export function isNetworkFailure(error: unknown): boolean {
  if (!(error instanceof Error)) return false;
  const msg = error.message.toLowerCase();
  if (error.name === "TypeError") return true;
  if (error.name === "AbortError") return true;
  if (msg.includes("failed to fetch")) return true;
  if (msg.includes("networkerror")) return true;
  if (msg.includes("network request failed")) return true;
  if (msg.includes("load failed")) return true;
  if (msg.includes("could not reach")) return true;
  return false;
}

export function isUnauthorizedError(error: unknown): boolean {
  if (!(error instanceof Error)) return false;
  const msg = error.message.toLowerCase();
  return msg.includes("401") || msg.includes("unauthorized") || msg.includes("sign in");
}
