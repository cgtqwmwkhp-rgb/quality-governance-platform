import { useEffect } from "react";
import { useNavigate, Outlet } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { usePortalAuth } from "../contexts/PortalAuthContext";

export default function PortalLayout() {
  const navigate = useNavigate();
  const { isAuthenticated, isLoading } = usePortalAuth();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      navigate("/portal/login");
    }
  }, [isAuthenticated, isLoading, navigate]);

  if (isLoading) {
    return (
      <div
        className="min-h-screen bg-background flex items-center justify-center"
        role="status"
        aria-label="Loading portal"
      >
        <div className="text-center">
          <Loader2 className="w-12 h-12 text-primary animate-spin mx-auto mb-4" />
          <p className="text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null; // Will redirect to login
  }

  return <Outlet />;
}
