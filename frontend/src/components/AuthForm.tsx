import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

type Mode = "signin" | "signup";
type Errors = Partial<Record<"name" | "email" | "password" | "confirm", string>>;

const emailValid = (v: string) => /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v);

export function AuthForm() {
  const navigate = useNavigate();
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

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const next: Errors = {};

    if (mode === "signup" && values.name.trim().length < 2) {
      next.name = "Please enter your full name.";
    }
    if (!emailValid(values.email.trim())) next.email = "Enter a valid email address.";
    if (values.password.length < 6) next.password = "Password must be at least 6 characters.";
    if (mode === "signup" && values.confirm !== values.password) {
      next.confirm = "Passwords do not match.";
    }

    setErrors(next);
    if (Object.keys(next).length > 0) {
      toast.error("Please fix the highlighted fields.");
      return;
    }

    setSubmitting(true);
    window.setTimeout(() => {
      toast.success(mode === "signin" ? "Welcome back to Krishi AI." : "Account created. Demo mode.");
      navigate({ to: "/chat" });
    }, 700);
  };

  return (
    <div className="w-full max-w-md">
      <div
        role="tablist"
        aria-label="Authentication mode"
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
            {m === "signin" ? "Sign In" : "Sign Up"}
          </button>
        ))}
      </div>

      <div key={mode} className="animate-in fade-in slide-in-from-bottom-2 duration-300">
        <h1 className="mt-8 text-3xl font-semibold text-foreground">
          {mode === "signin" ? "Welcome Back" : "Create Your Account"}
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          {mode === "signin" ? "Sign in to continue to Krishi AI" : "Start using Krishi AI today"}
        </p>

        <form onSubmit={handleSubmit} noValidate className="mt-7 grid gap-4">
          {mode === "signup" && (
            <Field label="Full Name" error={errors.name} id="name">
              <Input
                id="name"
                autoComplete="name"
                placeholder="Enter your full name"
                value={values.name}
                onChange={set("name")}
                aria-invalid={!!errors.name}
                className="h-12 rounded-xl bg-card"
              />
            </Field>
          )}

          <Field label="Email" error={errors.email} id="email">
            <Input
              id="email"
              type="email"
              autoComplete="email"
              placeholder="Enter your email"
              value={values.email}
              onChange={set("email")}
              aria-invalid={!!errors.email}
              className="h-12 rounded-xl bg-card"
            />
          </Field>

          <Field label="Password" error={errors.password} id="password">
            <div className="relative">
              <Input
                id="password"
                type={showPassword ? "text" : "password"}
                autoComplete={mode === "signin" ? "current-password" : "new-password"}
                placeholder={mode === "signin" ? "Enter your password" : "Create a password"}
                value={values.password}
                onChange={set("password")}
                aria-invalid={!!errors.password}
                className="h-12 rounded-xl bg-card pr-12"
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                className="absolute top-1/2 right-2 grid size-9 -translate-y-1/2 place-items-center rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
              </button>
            </div>
          </Field>

          {mode === "signup" && (
            <Field label="Confirm Password" error={errors.confirm} id="confirm">
              <Input
                id="confirm"
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                placeholder="Confirm your password"
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
              onClick={() => toast("Password reset is not available in this demo.")}
              className="justify-self-end text-sm font-medium text-primary hover:underline"
            >
              Forgot Password?
            </button>
          )}

          <Button
            type="submit"
            disabled={submitting}
            className="mt-1 h-12 rounded-xl bg-gradient-leaf text-base font-semibold shadow-soft hover:opacity-95"
          >
            {submitting && <Loader2 className="mr-2 size-4 animate-spin" />}
            {mode === "signin" ? "Sign In" : "Create Account"}
          </Button>
        </form>

        <div className="my-6 flex items-center gap-4">
          <span className="h-px flex-1 bg-border" />
          <span className="text-xs font-medium tracking-widest text-muted-foreground">OR</span>
          <span className="h-px flex-1 bg-border" />
        </div>

        <Button
          type="button"
          variant="outline"
          onClick={() => toast("Google sign-in is simulated in this prototype.")}
          className="h-12 w-full rounded-xl bg-card font-medium"
        >
          <GoogleMark />
          Continue with Google
        </Button>

        <p className="mt-6 text-center text-sm text-muted-foreground">
          {mode === "signin" ? "Don't have an account? " : "Already have an account? "}
          <button
            type="button"
            onClick={() => switchMode(mode === "signin" ? "signup" : "signin")}
            className="font-semibold text-primary hover:underline"
          >
            {mode === "signin" ? "Sign Up" : "Sign In"}
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

function GoogleMark() {
  return (
    <svg viewBox="0 0 24 24" className="size-4" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M23.5 12.3c0-.8-.1-1.6-.2-2.3H12v4.5h6.4a5.5 5.5 0 0 1-2.4 3.6v3h3.9c2.3-2.1 3.6-5.2 3.6-8.8Z"
      />
      <path
        fill="#34A853"
        d="M12 24c3.2 0 5.9-1.1 7.9-2.9l-3.9-3c-1.1.7-2.4 1.2-4 1.2a7 7 0 0 1-6.6-4.8H1.4v3.1A12 12 0 0 0 12 24Z"
      />
      <path fill="#FBBC05" d="M5.4 14.5a7.2 7.2 0 0 1 0-4.6V6.8H1.4a12 12 0 0 0 0 10.8l4-3.1Z" />
      <path
        fill="#EA4335"
        d="M12 4.8c1.8 0 3.3.6 4.5 1.8l3.4-3.4A12 12 0 0 0 1.4 6.8l4 3.1A7 7 0 0 1 12 4.8Z"
      />
    </svg>
  );
}
