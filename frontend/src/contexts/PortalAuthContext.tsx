import { createContext, useContext, useState, useEffect, ReactNode } from 'react';

// Microsoft Entra ID (Azure AD) configuration
const MSAL_CONFIG = {
  clientId: import.meta.env.VITE_AZURE_CLIENT_ID || 'your-client-id',
  authority: import.meta.env.VITE_AZURE_AUTHORITY || 'https://login.microsoftonline.com/your-tenant-id',
  redirectUri: import.meta.env.VITE_AZURE_REDIRECT_URI || window.location.origin + '/portal',
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
}

interface PortalAuthContextType {
  user: PortalUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: () => Promise<void>;
  logout: () => void;
  error: string | null;
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

  // Check for existing session on mount
  useEffect(() => {
    checkExistingSession();
  }, []);

  const checkExistingSession = async () => {
    setIsLoading(true);
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
          } else {
            // Session expired
            localStorage.removeItem('portal_user');
            localStorage.removeItem('portal_session_time');
          }
        }
      }
    } catch (err) {
      console.error('Session check failed:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const login = async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      // In production, this would use MSAL.js to authenticate with Azure AD
      // For now, we'll simulate the SSO flow with a popup
      
      // Check if MSAL is configured
      if (MSAL_CONFIG.clientId === 'your-client-id') {
        // Development mode - simulate SSO
        const mockUser: PortalUser = {
          id: 'dev-user-001',
          email: 'employee@plantexpand.com',
          name: 'Development User',
          firstName: 'Development',
          lastName: 'User',
          jobTitle: 'Mobile Engineer',
          department: 'Operations',
        };
        
        setUser(mockUser);
        localStorage.setItem('portal_user', JSON.stringify(mockUser));
        localStorage.setItem('portal_session_time', Date.now().toString());
        setIsLoading(false);
        return;
      }

      // Production MSAL flow
      const popup = window.open(
        `${MSAL_CONFIG.authority}/oauth2/v2.0/authorize?` +
        `client_id=${MSAL_CONFIG.clientId}` +
        `&response_type=id_token` +
        `&redirect_uri=${encodeURIComponent(MSAL_CONFIG.redirectUri)}` +
        `&scope=openid profile email User.Read` +
        `&response_mode=fragment` +
        `&nonce=${Math.random().toString(36).substring(7)}`,
        'Microsoft SSO',
        'width=500,height=600,scrollbars=yes'
      );

      // Listen for the popup to complete
      const checkPopup = setInterval(() => {
        try {
          if (popup?.closed) {
            clearInterval(checkPopup);
            checkExistingSession();
          }
          
          // Check if we got a response
          if (popup?.location?.hash) {
            const hash = popup.location.hash.substring(1);
            const params = new URLSearchParams(hash);
            const idToken = params.get('id_token');
            
            if (idToken) {
              // Parse the JWT token
              const payload = JSON.parse(atob(idToken.split('.')[1]));
              
              const newUser: PortalUser = {
                id: payload.oid || payload.sub,
                email: payload.email || payload.preferred_username,
                name: payload.name,
                firstName: payload.given_name || payload.name?.split(' ')[0],
                lastName: payload.family_name || payload.name?.split(' ').slice(1).join(' '),
                jobTitle: payload.jobTitle,
                department: payload.department,
              };
              
              setUser(newUser);
              localStorage.setItem('portal_user', JSON.stringify(newUser));
              localStorage.setItem('portal_session_time', Date.now().toString());
              
              popup.close();
              clearInterval(checkPopup);
            }
          }
        } catch (e) {
          // Cross-origin errors are expected until redirect completes
        }
      }, 500);

    } catch (err) {
      console.error('Login failed:', err);
      setError('Failed to sign in. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem('portal_user');
    localStorage.removeItem('portal_session_time');
    
    // In production, also sign out from Azure AD
    if (MSAL_CONFIG.clientId !== 'your-client-id') {
      window.location.href = `${MSAL_CONFIG.authority}/oauth2/v2.0/logout?post_logout_redirect_uri=${encodeURIComponent(window.location.origin + '/portal')}`;
    }
  };

  return (
    <PortalAuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        login,
        logout,
        error,
      }}
    >
      {children}
    </PortalAuthContext.Provider>
  );
}
