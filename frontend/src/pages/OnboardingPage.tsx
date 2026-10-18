import { Navigate, useNavigate } from "react-router-dom";
import { CheckCircle2, Leaf, ShieldCheck } from "lucide-react";
import { FarmProfileForm } from "@/components/FarmProfileForm";
import { Logo } from "@/components/Logo";
import { getAuthUser, isAuthenticated } from "@/lib/authSession";
import { isFarmProfileComplete } from "@/lib/farmProfile";

const STEPS = [
  { label: "Account", done: true },
  { label: "Farm profile", done: false },
  { label: "Ask Krishi AI", done: false },
];

export function OnboardingPage() {
  const navigate = useNavigate();
  const user = getAuthUser();

  if (!isAuthenticated()) {
    return <Navigate to="/auth" replace />;
  }
  if (isFarmProfileComplete()) {
    return <Navigate to="/chat" replace />;
  }

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
        <header className="flex items-center justify-between">
          <Logo size="md" />
          {user?.name && (
            <p className="rounded-full border border-border/70 bg-card/80 px-3 py-1.5 text-xs font-medium text-muted-foreground backdrop-blur">
              Welcome, <span className="text-foreground">{user.name.split(" ")[0]}</span>
            </p>
          )}
        </header>

        <div className="mt-10 grid flex-1 items-center gap-10 lg:mt-0 lg:grid-cols-[1fr_1.05fr] lg:gap-16">
          <section className="animate-in fade-in slide-in-from-left-3 duration-500">
            <p className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-card/70 px-3 py-1 text-xs font-semibold tracking-wide text-primary uppercase">
              <Leaf className="size-3.5" aria-hidden="true" />
              Step 2 of 3
            </p>
            <h1 className="mt-5 max-w-md font-display text-4xl leading-tight font-semibold text-foreground sm:text-5xl">
              Tell us about your farm
            </h1>
            <p className="mt-4 max-w-md text-base leading-relaxed text-muted-foreground">
              A short profile helps Krishi AI give advice that fits your land, crop, and conditions —
              before you ask your first question.
            </p>

            <ol className="mt-8 grid max-w-sm gap-3">
              {STEPS.map((step, index) => {
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
              Used only to personalize recommendations. You can update this anytime in Settings.
            </p>
          </section>

          <section className="animate-in fade-in slide-in-from-bottom-3 duration-500">
            <div className="rounded-[2rem] border border-border/80 bg-card p-6 shadow-lift sm:p-8">
              <div className="mb-6 border-b border-border/70 pb-5">
                <h2 className="text-xl font-semibold text-foreground">Farm profile</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Required fields are marked. Soil type is optional.
                </p>
              </div>
              <FarmProfileForm
                submitLabel="Continue to Krishi AI"
                onSaved={() => navigate("/chat", { replace: true })}
              />
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}
