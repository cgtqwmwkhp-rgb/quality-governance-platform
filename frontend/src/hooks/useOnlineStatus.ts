import { useState, useEffect } from "react";
import { useAppStore } from "@/stores/useAppStore";

/**
 * Syncs browser online/offline events with the app store and
 * returns the current online state for component-level usage.
 */
export function useOnlineStatus(): boolean {
  const setOnline = useAppStore((s) => s.setOnline);
  const [isOnline, setIsOnline] = useState(navigator.onLine);

  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true);
      setOnline(true);
    };
    const handleOffline = () => {
      setIsOnline(false);
      setOnline(false);
    };

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, [setOnline]);

  return isOnline;
}
