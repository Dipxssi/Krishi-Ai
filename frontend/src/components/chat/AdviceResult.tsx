import { useEffect, useRef, useState } from "react";
import {
  BadgeIndianRupee,
  ChevronRight,
  Droplets,
  Gauge,
  Info,
  Leaf,
  MapPin,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import type { DecisionScore, QueryResponse } from "@/api";
import SafeRecommendationRenderer from "@/SafeRecommendationRenderer";
import { NearbyHelpDialog } from "@/components/chat/NearbyHelpDialog";
import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";

function formatInr(value: number): string {
  return Math.round(value).toLocaleString("en-IN");
}

function pct(value: number): number {
  return Math.round(Math.min(1, Math.max(0, value)) * 100);
}

function VisionDiagnosisCard({
  diag,
}: {
  diag: NonNullable<QueryResponse["image_diagnosis"]>;
}) {
  const version = diag.model_version ?? "";
  const isMobileNet =
    version.includes("mobilenetv3") || version.includes("hf_space");
  const isAccepted =
    (diag.status === "ok" || diag.status === "accepted") && !diag.requires_expert;
  const plant =
    diag.plant_name ||
    (diag.crop_id
      ? diag.crop_id.charAt(0).toUpperCase() + diag.crop_id.slice(1)
      : "Crop");
  const disease =
    diag.predicted_disease ||
    (diag.disease ? diag.disease.replace(/_/g, " ") : null);
  const conf = diag.confidence ?? diag.disease_confidence;

  return (
    <div
      className={cn(
        "rounded-2xl border p-3.5 space-y-2",
        isMobileNet
          ? "border-emerald-500/35 bg-emerald-50/70 dark:border-emerald-500/25 dark:bg-emerald-950/30"
          : "border-amber-500/30 bg-amber-50/60 dark:border-amber-500/20 dark:bg-amber-950/25",
      )}
    >
      <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-wider">
        <Leaf className="size-3.5 shrink-0" aria-hidden="true" />
        <span className={isMobileNet ? "text-emerald-900 dark:text-emerald-200" : "text-amber-900 dark:text-amber-200"}>
          {isMobileNet ? "MobileNetV3 leaf scan" : "Heuristic leaf screening"}
        </span>
        {version ? (
          <span className="rounded-md bg-background/70 px-1.5 py-0.5 font-mono text-[10px] font-medium normal-case tracking-normal text-muted-foreground">
            {version}
          </span>
        ) : null}
      </div>

      {isAccepted ? (
        <p className="text-sm text-foreground leading-snug">
          <strong>{plant}</strong>
          {diag.is_healthy
            ? " · Healthy (no supported disease detected)"
            : disease
              ? ` · ${disease}`
              : null}
          {conf != null ? (
            <span className="text-muted-foreground">
              {" "}
              · {(conf * 100).toFixed(0)}% confidence (uncalibrated)
            </span>
          ) : null}
        </p>
      ) : (
        <p className="text-sm text-foreground leading-snug">
          {diag.rejection_reason ||
            (diag.requires_expert
              ? "Unconfirmed — expert review recommended"
              : "Image diagnosis abstained")}
        </p>
      )}

      {isMobileNet && diag.top_3 && diag.top_3.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {diag.top_3.slice(0, 3).map((cand, idx) => (
            <span
              key={`${cand.display_name}-${idx}`}
              className="rounded-lg border border-emerald-600/20 bg-background/80 px-2 py-1 text-[11px] text-foreground"
            >
              #{idx + 1} {cand.display_name} {(cand.confidence * 100).toFixed(0)}%
            </span>
          ))}
        </div>
      ) : null}

      {!isMobileNet ? (
        <p className="text-[11px] text-amber-950/80 dark:text-amber-100/80 leading-relaxed">
          Color-ratio fallback was used (Space unreachable or not configured). This is not the trained MobileNet model.
        </p>
      ) : null}
    </div>
  );
}

