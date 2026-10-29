import { Link } from "react-router-dom";
import { ArrowLeft, Radio, Smartphone, Wifi } from "lucide-react";
import { Button } from "@/components/ui/button";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { useApiConnection } from "@/hooks/useApiConnection";
import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";

export function FieldRelayPage() {
  const { status } = useApiConnection({ pollMs: 10_000 });
  const { t } = useI18n();

  const steps = [
    { icon: Wifi, title: t("relay.step1Title"), body: t("relay.step1Body") },
    { icon: Smartphone, title: t("relay.step2Title"), body: t("relay.step2Body") },
    { icon: Radio, title: t("relay.step3Title"), body: t("relay.step3Body") },
  ];

  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto max-w-2xl px-5 py-8 sm:px-8">
        <div className="mb-6 flex items-center justify-between gap-3">
          <Button asChild variant="ghost" className="-ml-2 rounded-full">
            <Link to="/chat">
              <ArrowLeft className="size-4" />
              {t("relay.back")}
            </Link>
          </Button>
          <LanguageSwitcher />
        </div>

        <p className="text-sm font-medium text-primary">{t("relay.badge")}</p>
        <h1 className="mt-2 font-serif text-3xl font-semibold tracking-tight text-foreground">
          {t("relay.title")}
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground sm:text-base">
          {t("relay.body")}
        </p>

        <div
          className={cn(
            "mt-6 rounded-2xl border px-4 py-3 text-sm",
            status === "online" && "border-primary/30 bg-primary/5 text-foreground",
            status === "offline" && "border-destructive/30 bg-destructive/5 text-foreground",
            (status === "checking" || status === "sending") &&
              "border-border bg-muted/40 text-muted-foreground",
          )}
        >
          {status === "online" && t("relay.online")}
          {status === "offline" && t("relay.offline")}
          {status === "checking" && t("relay.checking")}
          {status === "sending" && t("relay.sending")}
        </div>

        <ol className="mt-10 grid gap-6">
          {steps.map((step, index) => (
            <li key={step.title} className="flex gap-4">
              <span className="grid size-11 shrink-0 place-items-center rounded-2xl bg-gradient-leaf text-primary-foreground shadow-soft">
                <step.icon className="size-5" aria-hidden="true" />
              </span>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {t("home.step", { n: index + 1 })}
                </p>
                <h2 className="mt-1 text-base font-semibold text-foreground">{step.title}</h2>
                <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{step.body}</p>
              </div>
            </li>
          ))}
        </ol>

        <div className="mt-10 rounded-2xl border border-border bg-card p-5 shadow-soft">
          <h2 className="text-base font-semibold text-foreground">{t("relay.shopTitle")}</h2>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{t("relay.shopBody")}</p>
          <pre className="mt-3 overflow-x-auto rounded-xl bg-muted px-4 py-3 text-xs leading-relaxed text-foreground">
{`cd backend
uv run python scripts/field_relay_status.py`}
          </pre>
          <p className="mt-3 text-sm text-muted-foreground">{t("relay.shopHint")}</p>
        </div>

        <div className="mt-8 flex flex-wrap gap-3">
          <Button asChild className="rounded-full bg-gradient-leaf shadow-soft">
            <Link to="/chat">{t("relay.openChat")}</Link>
          </Button>
          <Button asChild variant="outline" className="rounded-full">
            <Link to="/">{t("nav.home")}</Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
