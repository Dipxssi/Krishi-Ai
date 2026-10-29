import { useState } from "react";
import { Link } from "react-router-dom";
import { Menu, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { Logo } from "@/components/Logo";
import { useI18n } from "@/hooks/useI18n";

export function Navbar() {
  const [open, setOpen] = useState(false);
  const { t } = useI18n();

  const navLinks = [
    { label: t("nav.home"), target: "top" },
    { label: t("nav.features"), target: "features" },
    { label: t("nav.about"), target: "about" },
    { label: t("nav.how"), target: "how-it-works" },
  ];

  const scrollTo = (id: string) => {
    setOpen(false);
    if (id === "top") {
      window.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <header className="absolute inset-x-0 top-0 z-50">
      <nav
        aria-label="Main navigation"
        className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-5 py-5 sm:px-8"
      >
        <Link to="/" aria-label={t("nav.homeAria")}>
          <Logo tone="onDark" />
        </Link>

        <ul className="hidden items-center gap-1 md:flex">
          {navLinks.map((link) => (
            <li key={link.target}>
              <button
                type="button"
                onClick={() => scrollTo(link.target)}
                className="rounded-full px-4 py-2 text-sm font-medium text-forest-foreground/85 transition-colors hover:bg-forest-foreground/10 hover:text-forest-foreground focus-visible:ring-2 focus-visible:ring-leaf focus-visible:outline-none"
              >
                {link.label}
              </button>
            </li>
          ))}
        </ul>

        <div className="hidden items-center gap-2 md:flex">
          <LanguageSwitcher tone="dark" />
          <Button
            asChild
            variant="ghost"
            className="rounded-full text-forest-foreground hover:bg-forest-foreground/10 hover:text-forest-foreground"
          >
            <Link to="/auth">{t("nav.signIn")}</Link>
          </Button>
          <Button asChild className="rounded-full bg-gradient-leaf shadow-soft hover:opacity-95">
            <Link to="/auth">{t("nav.getStarted")}</Link>
          </Button>
        </div>

        <div className="flex items-center gap-2 md:hidden">
          <LanguageSwitcher tone="dark" />
          <button
            type="button"
            aria-label={open ? t("nav.closeMenu") : t("nav.openMenu")}
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
            className="grid size-10 place-items-center rounded-xl border border-forest-foreground/25 text-forest-foreground"
          >
            {open ? <X className="size-5" /> : <Menu className="size-5" />}
          </button>
        </div>
      </nav>

      {open && (
        <div className="mx-4 animate-in slide-in-from-top-2 rounded-3xl border border-border bg-card p-4 shadow-lift md:hidden">
          <ul className="grid gap-1">
            {navLinks.map((link) => (
              <li key={link.target}>
                <button
                  type="button"
                  onClick={() => scrollTo(link.target)}
                  className="w-full rounded-xl px-4 py-3 text-left text-sm font-medium text-foreground hover:bg-muted"
                >
                  {link.label}
                </button>
              </li>
            ))}
          </ul>
          <div className="mt-3 grid gap-2">
            <Button asChild variant="outline" className="rounded-xl">
              <Link to="/auth">{t("nav.signIn")}</Link>
            </Button>
            <Button asChild className="rounded-xl bg-gradient-leaf">
              <Link to="/auth">{t("nav.getStarted")}</Link>
            </Button>
          </div>
        </div>
      )}
    </header>
  );
}
