import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { Menu, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Logo } from "@/components/Logo";

const NAV_LINKS = [
  { label: "Home", target: "top" },
  { label: "Features", target: "features" },
  { label: "About", target: "about" },
  { label: "How It Works", target: "how-it-works" },
];

export function Navbar() {
  const [open, setOpen] = useState(false);

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
        className="mx-auto flex max-w-7xl items-center justify-between px-5 py-5 sm:px-8"
      >
        <Link to="/" aria-label="Krishi AI home">
          <Logo tone="onDark" />
        </Link>

        <ul className="hidden items-center gap-1 md:flex">
          {NAV_LINKS.map((link) => (
            <li key={link.label}>
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
          <Button
            asChild
            variant="ghost"
            className="rounded-full text-forest-foreground hover:bg-forest-foreground/10 hover:text-forest-foreground"
          >
            <Link to="/auth">Sign In</Link>
          </Button>
          <Button asChild className="rounded-full bg-gradient-leaf shadow-soft hover:opacity-95">
            <Link to="/auth">Get Started</Link>
          </Button>
        </div>

        <button
          type="button"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
          className="grid size-10 place-items-center rounded-xl border border-forest-foreground/25 text-forest-foreground md:hidden"
        >
          {open ? <X className="size-5" /> : <Menu className="size-5" />}
        </button>
      </nav>

      {open && (
        <div className="mx-4 animate-in slide-in-from-top-2 rounded-3xl border border-border bg-card p-4 shadow-lift md:hidden">
          <ul className="grid gap-1">
            {NAV_LINKS.map((link) => (
              <li key={link.label}>
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
              <Link to="/auth">Sign In</Link>
            </Button>
            <Button asChild className="rounded-xl bg-gradient-leaf">
              <Link to="/auth">Get Started</Link>
            </Button>
          </div>
        </div>
      )}
    </header>
  );
}
