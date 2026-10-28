import { useState } from "react";
import {
  BadgeIndianRupee,
  ChevronRight,
  Droplets,
  Gauge,
  Info,
  MapPin,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import type { DecisionScore, QueryResponse } from "@/api";
import SafeRecommendationRenderer from "@/SafeRecommendationRenderer";
import { NearbyHelpDialog } from "@/components/chat/NearbyHelpDialog";
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
  const [helpDialogOpen, setHelpDialogOpen] = useState(false);
  const score = result.decision_score;
  const confidencePct = pct(result.confidence ?? 0);
  const escalation = result.escalation;

  const disclaimerText =
    result.disclaimer ||
    "KrishiAI provides AI-generated guidance that may not always be accurate. Verify important crop diagnoses and treatment decisions with a qualified agricultural expert.";

  if (compact) {
    return (
      <div className={cn("grid gap-3.5", className)}>
        <div className="advice-markdown overflow-x-auto leading-relaxed">
          <SafeRecommendationRenderer text={result.final_recommendation} />
        </div>

        {/* Safety & Expert Referral Banner when warranted */}
        {escalation?.requires_escalation && (
          <div className="rounded-2xl border border-amber-500/30 bg-amber-50/70 p-3.5 dark:border-amber-500/20 dark:bg-amber-950/25 space-y-2.5">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-amber-900 dark:text-amber-200">
              <ShieldAlert className="size-4 text-amber-600 dark:text-amber-400 shrink-0" />
              <span>
                {escalation.urgency === "high"
                  ? "Expert Verification Recommended"
                  : "Agronomic Referral Advised"}
              </span>
            </div>

            {escalation.reason && (
              <p className="text-xs text-amber-950/90 dark:text-amber-100/90 leading-normal">
                {escalation.reason}
              </p>
            )}

            {escalation.safe_next_step && (
              <div className="text-xs text-foreground/80 bg-background/60 dark:bg-background/40 rounded-xl p-2.5 border border-amber-200/50 dark:border-amber-900/40">
                <strong className="text-foreground">Safe Immediate Step: </strong>
                {escalation.safe_next_step}
              </div>
            )}

            <div className="pt-1 flex flex-wrap items-center justify-between gap-2">
              <button
                type="button"
                onClick={() => setHelpDialogOpen(true)}
                className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 px-3 py-1.5 text-xs font-semibold text-white shadow-soft transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
              >
                <MapPin className="size-3.5" />
                <span>{escalation.action_label || "Find an agricultural expert near me"}</span>
              </button>
            </div>
          </div>
        )}

        {onOpenScores && score && (
          <button
            type="button"
            onClick={onOpenScores}
            className="group inline-flex w-fit items-center gap-1.5 rounded-xl border border-primary/20 bg-primary/5 px-3 py-1.5 text-xs font-semibold text-primary transition-colors hover:bg-primary/10 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            See crop economics & viability score
            <ChevronRight
              className="size-3.5 transition-transform group-hover:translate-x-0.5"
              aria-hidden="true"
            />
          </button>
        )}

        {/* Subtle AI Disclaimer at Bottom */}
        <div className="mt-1 flex items-start gap-1.5 border-t border-border/40 pt-2 text-[11px] leading-relaxed text-muted-foreground/80">
          <Info className="mt-0.5 size-3 shrink-0 text-muted-foreground/60" aria-hidden="true" />
          <span>{disclaimerText}</span>
        </div>

        <NearbyHelpDialog
          open={helpDialogOpen}
          onOpenChange={setHelpDialogOpen}
          language={result.response_language || "en"}
        />
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

      <div className="advice-markdown overflow-x-auto rounded-2xl border border-border/70 bg-muted/30 p-4 leading-relaxed">
        <SafeRecommendationRenderer text={result.final_recommendation} />
      </div>

      {/* Safety & Expert Referral Banner when warranted */}
      {escalation?.requires_escalation && (
        <div className="rounded-2xl border border-amber-500/30 bg-amber-50/70 p-4 dark:border-amber-500/20 dark:bg-amber-950/25 space-y-3">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-amber-900 dark:text-amber-200">
            <ShieldAlert className="size-4 text-amber-600 dark:text-amber-400 shrink-0" />
            <span>
              {escalation.urgency === "high"
                ? "Expert Physical Verification Recommended"
                : "Agricultural Extension Referral Advised"}
            </span>
          </div>

          {escalation.reason && (
            <p className="text-xs sm:text-sm text-amber-950/90 dark:text-amber-100/90 leading-normal">
              {escalation.reason}
            </p>
          )}

          {escalation.safe_next_step && (
            <div className="text-xs sm:text-sm text-foreground/90 bg-background/60 dark:bg-background/40 rounded-xl p-3 border border-amber-200/50 dark:border-amber-900/40">
              <strong className="text-foreground">Safe Immediate Step: </strong>
              {escalation.safe_next_step}
            </div>
          )}

          {escalation.sample_instructions && (
            <div className="text-xs text-muted-foreground flex items-center gap-1.5">
              <span>What to take: {escalation.sample_instructions}</span>
            </div>
          )}

          <div className="pt-1">
            <button
              type="button"
              onClick={() => setHelpDialogOpen(true)}
              className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 px-4 py-2 text-xs sm:text-sm font-semibold text-white shadow-soft transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
            >
              <MapPin className="size-4" />
              <span>{escalation.action_label || "Find an agricultural expert near me"}</span>
            </button>
          </div>
        </div>
      )}

      {score ? (
        <section className="grid gap-3" aria-label="Decision scores">
          <h3 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            Crop Economics & Viability
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

      {/* Subtle AI Disclaimer at Bottom */}
      <div className="mt-2 flex items-start gap-1.5 border-t border-border/40 pt-3 text-[11px] leading-relaxed text-muted-foreground/80">
        <Info className="mt-0.5 size-3.5 shrink-0 text-muted-foreground/60" aria-hidden="true" />
        <span>{disclaimerText}</span>
      </div>

      <NearbyHelpDialog
        open={helpDialogOpen}
        onOpenChange={setHelpDialogOpen}
        language={result.response_language || "en"}
      />
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
