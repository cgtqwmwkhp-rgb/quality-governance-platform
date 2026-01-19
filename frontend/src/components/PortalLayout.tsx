import { useEffect } from 'react';
import { useNavigate, Outlet } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { usePortalAuth } from '../contexts/PortalAuthContext';

export default function PortalLayout() {
  const navigate = useNavigate();
  const { isAuthenticated, isLoading } = usePortalAuth();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      navigate('/portal/login');
    }
  }, [isAuthenticated, isLoading, navigate]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900/20 to-slate-900 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 text-purple-500 animate-spin mx-auto mb-4" />
          <p className="text-gray-400">Loading...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null; // Will redirect to login
  }

  return <Outlet />;
}
