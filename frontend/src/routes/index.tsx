import { createFileRoute, Link } from "@tanstack/react-router";
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
import { AGENTS } from "@/data/mockChats";
import heroFields from "@/assets/hero-fields.jpg";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Krishi AI — Multi-Agent AI Assistant for Farmers" },
      {
        name: "description",
        content:
          "Krishi AI is a multi-agent AI platform that helps farmers solve agricultural and financial problems with clear, practical assistance.",
      },
      { property: "og:title", content: "Krishi AI — Smarter Farming, Better Decisions" },
      {
        property: "og:description",
        content:
          "Crop guidance, disease and pest support, and agricultural financial help from specialized AI agents.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Home,
});

const FEATURES = [
  {
    icon: Leaf,
    title: "Agricultural Assistance",
    description:
      "Get practical guidance for crop selection, cultivation, fertilizers, irrigation and common farming challenges.",
  },
  {
    icon: Bug,
    title: "Crop Disease & Pest Support",
    description:
      "Understand common crop diseases and pest problems and receive easy-to-follow recommendations.",
  },
  {
    icon: IndianRupee,
    title: "Financial Guidance",
    description:
      "Get assistance with agricultural loans, financial planning, government schemes and farming-related expenses.",
  },
  {
    icon: Bot,
    title: "Multi-Agent AI",
    description:
      "Multiple specialized AI agents work together to provide more useful and relevant assistance.",
  },
];

const STEPS = [
  {
    icon: MessagesSquare,
    title: "Ask",
    description: "The farmer describes their agricultural or financial problem in simple words.",
  },
  {
    icon: Sparkle,
    title: "Analyze",
    description: "The appropriate AI agent analyzes the problem and the details provided.",
  },
  {
    icon: ShieldCheck,
    title: "Assist",
    description: "Krishi AI provides a clear, useful response with practical next steps.",
  },
];

