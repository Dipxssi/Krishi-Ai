import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { login, signup } from "@/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { useI18n } from "@/hooks/useI18n";
import { persistAuthSession } from "@/lib/authSession";
import { hydrateFarmProfileFromServer } from "@/lib/farmProfile";
import { cn } from "@/lib/utils";

type Mode = "signin" | "signup";
type Errors = Partial<Record<"name" | "email" | "password" | "confirm", string>>;

const emailValid = (v: string) => /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v);

export function AuthForm() {
  const navigate = useNavigate();
  const { t } = useI18n();
  const [mode, setMode] = useState<Mode>("signin");
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [values, setValues] = useState({ name: "", email: "", password: "", confirm: "" });
  const [errors, setErrors] = useState<Errors>({});

  const set = (key: keyof typeof values) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setValues((v) => ({ ...v, [key]: e.target.value }));
    setErrors((prev) => ({ ...prev, [key]: undefined }));
  };

  const switchMode = (next: Mode) => {
    setMode(next);
    setErrors({});
    setShowPassword(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const next: Errors = {};

    if (mode === "signup" && values.name.trim().length < 2) {
      next.name = t("auth.errName");
    }
    if (!emailValid(values.email.trim())) next.email = t("auth.errEmail");
    if (values.password.length < 6) next.password = t("auth.errPassword");
    if (mode === "signup" && values.confirm !== values.password) {
      next.confirm = t("auth.errConfirm");
    }

    setErrors(next);
    if (Object.keys(next).length > 0) {
      toast.error(t("auth.errFix"));
      return;
    }

    setSubmitting(true);
    try {
      const email = values.email.trim();
      const auth =
        mode === "signup"
          ? await signup(values.name.trim(), email, values.password)
          : await login(email, values.password);
      persistAuthSession(auth.access_token, auth.user);
      await hydrateFarmProfileFromServer();
      toast.success(mode === "signin" ? t("auth.welcomeToast") : t("auth.createdToast"));
      navigate(mode === "signup" ? "/onboarding" : "/chat");
    } catch (error) {
      const raw = error instanceof Error ? error.message : t("auth.failed");
      const message =
        mode === "signin" && /invalid email or password/i.test(raw) ? t("auth.noAccountToast") : raw;
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="w-full max-w-md">
      <div className="mb-4 flex justify-end">
        <LanguageSwitcher />
      </div>
      <div
        role="tablist"
        aria-label={t("auth.modeAria")}
        className="grid grid-cols-2 gap-1 rounded-2xl bg-muted p-1"
      >
        {(["signin", "signup"] as Mode[]).map((m) => (
          <button
            key={m}
            role="tab"
            type="button"
            aria-selected={mode === m}
            onClick={() => switchMode(m)}
            className={cn(
              "rounded-xl px-4 py-2.5 text-sm font-semibold transition-all",
              mode === m
                ? "bg-card text-foreground shadow-soft"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {m === "signin" ? t("auth.signIn") : t("auth.signUp")}
          </button>
        ))}
      </div>

      <div key={mode} className="animate-in fade-in slide-in-from-bottom-2 duration-300">
        <h1 className="mt-8 text-3xl font-semibold text-foreground">
          {mode === "signin" ? t("auth.welcomeBack") : t("auth.createAccount")}
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          {mode === "signin" ? t("auth.signInHint") : t("auth.signUpHint")}
        </p>

        <form onSubmit={handleSubmit} noValidate className="mt-7 grid gap-4">
          {mode === "signup" && (
            <Field label={t("auth.fullName")} error={errors.name} id="name">
              <Input
                id="name"
                autoComplete="name"
                placeholder={t("auth.namePlaceholder")}
                value={values.name}
                onChange={set("name")}
                aria-invalid={!!errors.name}
                className="h-12 rounded-xl bg-card"
              />
            </Field>
          )}

          <Field label={t("auth.email")} error={errors.email} id="email">
            <Input
              id="email"
              type="email"
              autoComplete="email"
              placeholder={t("auth.emailPlaceholder")}
              value={values.email}
              onChange={set("email")}
              aria-invalid={!!errors.email}
              className="h-12 rounded-xl bg-card"
            />
          </Field>

          <Field label={t("auth.password")} error={errors.password} id="password">
            <div className="relative">
              <Input
                id="password"
                type={showPassword ? "text" : "password"}
                autoComplete={mode === "signin" ? "current-password" : "new-password"}
                placeholder={
                  mode === "signin" ? t("auth.passwordPlaceholder") : t("auth.createPasswordPlaceholder")
                }
                value={values.password}
                onChange={set("password")}
                aria-invalid={!!errors.password}
                className="h-12 rounded-xl bg-card pr-12"
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? t("auth.hidePassword") : t("auth.showPassword")}
                className="absolute top-1/2 right-2 grid size-9 -translate-y-1/2 place-items-center rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
              </button>
            </div>
          </Field>

          {mode === "signup" && (
            <Field label={t("auth.confirmPassword")} error={errors.confirm} id="confirm">
              <Input
                id="confirm"
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                placeholder={t("auth.confirmPlaceholder")}
                value={values.confirm}
                onChange={set("confirm")}
                aria-invalid={!!errors.confirm}
                className="h-12 rounded-xl bg-card"
              />
            </Field>
          )}

          {mode === "signin" && (
            <button
              type="button"
              onClick={() => toast(t("auth.resetSoon"))}
              className="justify-self-end text-sm font-medium text-primary hover:underline"
            >
              {t("auth.forgot")}
            </button>
          )}

          <Button
            type="submit"
            disabled={submitting}
            className="mt-1 h-12 rounded-xl bg-gradient-leaf text-base font-semibold shadow-soft hover:opacity-95"
          >
            {submitting && <Loader2 className="mr-2 size-4 animate-spin" />}
            {mode === "signin" ? t("auth.submitSignIn") : t("auth.submitSignUp")}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-muted-foreground">
          {mode === "signin" ? t("auth.noAccount") : t("auth.hasAccount")}{" "}
          <button
            type="button"
            onClick={() => switchMode(mode === "signin" ? "signup" : "signin")}
            className="font-semibold text-primary hover:underline"
          >
            {mode === "signin" ? t("auth.signUp") : t("auth.signIn")}
          </button>
        </p>
      </div>
    </div>
  );
}

function Field({
  label,
  id,
  error,
  children,
}: {
  label: string;
  id: string;
  error?: string | undefined;
  children: React.ReactNode;
}) {
  return (
    <div className="grid gap-2">
      <Label htmlFor={id} className="text-sm font-medium">
        {label}
      </Label>
      {children}
      {error && (
        <p role="alert" className="text-xs font-medium text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
