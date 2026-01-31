/**
 * EnvironmentMismatchGuard - Blocks API calls if frontend/API environments don't match.
 * 
 * This prevents accidental cross-environment data access (e.g., staging UI -> prod API).
 */

import { useEffect, useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import { validateEnvironmentMatch, getExpectedEnvironment, getApiBaseUrl } from '../config/apiBase';

interface EnvironmentMismatchGuardProps {
  children: React.ReactNode;
}

export function EnvironmentMismatchGuard({ children }: EnvironmentMismatchGuardProps) {
  const [mismatchError, setMismatchError] = useState<string | null>(null);
  const [_isChecking, setIsChecking] = useState(true);

  useEffect(() => {
    async function checkEnvironment() {
      setIsChecking(true);
      const error = await validateEnvironmentMatch();
      setMismatchError(error);
      setIsChecking(false);
    }
    
    checkEnvironment();
  }, []);
  
  // Note: _isChecking is available for loading state if needed in future

  // Show mismatch warning if detected
  if (mismatchError) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-yellow-50 dark:bg-yellow-900/20 p-4">
        <div className="max-w-lg bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6 border-2 border-yellow-400">
          <div className="flex items-center gap-3 mb-4">
            <AlertTriangle className="w-8 h-8 text-yellow-500" />
            <h1 className="text-xl font-bold text-yellow-700 dark:text-yellow-400">
              Environment Mismatch Detected
            </h1>
          </div>
          
          <p className="text-gray-700 dark:text-gray-300 mb-4">
            {mismatchError}
          </p>
          
          <div className="bg-gray-100 dark:bg-gray-700 rounded p-3 text-sm font-mono mb-4">
            <div><strong>Expected:</strong> {getExpectedEnvironment()}</div>
            <div><strong>API URL:</strong> {getApiBaseUrl()}</div>
          </div>
          
          <p className="text-sm text-gray-500 dark:text-gray-400">
            This is a safety measure to prevent cross-environment data access.
            Please ensure you're using the correct URL for your environment.
          </p>
          
          <div className="mt-4 flex gap-2">
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 bg-yellow-500 text-white rounded hover:bg-yellow-600"
            >
              Retry
            </button>
            <button
              onClick={() => setMismatchError(null)}
              className="px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600"
            >
              Continue Anyway (Risky)
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Normal rendering
  return <>{children}</>;
}

export default EnvironmentMismatchGuard;
