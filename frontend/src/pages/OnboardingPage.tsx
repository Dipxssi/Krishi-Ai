import { Navigate, useNavigate } from "react-router-dom";
import { CheckCircle2, Leaf, ShieldCheck } from "lucide-react";
import { FarmProfileForm } from "@/components/FarmProfileForm";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { Logo } from "@/components/Logo";
import { useI18n } from "@/hooks/useI18n";
import { getAuthUser, isAuthenticated } from "@/lib/authSession";
import { hasRequiredFarmFields, isFarmProfileComplete, markOnboardingComplete } from "@/lib/farmProfile";

export function OnboardingPage() {
  const navigate = useNavigate();
  const { t } = useI18n();
  const user = getAuthUser();

  if (!isAuthenticated()) {
    return <Navigate to="/auth" replace />;
  }
  if (isFarmProfileComplete() || hasRequiredFarmFields()) {
    if (user?.farmer_id && hasRequiredFarmFields()) {
      markOnboardingComplete(user.farmer_id);
    }
    return <Navigate to="/chat" replace />;
  }

  const steps = [
    { label: t("onboard.stepAccount"), done: true },
    { label: t("onboard.stepFarm"), done: false },
    { label: t("onboard.stepAsk"), done: false },
  ];

  return (
    <main className="relative min-h-screen overflow-hidden bg-cream">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,_hsl(142_40%_88%_/_0.9),_transparent_55%),radial-gradient(ellipse_at_bottom_right,_hsl(48_50%_92%),_transparent_45%)]"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-24 -right-16 size-72 rounded-full bg-leaf/15 blur-3xl"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-20 -left-10 size-80 rounded-full bg-primary/10 blur-3xl"
      />

      <div className="relative mx-auto flex min-h-screen w-full max-w-6xl flex-col px-5 py-8 sm:px-8 lg:py-12">
        <header className="flex items-center justify-between gap-3">
          <Logo size="md" />
          <div className="flex items-center gap-2">
            <LanguageSwitcher />
            {user?.name && (
              <p className="rounded-full border border-border/70 bg-card/80 px-3 py-1.5 text-xs font-medium text-muted-foreground backdrop-blur">
                {t("onboard.welcome", { name: user.name.split(" ")[0] })}
              </p>
            )}
          </div>
        </header>

        <div className="mt-10 grid flex-1 items-center gap-10 lg:mt-0 lg:grid-cols-[1fr_1.05fr] lg:gap-16">
          <section className="animate-in fade-in slide-in-from-left-3 duration-500">
            <p className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-card/70 px-3 py-1 text-xs font-semibold tracking-wide text-primary uppercase">
              <Leaf className="size-3.5" aria-hidden="true" />
              {t("onboard.stepOf", { n: 2, total: 3 })}
            </p>
            <h1 className="mt-5 max-w-md font-display text-3xl leading-tight font-semibold text-foreground sm:text-5xl">
              {t("onboard.title")}
            </h1>
            <p className="mt-4 max-w-md text-base leading-relaxed text-muted-foreground">
              {t("onboard.body")}
            </p>

            <ol className="mt-8 grid max-w-sm gap-3">
              {steps.map((step, index) => {
                const current = index === 1;
                return (
                  <li
                    key={step.label}
                    className={
                      current
                        ? "flex items-center gap-3 rounded-2xl border border-primary/25 bg-card px-4 py-3 shadow-soft"
                        : "flex items-center gap-3 rounded-2xl border border-border/60 bg-card/60 px-4 py-3 backdrop-blur"
                    }
                  >
                    <span
                      className={
                        current
                          ? "grid size-8 place-items-center rounded-full bg-gradient-leaf text-xs font-bold text-primary-foreground"
                          : step.done
                            ? "grid size-8 place-items-center rounded-full bg-primary/10 text-primary"
                            : "grid size-8 place-items-center rounded-full bg-muted text-xs font-bold text-muted-foreground"
                      }
                    >
                      {step.done ? <CheckCircle2 className="size-4" /> : index + 1}
                    </span>
                    <span
                      className={
                        current
                          ? "text-sm font-semibold text-foreground"
                          : "text-sm font-medium text-muted-foreground"
                      }
                    >
                      {step.label}
                    </span>
                  </li>
                );
              })}
            </ol>

            <p className="mt-8 flex items-start gap-2 text-sm text-muted-foreground">
              <ShieldCheck className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
              {t("onboard.privacy")}
            </p>
          </section>

          <section className="animate-in fade-in slide-in-from-bottom-3 duration-500">
            <div className="rounded-[2rem] border border-border/80 bg-card p-6 shadow-lift sm:p-8">
              <div className="mb-6 border-b border-border/70 pb-5">
                <h2 className="text-xl font-semibold text-foreground">{t("onboard.formTitle")}</h2>
                <p className="mt-1 text-sm text-muted-foreground">{t("onboard.formHint")}</p>
              </div>
              <FarmProfileForm
                submitLabel={t("onboard.continue")}
                onSaved={() => navigate("/chat", { replace: true })}
              />
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}
