import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { AuthForm } from "@/components/AuthForm";
import { Logo } from "@/components/Logo";
import { useI18n } from "@/hooks/useI18n";
import authFarmer from "@/assets/auth-farmer.jpg";

export function AuthPage() {
  const { t } = useI18n();

  return (
    <main className="grid min-h-screen lg:grid-cols-2">
      <section className="relative hidden isolate overflow-hidden lg:block">
        <img
          src={authFarmer}
          alt={t("auth.farmerAlt")}
          width={1024}
          height={1536}
          className="absolute inset-0 size-full object-cover"
        />
        <div aria-hidden="true" className="absolute inset-0 bg-gradient-hero" />
        <div className="relative flex h-full flex-col justify-between p-12">
          <Logo tone="onDark" size="lg" />
          <div>
            <h2 className="max-w-md text-4xl leading-tight font-semibold text-forest-foreground">
              {t("auth.panelTitle")}
            </h2>
            <p className="mt-4 max-w-sm text-base text-forest-foreground/80">{t("auth.panelBody")}</p>
          </div>
        </div>
      </section>

      <section className="flex flex-col bg-background px-5 py-8 sm:px-10">
        <div className="flex items-center justify-between">
          <Link to="/" aria-label={t("nav.homeAria")}>
            <Logo />
          </Link>
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 rounded-full px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <ArrowLeft className="size-4" />
            {t("auth.backHome")}
          </Link>
        </div>

        <div className="flex flex-1 items-center justify-center py-10">
          <AuthForm />
        </div>
      </section>
    </main>
  );
}
