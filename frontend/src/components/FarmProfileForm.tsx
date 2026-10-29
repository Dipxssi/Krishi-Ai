import { useMemo, useState } from "react";
import {
  IndianRupee,
  Layers,
  Loader2,
  LocateFixed,
  MapPin,
  Ruler,
  Sprout,
} from "lucide-react";
import { toast } from "sonner";
import { saveFarmer, type FarmContext } from "@/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useI18n } from "@/hooks/useI18n";
import { getAuthUser } from "@/lib/authSession";
import {
  buildLocation,
  getStateDefaults,
  listIndianStates,
  parseLocationParts,
  reverseGeocodeIndianState,
  type IndianStateId,
} from "@/lib/indiaFarmDefaults";
import {
  loadFarmProfile,
  markOnboardingComplete,
  saveFarmProfileLocal,
} from "@/lib/farmProfile";
import { getLocale } from "@/lib/i18n";
import { cn } from "@/lib/utils";

interface FarmProfileFormProps {
  initial?: FarmContext;
  submitLabel?: string;
  onSaved?: (profile: FarmContext) => void;
  className?: string;
}

const CROP_OTHER = "__other__";

function initFromProfile(base: FarmContext) {
  const { place, state } = parseLocationParts(base.location || "");
  const defaults = getStateDefaults(state);
  const crop = (base.crop ?? "").trim();
  const cropOptions = defaults?.crops ?? [];
  const cropIsListed = crop !== "" && cropOptions.some((c) => c.toLowerCase() === crop.toLowerCase());
  return {
    place,
    state,
    cropSelect: cropIsListed ? crop : crop ? CROP_OTHER : "",
    cropCustom: cropIsListed ? "" : crop,
    soil: (base.soil_type ?? "").trim() || defaults?.soil || "",
    farm_area_acres: base.farm_area_acres,
    budget: base.budget,
    farmer_id: base.farmer_id,
    preferred_language: base.preferred_language,
  };
}

