import type { LucideIcon } from "lucide-react";

interface FeatureCardProps {
  icon: LucideIcon;
  title: string;
  description: string;
}

export function FeatureCard({ icon: Icon, title, description }: FeatureCardProps) {
  return (
    <article className="group rounded-3xl border border-border bg-card p-7 shadow-soft transition-all duration-300 hover:-translate-y-1 hover:border-primary/35 hover:shadow-lift">
      <span className="grid size-12 place-items-center rounded-2xl bg-accent text-accent-foreground transition-colors group-hover:bg-gradient-leaf group-hover:text-primary-foreground">
        <Icon className="size-6" aria-hidden="true" />
      </span>
      <h3 className="mt-5 text-lg font-semibold text-foreground">{title}</h3>
      <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{description}</p>
    </article>
  );
}
