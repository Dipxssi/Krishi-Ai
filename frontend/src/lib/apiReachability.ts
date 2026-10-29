/** Probe whether the KrishiAi API is reachable (not just navigator.onLine). */

const API_BASE = import.meta.env.VITE_API_URL ?? "";

export type ApiReachability = "checking" | "online" | "offline";

export async function probeApiReachable(timeoutMs = 5000): Promise<boolean> {
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
