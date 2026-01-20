import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Shield, Loader2, AlertCircle, CheckCircle } from 'lucide-react';
import { usePortalAuth } from '../contexts/PortalAuthContext';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { ThemeToggle } from '../components/ui/ThemeToggle';

export default function PortalLogin() {
  const navigate = useNavigate();
  const { isAuthenticated, isLoading, login, error } = usePortalAuth();

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated && !isLoading) {
      navigate('/portal');
    }
  }, [isAuthenticated, isLoading, navigate]);

  const handleLogin = async () => {
    await login();
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 text-primary animate-spin mx-auto mb-4" />
          <p className="text-muted-foreground">Checking authentication...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4 relative">
      {/* Theme Toggle */}
      <div className="absolute top-4 right-4">
        <ThemeToggle />
      </div>

      {/* Background decoration */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-primary/5 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-primary/10 rounded-full blur-3xl" />
      </div>

      <div className="max-w-md w-full relative animate-fade-in">
        {/* Logo & Header */}
        <div className="text-center mb-8">
          <div className="w-20 h-20 gradient-brand rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-glow">
            <Shield className="w-10 h-10 text-primary-foreground" />
          </div>
          <h1 className="text-3xl font-bold text-foreground mb-2">Employee Portal</h1>
          <p className="text-muted-foreground">Sign in with your Plantexpand account</p>
        </div>

        {/* Login Card */}
        <Card className="p-8">
          {/* Error Message */}
          {error && (
            <div className="mb-6 p-4 bg-destructive/10 border border-destructive/20 rounded-xl flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-destructive flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm text-destructive font-medium">Sign in failed</p>
                <p className="text-xs text-destructive/70 mt-1">{error}</p>
              </div>
            </div>
          )}

          {/* SSO Button */}
          <Button
            onClick={handleLogin}
            disabled={isLoading}
            variant="outline"
            size="xl"
            className="w-full bg-card hover:bg-surface"
          >
            {isLoading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <>
                {/* Microsoft Logo */}
                <svg className="w-5 h-5" viewBox="0 0 21 21" fill="none">
                  <rect x="1" y="1" width="9" height="9" fill="#F25022" />
                  <rect x="11" y="1" width="9" height="9" fill="#7FBA00" />
                  <rect x="1" y="11" width="9" height="9" fill="#00A4EF" />
                  <rect x="11" y="11" width="9" height="9" fill="#FFB900" />
                </svg>
                Sign in with Microsoft
              </>
            )}
          </Button>

          <div className="mt-6 text-center">
            <p className="text-xs text-muted-foreground">
              Use your <span className="text-primary font-medium">@plantexpand.com</span> email
            </p>
          </div>

          {/* Divider */}
          <div className="my-6 flex items-center gap-4">
            <div className="flex-1 h-px bg-border" />
            <span className="text-xs text-muted-foreground">SECURE SIGN-IN</span>
            <div className="flex-1 h-px bg-border" />
          </div>

          {/* Info */}
          <div className="space-y-3 text-sm text-muted-foreground">
            <div className="flex items-start gap-3">
              <div className="w-6 h-6 bg-success/10 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                <CheckCircle className="w-3.5 h-3.5 text-success" />
              </div>
              <p>Your identity will be recorded with each report for accountability</p>
            </div>
            <div className="flex items-start gap-3">
              <div className="w-6 h-6 bg-success/10 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                <CheckCircle className="w-3.5 h-3.5 text-success" />
              </div>
              <p>Your name and details will be auto-filled from your profile</p>
            </div>
            <div className="flex items-start gap-3">
              <div className="w-6 h-6 bg-success/10 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                <CheckCircle className="w-3.5 h-3.5 text-success" />
              </div>
              <p>Track all your submitted reports in one place</p>
            </div>
          </div>
        </Card>

        {/* Admin Link */}
        <div className="mt-8 text-center">
          <Button
            variant="link"
            onClick={() => navigate('/login')}
            className="text-muted-foreground hover:text-foreground"
          >
            Admin Login →
          </Button>
        </div>
      </div>
    </div>
  );
}
