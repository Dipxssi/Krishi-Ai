import { useState } from "react";
import { Languages } from "lucide-react";
import { Button } from "@/components/ui/button";
import { LOCALES, type Locale } from "@/lib/i18n";
import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";

/** First-visit language chooser — covers all UI copy after selection. */
export function LanguageGate() {
  const { chosen, locale, setLocale, t } = useI18n();
  const [pending, setPending] = useState<Locale>(locale);

  if (chosen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-background/80 p-5 backdrop-blur-md">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="lang-gate-title"
        className="w-full max-w-md rounded-[1.75rem] border border-border bg-card p-6 shadow-lift sm:p-8"
      >
        <span className="grid size-12 place-items-center rounded-2xl bg-gradient-leaf text-primary-foreground shadow-soft">
          <Languages className="size-6" aria-hidden="true" />
        </span>
        <h1 id="lang-gate-title" className="mt-5 font-display text-2xl font-semibold text-foreground">
          {t("lang.title")}
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{t("lang.subtitle")}</p>

        <div className="mt-6 grid gap-2" role="radiogroup" aria-label={t("lang.switch")}>
          {LOCALES.map((item) => {
            const selected = pending === item.id;
            return (
              <button
                key={item.id}
                type="button"
                role="radio"
                aria-checked={selected}
                onClick={() => setPending(item.id)}
                className={cn(
                  "flex items-center justify-between rounded-2xl border px-4 py-3 text-left transition-colors",
                  selected
                    ? "border-primary/40 bg-primary/10 text-foreground"
                    : "border-border bg-background text-foreground hover:bg-muted/60",
                )}
              >
                <span>
                  <span className="block text-sm font-semibold">{item.nativeLabel}</span>
                  <span className="block text-xs text-muted-foreground">{item.englishLabel}</span>
                </span>
                <span
                  className={cn(
                    "grid size-5 place-items-center rounded-full border",
                    selected ? "border-primary bg-primary text-primary-foreground" : "border-border",
                  )}
                >
                  {selected ? <span className="size-2 rounded-full bg-primary-foreground" /> : null}
                </span>
              </button>
            );
          })}
        </div>

        <Button
          className="mt-6 h-12 w-full rounded-2xl bg-gradient-leaf text-base font-semibold shadow-soft"
          onClick={() => setLocale(pending)}
        >
          {t("lang.continue")}
        </Button>
      </div>
    </div>
  );
}
