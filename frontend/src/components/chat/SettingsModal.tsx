import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { AGENTS } from "@/data/mockChats";

interface SettingsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onClearAll: () => void;
}

export function SettingsModal({ open, onOpenChange, onClearAll }: SettingsModalProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="rounded-3xl sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Settings</DialogTitle>
          <DialogDescription>
            Preferences for this Krishi AI demo. Nothing is stored on a server.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-5">
          <div className="grid gap-3 rounded-2xl border border-border p-4">
            <Row
              id="agent-labels"
              label="Show agent labels"
              hint="Display which specialist agent answered."
              defaultChecked
            />
            <Row
              id="suggestions"
              label="Suggested prompts"
              hint="Show starter questions on the welcome screen."
              defaultChecked
            />
            <Row
              id="sounds"
              label="Response sound"
              hint="Play a soft chime when a reply arrives."
            />
          </div>

          <div className="rounded-2xl border border-border p-4">
            <p className="text-sm font-semibold text-foreground">Available agents</p>
            <ul className="mt-3 grid gap-2">
              {Object.values(AGENTS).map((agent) => (
                <li key={agent.id} className="flex items-center gap-2 text-sm text-muted-foreground">
                  <span aria-hidden="true">{agent.emoji}</span>
                  <span className="font-medium text-foreground">{agent.name}</span>
                </li>
              ))}
            </ul>
          </div>

          <Button
            variant="outline"
            className="rounded-xl border-destructive/40 text-destructive hover:bg-destructive/10 hover:text-destructive"
            onClick={() => {
              onClearAll();
              onOpenChange(false);
              toast.success("All conversations deleted");
            }}
          >
            Delete all conversations
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function Row({
  id,
  label,
  hint,
  defaultChecked,
}: {
  id: string;
  label: string;
  hint: string;
  defaultChecked?: boolean | undefined;
}) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div>
        <Label htmlFor={id} className="text-sm font-medium">
          {label}
        </Label>
        <p className="text-xs text-muted-foreground">{hint}</p>
      </div>
      <Switch id={id} defaultChecked={defaultChecked ?? false} />
    </div>
  );
}
