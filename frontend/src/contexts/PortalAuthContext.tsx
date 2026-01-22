import { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react';

// Microsoft Entra ID (Azure AD) configuration
const MSAL_CONFIG = {
  clientId: import.meta.env.VITE_AZURE_CLIENT_ID || '',
  authority: import.meta.env.VITE_AZURE_AUTHORITY || '',
  redirectUri: import.meta.env.VITE_AZURE_REDIRECT_URI || window.location.origin + '/portal',
};

// API base URL for token exchange
const API_BASE = import.meta.env.VITE_API_URL || 'https://app-qgp-prod.azurewebsites.net';

// Check if Azure AD is properly configured
const isAzureConfigured = () => {
  return (
    MSAL_CONFIG.clientId &&
    MSAL_CONFIG.clientId !== 'your-client-id' &&
    MSAL_CONFIG.authority &&
    MSAL_CONFIG.authority !== 'https://login.microsoftonline.com/your-tenant-id'
  );
};

export interface PortalUser {
  id: string;
  email: string;
  name: string;
  firstName: string;
  lastName: string;
  jobTitle?: string;
  department?: string;
  photo?: string;
  isDemoUser?: boolean;
}

// Token exchange response from backend
interface TokenExchangeResponse {
  access_token: string;
  refresh_token: string;
  user: {
    id: number;
    email: string;
    full_name: string;
    is_superuser: boolean;
  };
}

interface PortalAuthContextType {
  user: PortalUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: () => Promise<void>;
  loginWithDemo: () => void;
  logout: () => void;
  error: string | null;
  isAzureADAvailable: boolean;
  platformToken: string | null;  // Platform JWT for API calls
}

const PortalAuthContext = createContext<PortalAuthContextType | undefined>(undefined);

export function usePortalAuth() {
  const context = useContext(PortalAuthContext);
  if (!context) {
    throw new Error('usePortalAuth must be used within a PortalAuthProvider');
  }
  return context;
}

interface PortalAuthProviderProps {
  children: ReactNode;
}

export function PortalAuthProvider({ children }: PortalAuthProviderProps) {
  const [user, setUser] = useState<PortalUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [platformToken, setPlatformToken] = useState<string | null>(() => {
    // Restore platform token from sessionStorage on mount
    return sessionStorage.getItem('platform_access_token');
  });

  // Exchange Azure AD id_token for platform JWT
  const exchangeToken = async (idToken: string): Promise<TokenExchangeResponse | null> => {
    try {
      console.log('[PortalAuth] Exchanging Azure token for platform token...');
      const response = await fetch(`${API_BASE}/api/v1/auth/token-exchange`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id_token: idToken }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        console.error('[PortalAuth] Token exchange failed:', response.status, errorData);
        return null;
      }

      const data: TokenExchangeResponse = await response.json();
      console.log('[PortalAuth] Token exchange successful for user:', data.user.email);
      
      // Store platform tokens securely (sessionStorage clears on tab close)
      sessionStorage.setItem('platform_access_token', data.access_token);
      sessionStorage.setItem('platform_refresh_token', data.refresh_token);
      setPlatformToken(data.access_token);
      
      return data;
    } catch (err) {
      console.error('[PortalAuth] Token exchange error:', err);
      return null;
    }
  };

  // Parse JWT token
  const parseJwt = (token: string) => {
    try {
      const base64Url = token.split('.')[1];
      const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
      const jsonPayload = decodeURIComponent(
        atob(base64)
          .split('')
          .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
          .join('')
      );
      return JSON.parse(jsonPayload);
    } catch (e) {
      console.error('Failed to parse JWT:', e);
      return null;
    }
  };

  // Handle OAuth callback (check URL for tokens)
  const handleOAuthCallback = useCallback(async (): Promise<boolean> => {
    // Check for id_token in URL hash (fragment response mode)
    const hash = window.location.hash;
    if (hash && hash.includes('id_token')) {
      const params = new URLSearchParams(hash.substring(1));
      const idToken = params.get('id_token');
      const errorParam = params.get('error');
      const errorDesc = params.get('error_description');

      if (errorParam) {
        console.error('OAuth error:', errorParam, errorDesc);
        setError(errorDesc || 'Authentication failed');
        // Clear the hash
        window.history.replaceState(null, '', window.location.pathname);
        return false;
      }

      if (idToken) {
        // Clear the hash from URL immediately to prevent re-processing
        window.history.replaceState(null, '', window.location.pathname);

        // Exchange Azure token for platform token (secure server-side validation)
        const exchangeResult = await exchangeToken(idToken);
        
        if (exchangeResult) {
          // Use server-validated user info from token exchange
          const newUser: PortalUser = {
            id: String(exchangeResult.user.id),
            email: exchangeResult.user.email,
            name: exchangeResult.user.full_name,
            firstName: exchangeResult.user.full_name.split(' ')[0] || 'User',
            lastName: exchangeResult.user.full_name.split(' ').slice(1).join(' ') || '',
            jobTitle: '',
            department: '',
          };

          setUser(newUser);
          localStorage.setItem('portal_user', JSON.stringify(newUser));
          localStorage.setItem('portal_session_time', Date.now().toString());
          // Note: We no longer store portal_id_token - platform token in sessionStorage
          
          return true;
        } else {
          // Token exchange failed - fall back to client-side parsing for user display
          // but mark as not fully authenticated (no platform token)
          const payload = parseJwt(idToken);
          if (payload) {
            const newUser: PortalUser = {
              id: payload.oid || payload.sub || 'unknown',
              email: payload.email || payload.preferred_username || payload.upn || '',
              name: payload.name || 'User',
              firstName: payload.given_name || payload.name?.split(' ')[0] || 'User',
              lastName: payload.family_name || payload.name?.split(' ').slice(1).join(' ') || '',
              jobTitle: payload.jobTitle || '',
              department: payload.department || '',
            };
            setUser(newUser);
            localStorage.setItem('portal_user', JSON.stringify(newUser));
            localStorage.setItem('portal_session_time', Date.now().toString());
            setError('Session established but API access may be limited. Please try logging in again if issues persist.');
          }
          return true;
        }
      }
    }
    return false;
  }, []);

  // Check for existing session on mount
  useEffect(() => {
    const checkSession = async () => {
      setIsLoading(true);
      
      // First check for OAuth callback (async - handles token exchange)
      const wasCallback = await handleOAuthCallback();
      if (wasCallback) {
        setIsLoading(false);
        return;
      }

      try {
        // Check localStorage for existing portal session
        const savedUser = localStorage.getItem('portal_user');
        if (savedUser) {
          const parsedUser = JSON.parse(savedUser);
          // Validate session isn't expired (24 hours)
          const sessionTime = localStorage.getItem('portal_session_time');
          if (sessionTime) {
            const elapsed = Date.now() - parseInt(sessionTime);
            if (elapsed < 24 * 60 * 60 * 1000) {
              setUser(parsedUser);
              // Also restore platform token from sessionStorage if still valid
              const storedPlatformToken = sessionStorage.getItem('platform_access_token');
              if (storedPlatformToken) {
                setPlatformToken(storedPlatformToken);
              }
            } else {
              // Session expired - clear everything
              localStorage.removeItem('portal_user');
              localStorage.removeItem('portal_session_time');
              localStorage.removeItem('portal_id_token');
              sessionStorage.removeItem('platform_access_token');
              sessionStorage.removeItem('platform_refresh_token');
              setPlatformToken(null);
            }
          }
        }
      } catch (err) {
        console.error('Session check failed:', err);
      } finally {
        setIsLoading(false);
      }
    };

    checkSession();
  }, [handleOAuthCallback]);

  // Login with Microsoft (redirect flow - more reliable than popup)
  const login = async () => {
    setIsLoading(true);
    setError(null);

    try {
      if (!isAzureConfigured()) {
        // Azure AD not configured - show helpful error
        setError(
          'Microsoft login is not configured. Please use Demo Login or contact your administrator.'
        );
        setIsLoading(false);
        return;
      }

      // Generate state and nonce for security
      const state = Math.random().toString(36).substring(7);
      const nonce = Math.random().toString(36).substring(7);
      
      // Store state for validation on return
      sessionStorage.setItem('oauth_state', state);
      sessionStorage.setItem('oauth_nonce', nonce);

      // Build authorization URL
      const authUrl = new URL(`${MSAL_CONFIG.authority}/oauth2/v2.0/authorize`);
      authUrl.searchParams.set('client_id', MSAL_CONFIG.clientId);
      authUrl.searchParams.set('response_type', 'id_token');
      authUrl.searchParams.set('redirect_uri', MSAL_CONFIG.redirectUri);
      authUrl.searchParams.set('scope', 'openid profile email');
      authUrl.searchParams.set('response_mode', 'fragment');
      authUrl.searchParams.set('state', state);
      authUrl.searchParams.set('nonce', nonce);
      authUrl.searchParams.set('prompt', 'select_account');

      // Redirect to Microsoft login
      window.location.href = authUrl.toString();
    } catch (err) {
      console.error('Login failed:', err);
      setError('Failed to initiate sign in. Please try again.');
      setIsLoading(false);
    }
  };

  // Demo login for testing/development
  const loginWithDemo = () => {
    const demoUser: PortalUser = {
      id: 'demo-user-001',
      email: 'demo.employee@plantexpand.com',
      name: 'Demo Employee',
      firstName: 'Demo',
      lastName: 'Employee',
      jobTitle: 'Field Engineer',
      department: 'Operations',
      isDemoUser: true,
    };

    setUser(demoUser);
    localStorage.setItem('portal_user', JSON.stringify(demoUser));
    localStorage.setItem('portal_session_time', Date.now().toString());
    setError(null);
  };

  // Logout
  const logout = () => {
    const wasAzureUser = user && !user.isDemoUser && isAzureConfigured();
    
    setUser(null);
    setPlatformToken(null);
    
    // Clear all stored tokens
    localStorage.removeItem('portal_user');
    localStorage.removeItem('portal_session_time');
    localStorage.removeItem('portal_id_token');
    sessionStorage.removeItem('oauth_state');
    sessionStorage.removeItem('oauth_nonce');
    sessionStorage.removeItem('platform_access_token');
    sessionStorage.removeItem('platform_refresh_token');

    // If was Azure AD user, redirect to Microsoft logout
    if (wasAzureUser) {
      const logoutUrl = new URL(`${MSAL_CONFIG.authority}/oauth2/v2.0/logout`);
      logoutUrl.searchParams.set('post_logout_redirect_uri', window.location.origin + '/portal/login');
      window.location.href = logoutUrl.toString();
    }
  };

  return (
    <PortalAuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        login,
        loginWithDemo,
        logout,
        error,
        isAzureADAvailable: isAzureConfigured(),
        platformToken,
      }}
    >
      {children}
    </PortalAuthContext.Provider>
  );
}