function Home() {
  const scrollToFeatures = () =>
    document.getElementById("features")?.scrollIntoView({ behavior: "smooth", block: "start" });

  return (
    <div className="min-h-screen bg-background">
      <Navbar />

      {/* HERO */}
      <section className="relative isolate overflow-hidden">
        <img
          src={heroFields}
          alt="Green crop field in an Indian farmland at sunrise"
          width={1920}
          height={1088}
          className="absolute inset-0 size-full object-cover"
        />
        <div aria-hidden="true" className="absolute inset-0 bg-gradient-hero" />
        <div className="relative mx-auto flex min-h-[92vh] max-w-7xl flex-col justify-center px-5 pt-32 pb-24 sm:px-8">
          <span className="inline-flex w-fit items-center gap-2 rounded-full border border-forest-foreground/25 bg-forest-foreground/10 px-4 py-1.5 text-xs font-semibold tracking-wide text-forest-foreground backdrop-blur">
            <Sprout className="size-3.5" aria-hidden="true" />
            AI-Powered Agriculture
          </span>

          <h1 className="mt-6 max-w-3xl text-4xl leading-[1.05] font-semibold text-forest-foreground sm:text-6xl lg:text-7xl">
            Smarter Farming.
            <br />
            Better Decisions.
          </h1>

          <p className="mt-6 max-w-2xl text-base leading-relaxed text-forest-foreground/85 sm:text-lg">
            Krishi AI is a multi-agent AI platform that helps farmers solve agricultural and
            financial problems with intelligent, easy-to-understand assistance.
          </p>

          <div className="mt-9 flex flex-wrap items-center gap-3">
            <Button
              asChild
              size="lg"
              className="h-13 rounded-full bg-gradient-leaf px-7 text-base font-semibold shadow-lift hover:opacity-95"
            >
              <Link to="/auth">
                Get Started
                <ArrowRight className="size-4" />
              </Link>
            </Button>
            <Button
              size="lg"
              variant="outline"
              onClick={scrollToFeatures}
              className="h-13 rounded-full border-forest-foreground/35 bg-forest-foreground/10 px-7 text-base font-semibold text-forest-foreground backdrop-blur hover:bg-forest-foreground/20 hover:text-forest-foreground"
            >
              Explore Krishi AI
            </Button>
          </div>

          <p className="mt-8 flex items-center gap-2 text-sm text-forest-foreground/70">
            <ShieldCheck className="size-4" aria-hidden="true" />
            Built to make agricultural knowledge more accessible.
          </p>
        </div>
      </section>

      {/* FEATURES */}
      <section id="features" className="scroll-mt-20 bg-background py-20 sm:py-28">
        <div className="mx-auto max-w-7xl px-5 sm:px-8">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-semibold text-foreground sm:text-4xl">
              Everything a Farmer Needs, In One Place
            </h2>
            <p className="mt-4 text-base text-muted-foreground">
              Krishi AI brings specialized AI assistance together to help farmers make better
              decisions.
            </p>
          </div>
          <div className="mt-14 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {FEATURES.map((f) => (
              <FeatureCard key={f.title} {...f} />
            ))}
          </div>
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section id="how-it-works" className="scroll-mt-20 bg-cream py-20 sm:py-28">
        <div className="mx-auto max-w-7xl px-5 sm:px-8">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-semibold text-foreground sm:text-4xl">
              How Krishi AI Works
            </h2>
            <p className="mt-4 text-base text-muted-foreground">
              Three simple steps between a farming problem and a practical answer.
            </p>
          </div>

          <ol className="relative mt-14 grid gap-6 md:grid-cols-3">
            <span
              aria-hidden="true"
              className="absolute top-16 right-[16%] left-[16%] hidden h-px bg-border md:block"
            />
            {STEPS.map((step, i) => (
              <li
                key={step.title}
                className="relative rounded-3xl border border-border bg-card p-7 text-center shadow-soft transition-transform hover:-translate-y-1"
              >
                <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-gradient-leaf shadow-soft">
                  <step.icon className="size-6 text-primary-foreground" aria-hidden="true" />
                </span>
                <p className="mt-4 text-xs font-semibold tracking-widest text-primary uppercase">
                  Step {i + 1}
                </p>
                <h3 className="mt-1 text-xl font-semibold text-foreground">{step.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                  {step.description}
                </p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* MULTI-AGENT / ABOUT */}
      <section id="about" className="scroll-mt-20 bg-background py-20 sm:py-28">
        <div className="mx-auto max-w-7xl px-5 sm:px-8">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-semibold text-foreground sm:text-4xl">
              One Platform. Multiple AI Experts.
            </h2>
            <p className="mt-4 text-base text-muted-foreground">
              Instead of one generic assistant, Krishi AI routes each question to a specialist agent
              so the answer is relevant to the problem.
            </p>
          </div>

          <div className="mt-14 grid items-center gap-8 lg:grid-cols-[1fr_auto_1fr]">
            <div className="grid gap-4">
              <AgentCard {...AGENTS.crop} />
              <AgentCard {...AGENTS.disease} />
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
                <p className="text-xs text-forest-foreground/70">Agent Router</p>
              </div>
            </div>

            <div className="grid gap-4">
              <AgentCard {...AGENTS.finance} />
              <AgentCard {...AGENTS.general} />
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="px-5 pb-20 sm:px-8 sm:pb-28">
        <div className="mx-auto max-w-6xl overflow-hidden rounded-[2rem] bg-gradient-forest px-7 py-16 text-center shadow-lift sm:px-16">
          <h2 className="mx-auto max-w-2xl text-3xl font-semibold text-forest-foreground sm:text-4xl">
            Ready to Make Smarter Farming Decisions?
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-base text-forest-foreground/80">
            Get intelligent agricultural and financial assistance with Krishi AI.
          </p>
          <Button
            asChild
            size="lg"
            className="mt-8 h-13 rounded-full bg-gradient-leaf px-8 text-base font-semibold shadow-lift hover:opacity-95"
          >
            <Link to="/auth">
              Start Using Krishi AI
              <ArrowRight className="size-4" />
            </Link>
          </Button>
        </div>
      </section>

      <Footer />
    </div>
  );
}
