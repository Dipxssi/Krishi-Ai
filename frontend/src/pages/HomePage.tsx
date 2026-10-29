import { Link } from "react-router-dom";
import {
  ArrowRight,
  Bot,
  Bug,
  IndianRupee,
  Leaf,
  MessagesSquare,
  ShieldCheck,
  Sparkle,
  Sprout,
} from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import { FeatureCard } from "@/components/FeatureCard";
import { AgentCard } from "@/components/AgentCard";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import heroFields from "@/assets/hero-fields.jpg";

export function HomePage() {
  const { t } = useI18n();

  const features = [
    { icon: Leaf, title: t("home.feat1Title"), description: t("home.feat1Body") },
    { icon: Bug, title: t("home.feat2Title"), description: t("home.feat2Body") },
    { icon: IndianRupee, title: t("home.feat3Title"), description: t("home.feat3Body") },
    { icon: Bot, title: t("home.feat4Title"), description: t("home.feat4Body") },
  ];

  const steps = [
    { icon: MessagesSquare, title: t("home.step1Title"), description: t("home.step1Body") },
    { icon: Sparkle, title: t("home.step2Title"), description: t("home.step2Body") },
    { icon: ShieldCheck, title: t("home.step3Title"), description: t("home.step3Body") },
  ];

  const agents = [
    { id: "crop", emoji: "🌱", name: t("agent.crop.name"), description: t("agent.crop.desc") },
    {
      id: "disease",
      emoji: "🐛",
      name: t("agent.disease.name"),
      description: t("agent.disease.desc"),
    },
    {
      id: "finance",
      emoji: "💰",
      name: t("agent.finance.name"),
      description: t("agent.finance.desc"),
    },
    {
      id: "general",
      emoji: "🤖",
      name: t("agent.general.name"),
      description: t("agent.general.desc"),
    },
  ] as const;

  const scrollToFeatures = () =>
    document.getElementById("features")?.scrollIntoView({ behavior: "smooth", block: "start" });

  return (
    <div className="min-h-screen bg-background">
      <Navbar />

      <section className="relative isolate overflow-hidden">
        <img
          src={heroFields}
          alt={t("home.heroAlt")}
          width={1920}
          height={1088}
          className="absolute inset-0 size-full object-cover"
        />
        <div aria-hidden="true" className="absolute inset-0 bg-gradient-hero" />
        <div className="relative mx-auto flex min-h-[92vh] max-w-7xl flex-col justify-center px-5 pt-32 pb-24 sm:px-8">
          <span className="inline-flex w-fit items-center gap-2 rounded-full border border-forest-foreground/25 bg-forest-foreground/10 px-4 py-1.5 text-xs font-semibold tracking-wide text-forest-foreground backdrop-blur">
            <Sprout className="size-3.5" aria-hidden="true" />
            {t("home.badge")}
          </span>

          <h1 className="mt-6 max-w-3xl text-3xl leading-[1.05] font-semibold text-forest-foreground sm:text-6xl lg:text-7xl">
            {t("home.hero1")}
            <br />
            {t("home.hero2")}
          </h1>

          <p className="mt-6 max-w-2xl text-base leading-relaxed text-forest-foreground/85 sm:text-lg">
            {t("home.heroBody")}
          </p>

          <div className="mt-9 flex flex-wrap items-center gap-3">
            <Button
              asChild
              size="lg"
              className="h-13 rounded-full bg-gradient-leaf px-7 text-base font-semibold shadow-lift hover:opacity-95"
            >
              <Link to="/auth">
                {t("nav.getStarted")}
                <ArrowRight className="size-4" />
              </Link>
            </Button>
            <Button
              size="lg"
              variant="outline"
              onClick={scrollToFeatures}
              className="h-13 rounded-full border-forest-foreground/35 bg-forest-foreground/10 px-7 text-base font-semibold text-forest-foreground backdrop-blur hover:bg-forest-foreground/20 hover:text-forest-foreground"
            >
              {t("home.explore")}
            </Button>
          </div>

          <p className="mt-8 flex items-center gap-2 text-sm text-forest-foreground/70">
            <ShieldCheck className="size-4" aria-hidden="true" />
            {t("home.accessible")}
          </p>
        </div>
      </section>

      <section id="features" className="scroll-mt-20 bg-background py-20 sm:py-28">
        <div className="mx-auto max-w-7xl px-5 sm:px-8">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-semibold text-foreground sm:text-4xl">
              {t("home.featuresTitle")}
            </h2>
            <p className="mt-4 text-base text-muted-foreground">{t("home.featuresBody")}</p>
          </div>
          <div className="mt-14 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {features.map((f) => (
              <FeatureCard key={f.title} {...f} />
            ))}
          </div>
        </div>
      </section>

      <section id="how-it-works" className="scroll-mt-20 bg-cream py-20 sm:py-28">
        <div className="mx-auto max-w-7xl px-5 sm:px-8">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-semibold text-foreground sm:text-4xl">
              {t("home.howTitle")}
            </h2>
            <p className="mt-4 text-base text-muted-foreground">{t("home.howBody")}</p>
          </div>

          <ol className="relative mt-14 grid gap-6 md:grid-cols-3">
            <span
              aria-hidden="true"
              className="absolute top-16 right-[16%] left-[16%] hidden h-px bg-border md:block"
            />
            {steps.map((step, i) => (
              <li
                key={step.title}
                className="relative rounded-3xl border border-border bg-card p-7 text-center shadow-soft transition-transform hover:-translate-y-1"
              >
                <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-gradient-leaf shadow-soft">
                  <step.icon className="size-6 text-primary-foreground" aria-hidden="true" />
                </span>
                <p className="mt-4 text-xs font-semibold tracking-widest text-primary uppercase">
                  {t("home.step", { n: i + 1 })}
                </p>
                <h3 className="mt-1 text-xl font-semibold text-foreground">{step.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{step.description}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section id="about" className="scroll-mt-20 bg-background py-20 sm:py-28">
        <div className="mx-auto max-w-7xl px-5 sm:px-8">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-semibold text-foreground sm:text-4xl">
              {t("home.aboutTitle")}
            </h2>
            <p className="mt-4 text-base text-muted-foreground">{t("home.aboutBody")}</p>
          </div>

          <div className="mt-14 grid items-center gap-8 lg:grid-cols-[1fr_auto_1fr]">
            <div className="grid gap-4">
              <AgentCard {...agents[0]} />
              <AgentCard {...agents[1]} />
            </div>

            <div className="relative mx-auto grid size-44 place-items-center rounded-full bg-gradient-forest text-center shadow-lift">
              <span
                aria-hidden="true"
                className="absolute inset-0 animate-pulse rounded-full border border-leaf/40"
              />
              <div>
                <Sprout className="mx-auto size-8 text-leaf" aria-hidden="true" />
                <p className="mt-2 font-display text-lg font-semibold text-forest-foreground">
                  Krishi AI
                </p>
                <p className="text-xs text-forest-foreground/70">{t("home.router")}</p>
              </div>
            </div>

            <div className="grid gap-4">
              <AgentCard {...agents[2]} />
              <AgentCard {...agents[3]} />
            </div>
          </div>
        </div>
      </section>

      <section className="px-5 pb-20 sm:px-8 sm:pb-28">
        <div className="mx-auto max-w-6xl overflow-hidden rounded-[2rem] bg-gradient-forest px-7 py-16 text-center shadow-lift sm:px-16">
          <h2 className="mx-auto max-w-2xl text-3xl font-semibold text-forest-foreground sm:text-4xl">
            {t("home.ctaTitle")}
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-base text-forest-foreground/80">{t("home.ctaBody")}</p>
          <Button
            asChild
            size="lg"
            className="mt-8 h-13 rounded-full bg-gradient-leaf px-8 text-base font-semibold shadow-lift hover:opacity-95"
          >
            <Link to="/auth">
              {t("home.ctaButton")}
              <ArrowRight className="size-4" />
            </Link>
          </Button>
        </div>
      </section>

      <Footer />
    </div>
  );
}
