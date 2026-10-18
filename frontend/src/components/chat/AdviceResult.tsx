import {
  AlertTriangle,
  BadgeIndianRupee,
  ChevronRight,
  Droplets,
  Gauge,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import type { DecisionScore, QueryResponse } from "@/api";
import SafeRecommendationRenderer from "@/SafeRecommendationRenderer";
import { cn } from "@/lib/utils";

function formatInr(value: number): string {
  return Math.round(value).toLocaleString("en-IN");
}

function pct(value: number): number {
  return Math.round(Math.min(1, Math.max(0, value)) * 100);
}

export function AdviceResult({
  result,
  compact,
  onOpenScores,
  className,
}: {
  result: QueryResponse;
  /** Chat bubble: recommendation only + link to scores panel. */
  compact?: boolean;
  onOpenScores?: () => void;
  className?: string;
}) {
  const score = result.decision_score;
  const confidencePct = pct(result.confidence ?? 0);

  if (compact) {
    return (
      <div className={cn("grid gap-4", className)}>
        <div className="advice-markdown overflow-x-auto">
          <SafeRecommendationRenderer text={result.final_recommendation} />
        </div>

        {result.agents_used?.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {result.agents_used.map((a) => (
              <span
                key={a}
                className="rounded-full border border-border/80 bg-muted/40 px-2.5 py-0.5 text-[11px] font-medium text-muted-foreground"
              >
                {a.replace(/_/g, " ")}
              </span>
            ))}
          </div>
        )}

        {onOpenScores && (
          <button
            type="button"
            onClick={onOpenScores}
            className="group inline-flex w-fit items-center gap-1.5 rounded-xl border border-primary/20 bg-primary/5 px-3 py-2 text-sm font-semibold text-primary transition-colors hover:bg-primary/10 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            See the complete decision score
            <ChevronRight
              className="size-4 transition-transform group-hover:translate-x-0.5"
              aria-hidden="true"
            />
          </button>
        )}
      </div>
    );
  }

  return (
    <div className={cn("grid gap-5", className)}>
      <div className="flex flex-wrap items-center gap-2">
        <MetricPill
          icon={Gauge}
          label="Confidence"
          value={`${confidencePct}%`}
          hint="Pipeline heuristic"
          tone={confidencePct >= 70 ? "good" : confidencePct >= 45 ? "mid" : "low"}
        />
        {score && (
          <MetricPill
            icon={Sparkles}
            label="Decision"
            value={`${pct(score.final_score)}/100`}
            hint="Composite index"
            tone={pct(score.final_score) >= 65 ? "good" : "mid"}
          />
        )}
        {result.structured_recommendation?.risk_level && (
          <MetricPill
            icon={ShieldAlert}
            label="Risk"
            value={result.structured_recommendation.risk_level}
            tone="mid"
          />
        )}
      </div>

      <div className="advice-markdown overflow-x-auto rounded-2xl border border-border/70 bg-muted/30 p-4">
        <SafeRecommendationRenderer text={result.final_recommendation} />
      </div>

      {score ? (
        <section className="grid gap-3" aria-label="Decision scores">
          <h3 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            Decision scores
          </h3>
          <div className="grid gap-2.5">
            <ScoreBar label="Agronomic suitability" value={score.agronomic_score} tone="leaf" />
            <ScoreBar label="Economic viability" value={score.economic_score} tone="gold" />
            <ScoreBar label="Overall decision index" value={score.final_score} tone="soil" />
          </div>
          <ScoreMetrics score={score} />
        </section>
      ) : (
        <p className="rounded-xl border border-dashed border-border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
          No decision score for this reply — scores appear when the pipeline has enough farm and market
          context.
        </p>
      )}

      {result.warnings?.length > 0 && (
        <section className="rounded-2xl border border-amber-200/80 bg-amber-50/80 px-4 py-3 dark:border-amber-900/50 dark:bg-amber-950/30">
          <div className="mb-1.5 flex items-center gap-2 text-sm font-semibold text-amber-900 dark:text-amber-100">
            <AlertTriangle className="size-4" aria-hidden="true" />
            Warnings
          </div>
          <ul className="grid gap-1 text-sm text-amber-950/90 dark:text-amber-50/90">
            {result.warnings.map((w) => (
              <li key={w} className="flex gap-2">
                <span aria-hidden="true" className="mt-2 size-1.5 shrink-0 rounded-full bg-amber-600" />
                <span>{w}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {result.missing_context?.length > 0 && (
        <p className="text-xs text-muted-foreground">
          Add to improve advice:{" "}
          <span className="font-medium text-foreground">
            {result.missing_context.map((f) => f.replace(/_/g, " ")).join(", ")}
          </span>
        </p>
      )}

      {result.agents_used?.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {result.agents_used.map((a) => (
            <span
              key={a}
              className="rounded-full border border-border/80 bg-card px-2.5 py-0.5 text-[11px] font-medium text-muted-foreground"
            >
              {a.replace(/_/g, " ")}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function ScoreMetrics({ score }: { score: DecisionScore }) {
  return (
    <div className="mt-1 grid grid-cols-2 gap-2 sm:grid-cols-4">
      <MiniStat
        icon={BadgeIndianRupee}
        label="Expected profit"
        value={`₹${formatInr(score.expected_profit)}`}
      />
      <MiniStat icon={BadgeIndianRupee} label="Input cost" value={`₹${formatInr(score.input_cost)}`} />
      <MiniStat
        icon={Droplets}
        label="Water risk"
        value={`${pct(score.water_risk)}%`}
      />
      <MiniStat
        icon={ShieldAlert}
        label="Disease risk"
        value={
          score.disease_risk != null ? `${pct(score.disease_risk)}%` : "Suppressed"
        }
      />
    </div>
  );
}

function MetricPill({
  icon: Icon,
  label,
  value,
  hint,
  tone = "mid",
}: {
  icon: typeof Gauge;
  label: string;
  value: string;
  hint?: string;
  tone?: "good" | "mid" | "low";
}) {
  return (
    <div
      title={hint}
      className={cn(
        "inline-flex items-center gap-2 rounded-2xl border px-3 py-2 text-sm shadow-soft",
        tone === "good" && "border-primary/25 bg-primary/8 text-foreground",
        tone === "mid" && "border-border bg-card text-foreground",
        tone === "low" && "border-destructive/30 bg-destructive/5 text-foreground",
      )}
    >
      <Icon className="size-3.5 text-primary" aria-hidden="true" />
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="font-semibold tabular-nums">{value}</span>
    </div>
  );
}

function ScoreBar({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "leaf" | "gold" | "soil";
}) {
  const valuePct = pct(value);
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-semibold tabular-nums text-foreground">{valuePct}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-muted">
        <div
          className={cn(
            "h-full rounded-full transition-[width] duration-500",
            tone === "leaf" && "bg-primary",
            tone === "gold" && "bg-amber-500",
            tone === "soil" && "bg-earth",
          )}
          style={{ width: `${valuePct}%` }}
        />
      </div>
    </div>
  );
}

function MiniStat({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Gauge;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-2xl border border-border/70 bg-card px-3 py-2.5">
      <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
        <Icon className="size-3" aria-hidden="true" />
        {label}
      </div>
      <p className="mt-1 text-sm font-semibold tabular-nums text-foreground">{value}</p>
    </div>
  );
}
