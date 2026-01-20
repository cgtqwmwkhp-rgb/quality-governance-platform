import { useNavigate } from 'react-router-dom';
import {
  FileText,
  Search,
  HelpCircle,
  Shield,
  ChevronRight,
  Smartphone,
  LogOut,
  User,
} from 'lucide-react';
import { usePortalAuth } from '../contexts/PortalAuthContext';
import { Card } from '../components/ui/Card';
import { ThemeToggle } from '../components/ui/ThemeToggle';
import { cn } from '../helpers/utils';

export default function Portal() {
  const navigate = useNavigate();
  const { user, logout } = usePortalAuth();

  const handleLogout = () => {
    logout();
    navigate('/portal/login');
  };

  return (
    <div className="min-h-screen bg-surface">
      {/* Header */}
      <header className="bg-card/95 backdrop-blur-lg border-b border-border sticky top-0 z-40">
        <div className="max-w-lg mx-auto px-4 sm:px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl gradient-brand flex items-center justify-center shadow-glow">
                <Shield className="w-5 h-5 text-primary-foreground" />
              </div>
              <div>
                <h1 className="text-foreground font-semibold">Plantexpand</h1>
                <p className="text-muted-foreground text-xs">Employee Portal</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <ThemeToggle />
              <button
                onClick={handleLogout}
                className="p-2 hover:bg-surface rounded-lg transition-colors"
                title="Sign out"
              >
                <LogOut className="w-5 h-5 text-muted-foreground hover:text-foreground" />
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-lg mx-auto px-4 sm:px-6 py-8">
        {/* User Welcome Card */}
        <Card className="p-4 mb-6">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center">
              <User className="w-6 h-6 text-primary" />
            </div>
            <div className="flex-1">
              <p className="text-foreground font-semibold">{user?.name || 'Employee'}</p>
              <p className="text-muted-foreground text-sm">{user?.email}</p>
              {user?.isDemoUser && (
                <span className="inline-block mt-1 px-2 py-0.5 bg-warning/10 text-warning text-xs font-medium rounded-full border border-warning/20">
                  Demo Mode
                </span>
              )}
            </div>
          </div>
        </Card>

        {/* Welcome Message */}
        <div className="text-center mb-8">
          <h2 className="text-2xl font-semibold text-foreground mb-2">What would you like to do?</h2>
          <p className="text-muted-foreground">Select an option below</p>
        </div>

        {/* Main Actions */}
        <div className="space-y-3">
          {/* Primary Action: Submit Report */}
          <button
            onClick={() => navigate('/portal/report')}
            className={cn(
              "w-full flex items-center gap-4 p-5 rounded-2xl transition-all group",
              "bg-primary/5 hover:bg-primary/10 border-2 border-primary/20 hover:border-primary/40"
            )}
          >
            <div className="w-14 h-14 rounded-xl gradient-brand flex items-center justify-center shadow-glow">
              <FileText className="w-7 h-7 text-primary-foreground" />
            </div>
            <div className="flex-1 text-left">
              <h3 className="text-lg font-semibold text-foreground group-hover:text-primary transition-colors">
                Submit a Report
              </h3>
              <p className="text-sm text-muted-foreground">Incident, Near Miss, Complaint, or RTA</p>
            </div>
            <ChevronRight className="w-6 h-6 text-primary group-hover:translate-x-1 transition-transform" />
          </button>

          {/* Secondary Action: Track Status */}
          <Card
            hoverable
            className="p-4 cursor-pointer group"
            onClick={() => navigate('/portal/track')}
          >
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-info/10 rounded-xl flex items-center justify-center">
                <Search className="w-6 h-6 text-info" />
              </div>
              <div className="flex-1 text-left">
                <h3 className="font-semibold text-foreground group-hover:text-info transition-colors">
                  Track My Report
                </h3>
                <p className="text-sm text-muted-foreground">Check status with reference number</p>
              </div>
              <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:translate-x-1 transition-transform" />
            </div>
          </Card>

          {/* Help & Support */}
          <Card
            hoverable
            className="p-4 cursor-pointer group"
            onClick={() => navigate('/portal/help')}
          >
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-muted rounded-xl flex items-center justify-center">
                <HelpCircle className="w-6 h-6 text-muted-foreground" />
              </div>
              <div className="flex-1 text-left">
                <h3 className="font-semibold text-foreground group-hover:text-foreground/80 transition-colors">
                  Help & Support
                </h3>
                <p className="text-sm text-muted-foreground">FAQs and contact information</p>
              </div>
              <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:translate-x-1 transition-transform" />
            </div>
          </Card>
        </div>

        {/* Mobile Optimized Badge */}
        <div className="mt-10 flex items-center justify-center gap-2 text-muted-foreground text-sm">
          <Smartphone className="w-4 h-4" />
          <span>Optimized for mobile devices</span>
        </div>
      </main>

      {/* Admin Login Link */}
      <footer className="fixed bottom-0 left-0 right-0 p-4 text-center bg-card/80 backdrop-blur-sm border-t border-border">
        <button
          onClick={() => navigate('/login')}
          className="text-muted-foreground hover:text-primary text-sm transition-colors"
        >
          Admin Login →
        </button>
      </footer>
    </div>
  );
}
