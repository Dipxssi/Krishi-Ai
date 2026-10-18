import { Navigate, useLocation } from "react-router-dom";
import { isAuthenticated } from "@/lib/authSession";
import { isFarmProfileComplete } from "@/lib/farmProfile";

interface RequireAuthProps {
  children: React.ReactNode;
  requireFarmProfile?: boolean;
}

export function RequireAuth({ children, requireFarmProfile = false }: RequireAuthProps) {
  const location = useLocation();

  if (!isAuthenticated()) {
    return <Navigate to="/auth" replace state={{ from: location.pathname }} />;
  }

  if (requireFarmProfile && !isFarmProfileComplete()) {
    return <Navigate to="/onboarding" replace />;
  }

  return <>{children}</>;
}
