import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Shield, Loader2, AlertCircle, CheckCircle, User } from 'lucide-react';
import { usePortalAuth } from '../contexts/PortalAuthContext';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { ThemeToggle } from '../components/ui/ThemeToggle';

export default function PortalLogin() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { 
    isAuthenticated, 
    isLoading, 
    login, 
    loginWithDemo, 
    error, 
    isAzureADAvailable 
  } = usePortalAuth();

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated && !isLoading) {
      navigate('/portal');
    }
  }, [isAuthenticated, isLoading, navigate]);

  const handleMicrosoftLogin = async () => {
    await login();
  };

  const handleDemoLogin = () => {
    loginWithDemo();
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 text-primary animate-spin mx-auto mb-4" />
          <p className="text-muted-foreground">{t('portal.checking_auth')}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-surface flex items-center justify-center p-4 relative">
      {/* Theme Toggle */}
      <div className="absolute top-4 right-4">
        <ThemeToggle />
      </div>

      {/* Subtle gradient glow */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-primary/5 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-primary/10 rounded-full blur-3xl" />
      </div>

      <div className="max-w-md w-full relative animate-fade-in">
        {/* Logo & Header */}
        <div className="text-center mb-8">
          <div className="w-20 h-20 rounded-2xl gradient-brand flex items-center justify-center mx-auto mb-6 shadow-glow">
            <Shield className="w-10 h-10 text-primary-foreground" />
          </div>
          <h1 className="text-3xl font-bold text-foreground mb-2">{t('portal.employee_portal')}</h1>
          <p className="text-muted-foreground">{t('portal.sign_in_subtitle')}</p>
        </div>

        {/* Login Card */}
        <Card className="p-8">
          {/* Error Message */}
          {error && (
            <div className="mb-6 p-4 bg-destructive/10 border border-destructive/20 rounded-xl flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-destructive flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm text-destructive font-medium">{t('portal.sign_in_issue')}</p>
                <p className="text-xs text-destructive/70 mt-1">{error}</p>
              </div>
            </div>
          )}

          {/* Microsoft SSO Button */}
          <Button
            onClick={handleMicrosoftLogin}
            disabled={isLoading}
            variant="outline"
            size="xl"
            className="w-full"
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
                {t('portal.sign_in_microsoft')}
              </>
            )}
          </Button>

          {isAzureADAvailable && (
            <div className="mt-4 text-center">
              <p className="text-xs text-muted-foreground">
                Use your <span className="text-primary font-medium">@plantexpand.com</span> email
              </p>
            </div>
          )}

          {/* Divider */}
          <div className="my-6 flex items-center gap-4">
            <div className="flex-1 h-px bg-border" />
            <span className="text-xs text-muted-foreground">{t('portal.or_divider')}</span>
            <div className="flex-1 h-px bg-border" />
          </div>

          {/* Demo Login Button */}
          <Button
            onClick={handleDemoLogin}
            variant="secondary"
            size="lg"
            className="w-full"
          >
            <User className="w-4 h-4" />
            {t('portal.continue_demo')}
          </Button>

          <p className="text-xs text-muted-foreground text-center mt-3">
            {t('portal.demo_explore')}
          </p>

          {/* Divider */}
          <div className="my-6 flex items-center gap-4">
            <div className="flex-1 h-px bg-border" />
            <span className="text-xs text-muted-foreground">{t('portal.secure_sign_in')}</span>
            <div className="flex-1 h-px bg-border" />
          </div>

          {/* Info */}
          <div className="space-y-3 text-sm text-muted-foreground">
            <div className="flex items-start gap-3">
              <div className="w-6 h-6 bg-success/10 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                <CheckCircle className="w-3.5 h-3.5 text-success" />
              </div>
              <p>{t('portal.info_identity')}</p>
            </div>
            <div className="flex items-start gap-3">
              <div className="w-6 h-6 bg-success/10 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                <CheckCircle className="w-3.5 h-3.5 text-success" />
              </div>
              <p>{t('portal.info_autofill')}</p>
            </div>
            <div className="flex items-start gap-3">
              <div className="w-6 h-6 bg-success/10 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                <CheckCircle className="w-3.5 h-3.5 text-success" />
              </div>
              <p>{t('portal.info_tracking')}</p>
            </div>
          </div>
        </Card>

        {/* Admin Link */}
        <div className="mt-8 text-center">
          <Button
            variant="link"
            onClick={() => navigate('/login')}
            className="text-muted-foreground hover:text-primary"
          >
            {t('portal.admin_login')}
          </Button>
        </div>
      </div>
    </div>
  );
}
