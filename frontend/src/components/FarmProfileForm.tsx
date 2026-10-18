import { useState } from "react";
import { IndianRupee, Layers, Loader2, MapPin, Ruler, Sprout } from "lucide-react";
import { toast } from "sonner";
import { saveFarmer, type FarmContext } from "@/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getAuthUser } from "@/lib/authSession";
import {
  loadFarmProfile,
  markOnboardingComplete,
  saveFarmProfileLocal,
} from "@/lib/farmProfile";
import { cn } from "@/lib/utils";

interface FarmProfileFormProps {
  initial?: FarmContext;
  submitLabel?: string;
  onSaved?: (profile: FarmContext) => void;
  className?: string;
}

const NUMERIC_KEYS = new Set<keyof FarmContext>(["farm_area_acres", "budget"]);

export function FarmProfileForm({
  initial,
  submitLabel = "Save farm profile",
  onSaved,
  className,
}: FarmProfileFormProps) {
  const user = getAuthUser();
  const [profile, setProfile] = useState<FarmContext>(() => {
    const base = initial ?? loadFarmProfile();
    return {
      ...base,
      farmer_id: user?.farmer_id || base.farmer_id,
    };
  });
  const [saving, setSaving] = useState(false);

  const setField =
    (key: keyof FarmContext) => (e: React.ChangeEvent<HTMLInputElement>) => {
      const value = e.target.value;
      setProfile((prev) => {
        if (!NUMERIC_KEYS.has(key)) {
          return { ...prev, [key]: value };
        }
        if (value === "") {
          return { ...prev, [key]: key === "budget" ? null : 0 };
        }
        const num = Number(value);
        return { ...prev, [key]: Number.isFinite(num) ? num : prev[key] };
      });
    };

  const handleSave = async () => {
    if (!user?.farmer_id) {
      toast.error("Please sign in before saving your farm profile.");
      return;
    }
    if (!profile.location.trim()) {
      toast.error("Location is required.");
      return;
    }
    if (!(profile.crop ?? "").trim()) {
      toast.error("Primary crop is required.");
      return;
    }
    if (!(Number(profile.farm_area_acres) > 0)) {
      toast.error("Farm area must be greater than 0.");
      return;
    }
    if (profile.budget != null && !(Number(profile.budget) > 0)) {
      toast.error("Budget must be greater than 0, or leave it blank.");
      return;
    }

    setSaving(true);
    try {
      const budgetNum = profile.budget == null ? null : Number(profile.budget);
      const next: FarmContext = {
        ...profile,
        farmer_id: user.farmer_id,
        location: profile.location.trim(),
        crop: (profile.crop ?? "").trim(),
        soil_type: (profile.soil_type ?? "").trim() || null,
        farm_area_acres: Number(profile.farm_area_acres),
        budget: budgetNum != null && Number.isFinite(budgetNum) && budgetNum > 0 ? budgetNum : null,
        preferred_language: profile.preferred_language || "en",
      };
      await saveFarmer(next);
      saveFarmProfileLocal(next);
      markOnboardingComplete(user.farmer_id);
      toast.success("Farm profile saved.");
      onSaved?.(next);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not save profile";
      toast.error(message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className={cn("grid gap-4", className)}>
      <Field
        id="location"
        label="Location"
        icon={MapPin}
        value={profile.location}
        onChange={setField("location")}
        placeholder="Village / district, state"
        required
      />
      <div className="grid gap-4 sm:grid-cols-2">
        <Field
          id="crop"
          label="Primary crop"
          icon={Sprout}
          value={profile.crop ?? ""}
          onChange={setField("crop")}
          placeholder="Wheat, rice, cotton…"
          required
        />
        <Field
          id="farm_area_acres"
          label="Farm area"
          icon={Ruler}
          type="number"
          value={profile.farm_area_acres ? String(profile.farm_area_acres) : ""}
          onChange={setField("farm_area_acres")}
          placeholder="Acres"
          required
          suffix="acres"
        />
      </div>
      <Field
        id="budget"
        label="Season budget"
        icon={IndianRupee}
        type="number"
        value={profile.budget != null && profile.budget > 0 ? String(profile.budget) : ""}
        onChange={setField("budget")}
        placeholder="e.g. 50000"
        suffix="INR"
        hint="Helps finance and market advice stay realistic for your spend."
      />
      <Field
        id="soil_type"
        label="Soil type"
        icon={Layers}
        value={profile.soil_type ?? ""}
        onChange={setField("soil_type")}
        placeholder="Optional — loamy, clay, sandy…"
      />

      <Button
        className="mt-1 h-12 rounded-2xl bg-gradient-leaf text-base font-semibold shadow-soft hover:opacity-95"
        disabled={saving}
        onClick={() => void handleSave()}
      >
        {saving && <Loader2 className="size-4 animate-spin" />}
        {saving ? "Saving…" : submitLabel}
      </Button>
    </div>
  );
}

function Field({
  id,
  label,
  value,
  onChange,
  type = "text",
  placeholder,
  required,
  icon: Icon,
  suffix,
  hint,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  type?: string;
  placeholder?: string;
  required?: boolean;
  icon: typeof MapPin;
  suffix?: string;
  hint?: string;
}) {
  return (
    <div className="grid gap-2">
      <Label htmlFor={id} className="text-sm font-medium text-foreground">
        {label}
        {required ? <span className="text-primary"> *</span> : null}
      </Label>
      <div className="relative">
        <Icon
          className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden="true"
        />
        <Input
          id={id}
          type={type}
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          className={cn(
            "h-12 rounded-2xl border-border/80 bg-background pl-10 shadow-none transition-colors",
            "focus-visible:border-primary/50 focus-visible:ring-primary/20",
            suffix && "pr-16",
          )}
          min={type === "number" ? 0 : undefined}
          step={type === "number" ? "any" : undefined}
        />
        {suffix && (
          <span className="pointer-events-none absolute top-1/2 right-3.5 -translate-y-1/2 text-xs font-medium text-muted-foreground">
            {suffix}
          </span>
        )}
      </div>
      {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}
