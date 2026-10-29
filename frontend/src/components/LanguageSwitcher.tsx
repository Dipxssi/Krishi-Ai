import { LOCALES, type Locale } from "@/lib/i18n";
import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";

interface LanguageSwitcherProps {
  className?: string;
  tone?: "light" | "dark";
}

export function LanguageSwitcher({ className, tone = "light" }: LanguageSwitcherProps) {
  const { locale, setLocale, t } = useI18n();

  return (
    <label className={cn("inline-flex items-center gap-2", className)}>
      <span className="sr-only">{t("lang.switch")}</span>
      <select
        value={locale}
        onChange={(e) => setLocale(e.target.value as Locale)}
        aria-label={t("lang.switch")}
        className={cn(
          "h-9 rounded-full border px-3 text-xs font-semibold outline-none focus-visible:ring-2",
          tone === "dark"
            ? "border-forest-foreground/30 bg-forest-foreground/10 text-forest-foreground focus-visible:ring-leaf"
            : "border-border bg-card text-foreground focus-visible:ring-ring",
        )}
      >
        {LOCALES.map((item) => (
          <option key={item.id} value={item.id}>
            {item.nativeLabel}
          </option>
        ))}
      </select>
    </label>
  );
}
