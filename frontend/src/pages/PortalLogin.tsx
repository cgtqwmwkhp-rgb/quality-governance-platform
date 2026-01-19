import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Shield, LogIn, Loader2, AlertCircle } from 'lucide-react';
import { usePortalAuth } from '../contexts/PortalAuthContext';

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
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900/20 to-slate-900 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 text-purple-500 animate-spin mx-auto mb-4" />
          <p className="text-gray-400">Checking authentication...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900/20 to-slate-900 flex items-center justify-center p-4">
      <div className="max-w-md w-full">
        {/* Logo & Header */}
        <div className="text-center mb-8">
          <div className="w-20 h-20 bg-gradient-to-br from-purple-500 to-cyan-500 rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-lg shadow-purple-500/30">
            <Shield className="w-10 h-10 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-white mb-2">Employee Portal</h1>
          <p className="text-gray-400">Sign in with your Plantexpand account</p>
        </div>

        {/* Login Card */}
        <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-8">
          {/* Error Message */}
          {error && (
            <div className="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-xl flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm text-red-400 font-medium">Sign in failed</p>
                <p className="text-xs text-red-400/70 mt-1">{error}</p>
              </div>
            </div>
          )}

          {/* SSO Button */}
          <button
            onClick={handleLogin}
            disabled={isLoading}
            className="w-full flex items-center justify-center gap-3 px-6 py-4 bg-white hover:bg-gray-100 text-gray-900 font-semibold rounded-xl transition-all disabled:opacity-50 shadow-lg"
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
          </button>

          <div className="mt-6 text-center">
            <p className="text-xs text-gray-500">
              Use your <span className="text-purple-400">@plantexpand.com</span> email
            </p>
          </div>

          {/* Divider */}
          <div className="my-6 flex items-center gap-4">
            <div className="flex-1 h-px bg-white/10" />
            <span className="text-xs text-gray-500">SECURE SIGN-IN</span>
            <div className="flex-1 h-px bg-white/10" />
          </div>

          {/* Info */}
          <div className="space-y-3 text-sm text-gray-400">
            <div className="flex items-start gap-3">
              <div className="w-6 h-6 bg-green-500/20 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="text-green-400 text-xs">✓</span>
              </div>
              <p>Your identity will be recorded with each report for accountability</p>
            </div>
            <div className="flex items-start gap-3">
              <div className="w-6 h-6 bg-green-500/20 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="text-green-400 text-xs">✓</span>
              </div>
              <p>Your name and details will be auto-filled from your profile</p>
            </div>
            <div className="flex items-start gap-3">
              <div className="w-6 h-6 bg-green-500/20 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="text-green-400 text-xs">✓</span>
              </div>
              <p>Track all your submitted reports in one place</p>
            </div>
          </div>
        </div>

        {/* Admin Link */}
        <div className="mt-8 text-center">
          <button
            onClick={() => navigate('/login')}
            className="text-sm text-gray-600 hover:text-gray-400 transition-colors"
          >
            Admin Login →
          </button>
        </div>
      </div>
    </div>
  );
}
