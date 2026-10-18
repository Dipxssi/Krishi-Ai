import { Sprout } from "lucide-react";
import { cn } from "@/lib/utils";

interface LogoProps {
  className?: string;
  showText?: boolean;
  tone?: "default" | "onDark";
  size?: "sm" | "md" | "lg";
}

const boxSizes = { sm: "size-8", md: "size-10", lg: "size-14" } as const;
const iconSizes = { sm: "size-4", md: "size-5", lg: "size-7" } as const;
const textSizes = { sm: "text-base", md: "text-lg", lg: "text-2xl" } as const;

export function Logo({ className, showText = true, tone = "default", size = "md" }: LogoProps) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <span
        className={cn(
          "grid place-items-center rounded-2xl bg-gradient-leaf shadow-soft",
          boxSizes[size],
        )}
      >
        <Sprout className={cn(iconSizes[size], "text-primary-foreground")} aria-hidden="true" />
      </span>
      {showText && (
        <span
          className={cn(
            "font-display font-semibold tracking-tight",
            textSizes[size],
            tone === "onDark" ? "text-forest-foreground" : "text-foreground",
          )}
        >
          Krishi AI
        </span>
      )}
    </span>
  );
}
