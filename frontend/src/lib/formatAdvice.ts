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

  const diagnosis = response.image_diagnosis;
  if (diagnosis) {
    const lines = ["", "**Leaf image diagnosis**"];
    if (diagnosis.status === "rejected") {
      lines.push(`Could not diagnose: ${diagnosis.rejection_reason ?? "image rejected"}`);
    } else {
      const label =
        diagnosis.predicted_disease ||
        diagnosis.disease ||
        diagnosis.plant_name ||
        "Unknown";
      lines.push(`Prediction: ${label}`);
      if (typeof diagnosis.confidence === "number") {
        lines.push(`Confidence: ${(diagnosis.confidence * 100).toFixed(1)}%`);
      }
      if (diagnosis.top_3?.length) {
        lines.push(
          `Top matches: ${diagnosis.top_3
            .map((t) => `${t.display_name} (${(t.confidence * 100).toFixed(0)}%)`)
            .join(", ")}`,
        );
      }
      if (diagnosis.treatment_hints?.length) {
        lines.push(`Hints: ${diagnosis.treatment_hints.join("; ")}`);
      }
      if (diagnosis.disclaimer) {
        lines.push(diagnosis.disclaimer);
      }
    }
    parts.push(lines.join("\n"));
  }

  if (response.warnings?.length) {
    parts.push(`\nWarnings:\n${response.warnings.map((w) => `- ${w}`).join("\n")}`);
  }

  if (response.missing_context?.length) {
    parts.push(
      `\nTo improve this answer, please add: ${response.missing_context.join(", ")}`,
    );
  }

  if (response.agents_used?.length) {
    parts.push(`\n_Agents involved: ${response.agents_used.join(", ")}_`);
  }

  return parts.join("\n").trim() || "I could not generate a recommendation. Please try again.";
}
