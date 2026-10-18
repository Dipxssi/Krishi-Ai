import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowLeft } from "lucide-react";
import { AuthForm } from "@/components/AuthForm";
import { Logo } from "@/components/Logo";
import authFarmer from "@/assets/auth-farmer.jpg";

export const Route = createFileRoute("/auth")({
  head: () => ({
    meta: [
      { title: "Sign In or Sign Up — Krishi AI" },
      {
        name: "description",
        content:
          "Access Krishi AI to get agricultural and financial assistance from specialized AI agents.",
      },
      { property: "og:title", content: "Sign In or Sign Up — Krishi AI" },
      {
        property: "og:description",
        content: "Create your Krishi AI account and start asking farming questions.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: AuthPage,
});

function AuthPage() {
  return (
    <main className="grid min-h-screen lg:grid-cols-2">
      <section className="relative hidden isolate overflow-hidden lg:block">
        <img
          src={authFarmer}
          alt="Farmer holding rice seedlings in a green paddy field"
          width={1024}
          height={1536}
          className="absolute inset-0 size-full object-cover"
        />
        <div aria-hidden="true" className="absolute inset-0 bg-gradient-hero" />
        <div className="relative flex h-full flex-col justify-between p-12">
          <Logo tone="onDark" size="lg" />
          <div>
            <h2 className="max-w-md text-4xl leading-tight font-semibold text-forest-foreground">
              Empowering Farmers with Intelligent AI
            </h2>
            <p className="mt-4 max-w-sm text-base text-forest-foreground/80">
              Get simple, accessible assistance for agricultural and financial challenges.
            </p>
          </div>
        </div>
      </section>

      <section className="flex flex-col bg-background px-5 py-8 sm:px-10">
        <div className="flex items-center justify-between">
          <Link to="/" aria-label="Krishi AI home">
            <Logo />
          </Link>
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 rounded-full px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <ArrowLeft className="size-4" />
            Back home
          </Link>
        </div>

        <div className="flex flex-1 items-center justify-center py-10">
          <AuthForm />
        </div>
      </section>
    </main>
  );
}
