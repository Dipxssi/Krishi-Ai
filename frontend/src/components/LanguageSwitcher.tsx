import { Check, ChevronDown } from "lucide-react";
import { LOCALES, type Locale } from "@/lib/i18n";
import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface LanguageSwitcherProps {
  className?: string;
  tone?: "light" | "dark";
}

export function LanguageSwitcher({ className, tone = "light" }: LanguageSwitcherProps) {
  const { locale, setLocale, t } = useI18n();
  const current = LOCALES.find((item) => item.id === locale) ?? LOCALES[0];

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label={t("lang.switch")}
          className={cn(
            "inline-flex h-9 items-center gap-1.5 rounded-full border px-3 text-xs font-semibold outline-none transition-colors",
            "focus-visible:ring-2 focus-visible:ring-offset-0",
            tone === "dark"
              ? "border-forest-foreground/30 bg-forest-foreground/10 text-forest-foreground hover:bg-forest-foreground/15 focus-visible:ring-leaf"
              : "border-border bg-card text-foreground hover:bg-muted focus-visible:ring-ring",
            className,
          )}
        >
          <span>{current.nativeLabel}</span>
          <ChevronDown className="size-3.5 opacity-70" aria-hidden="true" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        sideOffset={6}
        className="z-[80] min-w-[9.5rem] rounded-xl border border-border bg-popover p-1 text-popover-foreground shadow-lift"
      >
        {LOCALES.map((item) => {
          const selected = item.id === locale;
          return (
            <DropdownMenuItem
              key={item.id}
              onSelect={() => setLocale(item.id as Locale)}
              className={cn(
                "cursor-pointer rounded-lg px-2.5 py-2 text-sm font-medium text-popover-foreground",
                "focus:bg-accent focus:text-accent-foreground",
                selected && "bg-primary/10 text-foreground",
              )}
            >
              <span className="flex-1">{item.nativeLabel}</span>
              {selected ? <Check className="size-3.5 text-primary" aria-hidden="true" /> : null}
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
