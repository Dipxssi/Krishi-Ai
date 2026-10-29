import { Link } from "react-router-dom";
import { ArrowLeft, Radio, Smartphone, Wifi } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useApiConnection } from "@/hooks/useApiConnection";
import { cn } from "@/lib/utils";

const STEPS = [
  {
    icon: Wifi,
    title: "Shop or KVK turns on a hotspot",
    body: "Someone nearby with internet shares a mobile hotspot or WiFi. Write the WiFi name and password on the setup card from the relay script.",
  },
  {
    icon: Smartphone,
    title: "Farmer joins that WiFi",
    body: "On the phone, open WiFi settings, join the shop network, and return to Krishi AI. You do not need your own mobile data.",
  },
  {
    icon: Radio,
    title: "Waiting questions send by themselves",
    body: "Stay on the chat screen. Saved questions go to the real Krishi AI API through the shop’s internet. Answers stay on the phone after you leave.",
  },
];

export function FieldRelayPage() {
  const { status } = useApiConnection({ pollMs: 10_000 });

  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto max-w-2xl px-5 py-8 sm:px-8">
        <Button asChild variant="ghost" className="-ml-2 mb-6 rounded-full">
          <Link to="/chat">
            <ArrowLeft className="size-4" />
            Back to chat
          </Link>
        </Button>

        <p className="text-sm font-medium text-primary">Field relay</p>
        <h1 className="mt-2 font-serif text-3xl font-semibold tracking-tight text-foreground">
          Reach Krishi AI without your own data
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground sm:text-base">
          Bluetooth cannot reach our server. A nearby shop, KVK, or friend’s hotspot can.
          Ask offline first; join their WiFi later; answers come from the real API.
        </p>

        <div
          className={cn(
            "mt-6 rounded-2xl border px-4 py-3 text-sm",
            status === "online" && "border-primary/30 bg-primary/5 text-foreground",
            status === "offline" && "border-destructive/30 bg-destructive/5 text-foreground",
            (status === "checking" || status === "sending") && "border-border bg-muted/40 text-muted-foreground",
          )}
        >
          {status === "online" && "API is reachable from this phone right now. Queued questions can send."}
          {status === "offline" && "API is not reachable. Join the shop WiFi, then return here or to chat."}
          {status === "checking" && "Checking whether the API is reachable…"}
          {status === "sending" && "Sending queued questions…"}
        </div>

        <ol className="mt-10 grid gap-6">
          {STEPS.map((step, index) => (
            <li key={step.title} className="flex gap-4">
              <span className="grid size-11 shrink-0 place-items-center rounded-2xl bg-gradient-leaf text-primary-foreground shadow-soft">
                <step.icon className="size-5" aria-hidden="true" />
              </span>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Step {index + 1}
                </p>
                <h2 className="mt-1 text-base font-semibold text-foreground">{step.title}</h2>
                <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{step.body}</p>
              </div>
            </li>
          ))}
        </ol>

        <div className="mt-10 rounded-2xl border border-border bg-card p-5 shadow-soft">
          <h2 className="text-base font-semibold text-foreground">For the shop laptop</h2>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
            On a machine that already has internet, turn on a mobile hotspot (Windows / Android / iPhone),
            then run:
          </p>
          <pre className="mt-3 overflow-x-auto rounded-xl bg-muted px-4 py-3 text-xs leading-relaxed text-foreground">
{`cd backend
uv run python scripts/field_relay_status.py`}
          </pre>
          <p className="mt-3 text-sm text-muted-foreground">
            The script checks the API and prints a setup card with the WiFi name, password, and app URL
            for farmers to join.
          </p>
        </div>

        <div className="mt-8 flex flex-wrap gap-3">
          <Button asChild className="rounded-full bg-gradient-leaf shadow-soft">
            <Link to="/chat">Open chat</Link>
          </Button>
          <Button asChild variant="outline" className="rounded-full">
            <Link to="/">Home</Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
