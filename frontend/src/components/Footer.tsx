import { Logo } from "@/components/Logo";

const LINKS = [
  { label: "Home", target: "top" },
  { label: "Features", target: "features" },
  { label: "About", target: "about" },
  { label: "How It Works", target: "how-it-works" },
];

export function Footer() {
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
            <p className="mt-4 text-sm text-forest-foreground/75">
              AI-powered assistance for smarter agriculture.
            </p>
          </div>
          <nav aria-label="Footer navigation">
            <h3 className="text-sm font-semibold tracking-wide text-forest-foreground/90 uppercase">
              Explore
            </h3>
            <ul className="mt-4 grid gap-2">
              {LINKS.map((link) => (
                <li key={link.label}>
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
          © 2026 Krishi AI. All rights reserved.
        </div>
      </div>
    </footer>
  );
}
