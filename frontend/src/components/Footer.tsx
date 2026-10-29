import { Logo } from "@/components/Logo";
import { useI18n } from "@/hooks/useI18n";

export function Footer() {
  const { t } = useI18n();
  const links = [
    { label: t("nav.home"), target: "top" },
    { label: t("nav.features"), target: "features" },
    { label: t("nav.about"), target: "about" },
    { label: t("nav.how"), target: "how-it-works" },
  ];

  const scrollTo = (id: string) => {
    if (id === "top") {
      window.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <footer className="bg-gradient-forest text-forest-foreground">
      <div className="mx-auto max-w-7xl px-5 py-14 sm:px-8">
        <div className="flex flex-col gap-10 md:flex-row md:items-start md:justify-between">
          <div className="max-w-sm">
            <Logo tone="onDark" />
            <p className="mt-4 text-sm text-forest-foreground/75">{t("footer.tagline")}</p>
          </div>
          <nav aria-label="Footer navigation">
            <h3 className="text-sm font-semibold tracking-wide text-forest-foreground/90 uppercase">
              {t("footer.explore")}
            </h3>
            <ul className="mt-4 grid gap-2">
              {links.map((link) => (
                <li key={link.target}>
                  <button
                    type="button"
                    onClick={() => scrollTo(link.target)}
                    className="text-sm text-forest-foreground/75 transition-colors hover:text-forest-foreground"
                  >
                    {link.label}
                  </button>
                </li>
              ))}
            </ul>
          </nav>
        </div>
        <div className="mt-12 border-t border-forest-foreground/15 pt-6 text-xs text-forest-foreground/60">
          {t("footer.rights", { year: 2026 })}
        </div>
      </div>
    </footer>
  );
}
