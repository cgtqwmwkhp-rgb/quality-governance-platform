import { useEffect } from 'react';
import { useAppStore } from '@/stores/useAppStore';

/**
 * Syncs browser online/offline events with the app store.
 * Mount once near the app root (e.g. in App.tsx or Layout).
 */
export function useOnlineStatus() {
  const setOnline = useAppStore((s) => s.setOnline);

  useEffect(() => {
    const handleOnline = () => setOnline(true);
    const handleOffline = () => setOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, [setOnline]);
}
