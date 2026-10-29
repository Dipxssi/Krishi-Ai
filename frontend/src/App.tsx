import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthSessionBootstrap } from "@/components/AuthSessionBootstrap";
import { LanguageGate } from "@/components/LanguageGate";
import { RequireAuth } from "@/components/RequireAuth";
import { Toaster } from "@/components/ui/sonner";
import { AuthPage } from "@/pages/AuthPage";
import { ChatPage } from "@/pages/ChatPage";
import { FieldRelayPage } from "@/pages/FieldRelayPage";
import { HomePage } from "@/pages/HomePage";
import { OnboardingPage } from "@/pages/OnboardingPage";

/** Live product shell. TanStack mock chat under src/routes/ is not mounted here. */
export default function App() {
  return (
    <BrowserRouter>
      <AuthSessionBootstrap />
      <LanguageGate />
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/auth" element={<AuthPage />} />
        <Route
          path="/onboarding"
          element={
            <RequireAuth>
              <OnboardingPage />
            </RequireAuth>
          }
        />
        <Route
          path="/chat"
          element={
            <RequireAuth>
              <ChatPage />
            </RequireAuth>
          }
        />
        <Route
          path="/field-relay"
          element={
            <RequireAuth>
              <FieldRelayPage />
            </RequireAuth>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <Toaster position="top-center" richColors />
    </BrowserRouter>
  );
}