export function AdviceResult({
  result,
  compact,
  onOpenScores,
  className,
  typewriter = false,
  onTypewriterDone,
  onTypewriterProgress,
}: {
  result: QueryResponse;
  /** Chat bubble: recommendation only + link to scores panel. */
  compact?: boolean;
  onOpenScores?: () => void;
  className?: string;
  /** Reveal the finished recommendation as if it were streaming. */
  typewriter?: boolean;
  onTypewriterDone?: () => void;
  onTypewriterProgress?: () => void;
}) {
  const { t } = useI18n();
  const [helpDialogOpen, setHelpDialogOpen] = useState(false);
  const score = result.decision_score;
  const confidencePct = pct(result.confidence ?? 0);
  const escalation = result.escalation;

  const disclaimerText = result.disclaimer || t("advice.disclaimer");
  const fullText = result.final_recommendation || "";
  const skipTypingRef = useRef(false);
  const [typedCount, setTypedCount] = useState(() => (typewriter ? 0 : fullText.length));
  const typing = typewriter && typedCount < fullText.length;
  const shownText = typing ? fullText.slice(0, typedCount) : fullText;

  useEffect(() => {
    if (!typewriter) {
      setTypedCount(fullText.length);
      return;
    }
    if (typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setTypedCount(fullText.length);
      onTypewriterDone?.();
      return;
    }
    if (!fullText) {
      onTypewriterDone?.();
      return;
    }
    setTypedCount(0);
    skipTypingRef.current = false;
    let count = 0;
    const step = fullText.length > 1200 ? 8 : fullText.length > 500 ? 4 : 2;
    const timer = window.setInterval(() => {
      if (skipTypingRef.current) {
        window.clearInterval(timer);
        return;
      }
      count = Math.min(fullText.length, count + step);
      setTypedCount(count);
      onTypewriterProgress?.();
      if (count >= fullText.length) {
        window.clearInterval(timer);
        onTypewriterDone?.();
      }
    }, 16);
    return () => window.clearInterval(timer);
    // Restart only when a new full answer is meant to type.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [typewriter, fullText]);

  const finishTyping = () => {
    if (!typing) return;
    skipTypingRef.current = true;
    setTypedCount(fullText.length);
    onTypewriterDone?.();
  };

  if (compact) {
    return (
      <div className={cn("grid gap-3.5", className)}>
        {result.image_diagnosis ? (
          <VisionDiagnosisCard diag={result.image_diagnosis} />
        ) : null}

        <div
          className="advice-markdown min-w-0 leading-relaxed"
          onClick={finishTyping}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") finishTyping();
          }}
          role={typing ? "button" : undefined}
          tabIndex={typing ? 0 : undefined}
          title={typing ? "Click to show the full answer" : undefined}
        >
          <SafeRecommendationRenderer text={shownText} />
          {typing ? (
            <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-primary align-middle" aria-hidden="true" />
          ) : null}
        </div>

        {escalation?.requires_escalation && !typing && (
          <div className="rounded-2xl border border-amber-500/30 bg-amber-50/70 p-3.5 dark:border-amber-500/20 dark:bg-amber-950/25 space-y-2.5">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-amber-900 dark:text-amber-200">
              <ShieldAlert className="size-4 text-amber-600 dark:text-amber-400 shrink-0" />
              <span>
                {escalation.urgency === "high" ? t("advice.expertHigh") : t("advice.expertMid")}
              </span>
            </div>

            {escalation.reason && (
              <p className="text-xs text-amber-950/90 dark:text-amber-100/90 leading-normal">
                {escalation.reason}
              </p>
            )}

            {escalation.safe_next_step && (
              <div className="text-xs text-foreground/80 bg-background/60 dark:bg-background/40 rounded-xl p-2.5 border border-amber-200/50 dark:border-amber-900/40">
                <strong className="text-foreground">{t("advice.safeStep")} </strong>
                {escalation.safe_next_step}
              </div>
            )}

            <div className="pt-1 flex flex-wrap items-center justify-between gap-2">
              <button
                type="button"
                onClick={() => setHelpDialogOpen(true)}
                className="inline-flex max-w-full items-center gap-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 px-3 py-1.5 text-left text-xs font-semibold text-white shadow-soft transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
              >
                <MapPin className="size-3.5 shrink-0" />
                <span className="min-w-0 break-words">
                  {escalation.action_label || t("advice.findExpert")}
                </span>
              </button>
            </div>
          </div>
        )}

        {onOpenScores && score && !typing && (
          <button
            type="button"
            onClick={onOpenScores}
            className="group inline-flex w-fit items-center gap-1.5 rounded-xl border border-primary/20 bg-primary/5 px-3 py-1.5 text-xs font-semibold text-primary transition-colors hover:bg-primary/10 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            {t("advice.scores")}
            <ChevronRight
              className="size-3.5 transition-transform group-hover:translate-x-0.5"
              aria-hidden="true"
            />
          </button>
        )}

        {!typing && (
          <div className="mt-1 flex items-start gap-1.5 border-t border-border/40 pt-2 text-[11px] leading-relaxed text-muted-foreground/80">
            <Info className="mt-0.5 size-3 shrink-0 text-muted-foreground/60" aria-hidden="true" />
            <span>{disclaimerText}</span>
          </div>
        )}

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
          label={t("advice.confidence")}
          value={`${confidencePct}%`}
          hint={t("advice.pipeline")}
          tone={confidencePct >= 70 ? "good" : confidencePct >= 45 ? "mid" : "low"}
        />
        {score && (
          <MetricPill
            icon={Sparkles}
            label={t("advice.decision")}
            value={`${pct(score.final_score)}/100`}
            hint={t("advice.composite")}
            tone={pct(score.final_score) >= 65 ? "good" : "mid"}
          />
        )}
        {result.structured_recommendation?.risk_level && (
          <MetricPill
            icon={ShieldAlert}
            label={t("advice.risk")}
            value={result.structured_recommendation.risk_level}
            tone="mid"
          />
        )}
      </div>

      {result.image_diagnosis ? (
        <VisionDiagnosisCard diag={result.image_diagnosis} />
      ) : null}

      <div className="advice-markdown min-w-0 rounded-2xl border border-border/70 bg-muted/30 p-3 leading-relaxed sm:p-4">
        <SafeRecommendationRenderer text={result.final_recommendation} />
      </div>

      {escalation?.requires_escalation && (
        <div className="rounded-2xl border border-amber-500/30 bg-amber-50/70 p-4 dark:border-amber-500/20 dark:bg-amber-950/25 space-y-3">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-amber-900 dark:text-amber-200">
            <ShieldAlert className="size-4 text-amber-600 dark:text-amber-400 shrink-0" />
            <span>
              {escalation.urgency === "high" ? t("advice.expertHighFull") : t("advice.expertMidFull")}
            </span>
          </div>

          {escalation.reason && (
            <p className="text-xs sm:text-sm text-amber-950/90 dark:text-amber-100/90 leading-normal">
              {escalation.reason}
            </p>
          )}

          {escalation.safe_next_step && (
            <div className="text-xs sm:text-sm text-foreground/90 bg-background/60 dark:bg-background/40 rounded-xl p-3 border border-amber-200/50 dark:border-amber-900/40">
              <strong className="text-foreground">{t("advice.safeStep")} </strong>
              {escalation.safe_next_step}
            </div>
          )}

          {escalation.sample_instructions && (
            <div className="text-xs text-muted-foreground flex items-center gap-1.5">
              <span>
                {t("advice.sample")} {escalation.sample_instructions}
              </span>
            </div>
          )}

          <div className="pt-1">
            <button
              type="button"
              onClick={() => setHelpDialogOpen(true)}
              className="inline-flex max-w-full items-center gap-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 px-4 py-2 text-left text-xs sm:text-sm font-semibold text-white shadow-soft transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
            >
              <MapPin className="size-4 shrink-0" />
              <span className="min-w-0 break-words">
                {escalation.action_label || t("advice.findExpert")}
              </span>
            </button>
          </div>
        </div>
      )}

      {score ? (
        <section className="grid gap-3" aria-label={t("chat.scoresAria")}>
          <h3 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            {t("advice.economics")}
          </h3>
          <div className="grid gap-2.5">
            <ScoreBar label={t("advice.agronomic")} value={score.agronomic_score} tone="leaf" />
            <ScoreBar label={t("advice.economic")} value={score.economic_score} tone="gold" />
            <ScoreBar label={t("advice.overall")} value={score.final_score} tone="soil" />
          </div>
          <ScoreMetrics score={score} />
        </section>
      ) : (
        <p className="rounded-xl border border-dashed border-border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
          {t("advice.noScore")}
        </p>
      )}

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
  const { t } = useI18n();
  return (
    <div className="mt-1 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
      <MiniStat
        icon={BadgeIndianRupee}
        label={t("advice.profit")}
        value={`₹${formatInr(score.expected_profit)}`}
      />
      <MiniStat icon={BadgeIndianRupee} label={t("advice.cost")} value={`₹${formatInr(score.input_cost)}`} />
      <MiniStat
        icon={Droplets}
        label={t("advice.water")}
        value={`${pct(score.water_risk)}%`}
      />
      <MiniStat
        icon={ShieldAlert}
        label={t("advice.disease")}
        value={
          score.disease_risk != null ? `${pct(score.disease_risk)}%` : t("advice.suppressed")
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