export function FarmProfileForm({
  initial,
  submitLabel,
  onSaved,
  className,
}: FarmProfileFormProps) {
  const { t } = useI18n();
  const user = getAuthUser();
  const resolvedSubmitLabel = submitLabel ?? t("farm.save");
  const [form, setForm] = useState(() => {
    const base = initial ?? loadFarmProfile();
    return initFromProfile({
      ...base,
      farmer_id: user?.farmer_id || base.farmer_id,
    });
  });
  const [saving, setSaving] = useState(false);
  const [locating, setLocating] = useState(false);

  const stateDefaults = useMemo(() => getStateDefaults(form.state), [form.state]);
  const cropOptions = stateDefaults?.crops ?? [];

  const applyState = (state: IndianStateId | null, opts?: { place?: string; forceSoil?: boolean }) => {
    const defaults = getStateDefaults(state);
    setForm((prev) => {
      const nextSoil =
        opts?.forceSoil || !prev.soil.trim() || prev.soil === getStateDefaults(prev.state)?.soil
          ? defaults?.soil ?? prev.soil
          : prev.soil;

      let cropSelect = prev.cropSelect;
      let cropCustom = prev.cropCustom;
      if (defaults && cropSelect && cropSelect !== CROP_OTHER) {
        const stillListed = defaults.crops.some((c) => c.toLowerCase() === cropSelect.toLowerCase());
        if (!stillListed) {
          cropCustom = cropSelect;
          cropSelect = CROP_OTHER;
        }
      }

      return {
        ...prev,
        state,
        place: opts?.place !== undefined ? opts.place : prev.place,
        soil: nextSoil,
        cropSelect,
        cropCustom,
      };
    });
  };

  const resolvedCrop = (): string => {
    if (form.cropSelect === CROP_OTHER) return form.cropCustom.trim();
    return form.cropSelect.trim();
  };

  const handleLocate = () => {
    if (!navigator.geolocation) {
      toast.error(t("farm.noGeo"));
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          const { state, place } = await reverseGeocodeIndianState(
            pos.coords.latitude,
            pos.coords.longitude,
          );
          if (!state) {
            toast.error(t("farm.geoNoState"));
            return;
          }
          applyState(state, {
            place: place || undefined,
            forceSoil: true,
          });
          toast.success(t("farm.geoOk", { state }));
        } catch (error) {
          const message = error instanceof Error ? error.message : t("farm.geoFail");
          toast.error(message === "Location is outside India" ? t("farm.geoOutside") : t("farm.geoFail"));
        } finally {
          setLocating(false);
        }
      },
      () => {
        setLocating(false);
        toast.error(t("farm.geoDenied"));
      },
      { enableHighAccuracy: true, timeout: 15000 },
    );
  };

  const handleSave = async () => {
    if (!user?.farmer_id) {
      toast.error(t("farm.needAuth"));
      return;
    }
    if (!form.state) {
      toast.error(t("farm.needState"));
      return;
    }
    const crop = resolvedCrop();
    if (!crop) {
      toast.error(t("farm.needCrop"));
      return;
    }
    if (!(Number(form.farm_area_acres) > 0)) {
      toast.error(t("farm.needArea"));
      return;
    }
    if (form.budget != null && !(Number(form.budget) > 0)) {
      toast.error(t("farm.needBudget"));
      return;
    }

    setSaving(true);
    try {
      const budgetNum = form.budget == null ? null : Number(form.budget);
      const next: FarmContext = {
        farmer_id: user.farmer_id,
        location: buildLocation(form.place, form.state),
        crop,
        soil_type: form.soil.trim() || null,
        farm_area_acres: Number(form.farm_area_acres),
        budget: budgetNum != null && Number.isFinite(budgetNum) && budgetNum > 0 ? budgetNum : null,
        preferred_language: getLocale(),
      };
      await saveFarmer(next);
      saveFarmProfileLocal(next);
      markOnboardingComplete(user.farmer_id);
      toast.success(t("farm.saved"));
      onSaved?.(next);
    } catch (error) {
      const message = error instanceof Error ? error.message : t("farm.saveFail");
      toast.error(message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className={cn("grid gap-4", className)}>
      <div className="grid gap-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Label htmlFor="farm-state" className="text-sm font-medium text-foreground">
            {t("farm.state")}
            <span className="text-primary"> *</span>
          </Label>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-9 rounded-xl gap-1.5"
            disabled={locating}
            onClick={handleLocate}
          >
            {locating ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <LocateFixed className="size-3.5" />
            )}
            {locating ? t("farm.locating") : t("farm.useLocation")}
          </Button>
        </div>
        <div className="relative">
          <MapPin
            className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <select
            id="farm-state"
            value={form.state ?? ""}
            onChange={(e) => {
              const next = (e.target.value || null) as IndianStateId | null;
              applyState(next, { forceSoil: true });
            }}
            className={cn(
              "h-12 w-full appearance-none rounded-2xl border border-border/80 bg-background pl-10 pr-8 text-sm shadow-none",
              "focus-visible:border-primary/50 focus-visible:ring-2 focus-visible:ring-primary/20 focus-visible:outline-none",
            )}
            required
          >
            <option value="">{t("farm.statePh")}</option>
            {listIndianStates().map((state) => (
              <option key={state} value={state}>
                {state}
              </option>
            ))}
          </select>
        </div>
        <p className="text-xs text-muted-foreground">{t("farm.stateHint")}</p>
      </div>

      <Field
        id="place"
        label={t("farm.place")}
        icon={MapPin}
        value={form.place}
        onChange={(e) => setForm((prev) => ({ ...prev, place: e.target.value }))}
        placeholder={t("farm.placePh")}
        hint={t("farm.placeHint")}
      />

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="grid gap-2">
          <Label htmlFor="farm-crop" className="text-sm font-medium text-foreground">
            {t("farm.crop")}
            <span className="text-primary"> *</span>
          </Label>
          <div className="relative">
            <Sprout
              className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <select
              id="farm-crop"
              value={form.cropSelect}
              onChange={(e) =>
                setForm((prev) => ({
                  ...prev,
                  cropSelect: e.target.value,
                  cropCustom: e.target.value === CROP_OTHER ? prev.cropCustom : "",
                }))
              }
              disabled={!form.state}
              className={cn(
                "h-12 w-full appearance-none rounded-2xl border border-border/80 bg-background pl-10 pr-8 text-sm shadow-none",
                "focus-visible:border-primary/50 focus-visible:ring-2 focus-visible:ring-primary/20 focus-visible:outline-none",
                "disabled:opacity-60",
              )}
              required
            >
              <option value="">{t("farm.cropPh")}</option>
              {cropOptions.map((crop) => (
                <option key={crop} value={crop}>
                  {crop}
                </option>
              ))}
              <option value={CROP_OTHER}>{t("farm.cropOther")}</option>
            </select>
          </div>
          {form.cropSelect === CROP_OTHER && (
            <Input
              id="farm-crop-custom"
              value={form.cropCustom}
              onChange={(e) => setForm((prev) => ({ ...prev, cropCustom: e.target.value }))}
              placeholder={t("farm.cropCustomPh")}
              className="h-12 rounded-2xl border-border/80 bg-background shadow-none focus-visible:border-primary/50 focus-visible:ring-primary/20"
            />
          )}
        </div>

        <Field
          id="farm_area_acres"
          label={t("farm.area")}
          icon={Ruler}
          type="number"
          value={form.farm_area_acres ? String(form.farm_area_acres) : ""}
          onChange={(e) => {
            const value = e.target.value;
            setForm((prev) => ({
              ...prev,
              farm_area_acres: value === "" ? 0 : Number(value) || prev.farm_area_acres,
            }));
          }}
          placeholder={t("farm.areaPh")}
          required
          suffix={t("farm.acres")}
        />
      </div>

      <Field
        id="budget"
        label={t("farm.budget")}
        icon={IndianRupee}
        type="number"
        value={form.budget != null && form.budget > 0 ? String(form.budget) : ""}
        onChange={(e) => {
          const value = e.target.value;
          setForm((prev) => ({
            ...prev,
            budget: value === "" ? null : Number(value) || null,
          }));
        }}
        placeholder={t("farm.budgetPh")}
        suffix="INR"
        hint={t("farm.budgetHint")}
      />

      <Field
        id="soil_type"
        label={t("farm.soil")}
        icon={Layers}
        value={form.soil}
        onChange={(e) => setForm((prev) => ({ ...prev, soil: e.target.value }))}
        placeholder={t("farm.soilPh")}
        hint={form.state ? t("farm.soilHint") : t("farm.soilNeedState")}
      />

      <Button
        className="mt-1 h-12 rounded-2xl bg-gradient-leaf text-base font-semibold shadow-soft hover:opacity-95"
        disabled={saving}
        onClick={() => void handleSave()}
      >
        {saving && <Loader2 className="size-4 animate-spin" />}
        {saving ? t("farm.saving") : resolvedSubmitLabel}
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
