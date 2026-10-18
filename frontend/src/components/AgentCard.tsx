interface AgentCardProps {
  emoji: string;
  name: string;
  description: string;
}

export function AgentCard({ emoji, name, description }: AgentCardProps) {
  return (
    <article className="flex items-start gap-4 rounded-2xl border border-border bg-card p-5 shadow-soft transition-all duration-300 hover:-translate-y-0.5 hover:border-primary/35 hover:shadow-lift">
      <span
        aria-hidden="true"
        className="grid size-11 shrink-0 place-items-center rounded-xl bg-secondary text-xl"
      >
        {emoji}
      </span>
      <div>
        <h3 className="text-base font-semibold text-foreground">{name}</h3>
        <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{description}</p>
      </div>
    </article>
  );
}
