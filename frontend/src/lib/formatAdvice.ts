import type { QueryResponse } from "@/api";
import type { AgentId } from "@/data/mockChats";

export function mapAgentsToUi(agentsUsed: string[]): AgentId {
  const joined = agentsUsed.map((a) => a.toLowerCase()).join(" ");
  if (joined.includes("finance") || joined.includes("market") || joined.includes("loan")) {
    return "finance";
  }
  if (joined.includes("disease") || joined.includes("crop") || joined.includes("vision")) {
    return agentsUsed.some((a) => /disease|vision|pest/i.test(a)) ? "disease" : "crop";
  }
  if (joined.includes("weather") || joined.includes("soil") || joined.includes("equipment")) {
    return "crop";
  }
  return "general";
}

export function formatAdviceMessage(response: QueryResponse): string {
  const parts: string[] = [];

  if (response.final_recommendation?.trim()) {
    parts.push(response.final_recommendation.trim());
  }

  // Include subtle AI disclaimer at bottom if not already in message
  if (response.disclaimer && !parts.some((p) => p.includes("KrishiAI provides") || p.includes("ಕೃಷಿ AI") || p.includes("कृषि AI"))) {
    parts.push(`\n---\n*${response.disclaimer}*`);
  }

  return parts.join("\n\n").trim() || "I could not prepare a recommendation. Please try again.";
}
