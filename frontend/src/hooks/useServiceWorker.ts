/**
 * Service Worker Hook for PWA functionality
 * Handles registration, updates, and push notifications
 */

import { useState, useEffect, useCallback } from 'react';

interface ServiceWorkerState {
  isSupported: boolean;
  isRegistered: boolean;
  isOnline: boolean;
  hasUpdate: boolean;
  registration: ServiceWorkerRegistration | null;
  pushSubscription: PushSubscription | null;
}

interface UseServiceWorkerReturn extends ServiceWorkerState {
  registerSW: () => Promise<void>;
  updateSW: () => Promise<void>;
  subscribeToPush: () => Promise<PushSubscription | null>;
  unsubscribeFromPush: () => Promise<boolean>;
  savePendingReport: (report: unknown) => Promise<void>;
  syncPendingReports: () => Promise<void>;
}

// VAPID public key for push notifications (generate your own for production)
const VAPID_PUBLIC_KEY = 'BEl62iUYgUivxIkv69yViEuiBIa-Ib9-SkvMeAtA3LFgDzkrxZJjSgSnfckjBJuBkr3qBUYIHBQFLXYp5Nksh8U';

export function useServiceWorker(): UseServiceWorkerReturn {
  const [state, setState] = useState<ServiceWorkerState>({
    isSupported: false,
    isRegistered: false,
    isOnline: navigator.onLine,
    hasUpdate: false,
    registration: null,
    pushSubscription: null,
  });

  // Check for service worker support
  useEffect(() => {
    setState((prev) => ({
      ...prev,
      isSupported: 'serviceWorker' in navigator && 'PushManager' in window,
    }));
  }, []);

  // Handle online/offline status
  useEffect(() => {
    const handleOnline = () => setState((prev) => ({ ...prev, isOnline: true }));
    const handleOffline = () => setState((prev) => ({ ...prev, isOnline: false }));

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  // Register service worker
  const registerSW = useCallback(async () => {
    if (!state.isSupported) return;

    try {
      const registration = await navigator.serviceWorker.register('/sw.js', {
        scope: '/',
      });

      console.log('[SW] Registered:', registration.scope);

      // Check for updates
      registration.addEventListener('updatefound', () => {
        const newWorker = registration.installing;
        if (newWorker) {
          newWorker.addEventListener('statechange', () => {
            if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
              console.log('[SW] New version available');
              setState((prev) => ({ ...prev, hasUpdate: true }));
            }
          });
        }
      });

      // Get push subscription if exists
      let pushSubscription = null;
      try {
        pushSubscription = await registration.pushManager.getSubscription();
      } catch (e) {
        console.log('[SW] Push not available');
      }

      setState((prev) => ({
        ...prev,
        isRegistered: true,
        registration,
        pushSubscription,
      }));
    } catch (error) {
      console.error('[SW] Registration failed:', error);
    }
  }, [state.isSupported]);

  // Update service worker
  const updateSW = useCallback(async () => {
    if (!state.registration) return;

    try {
      await state.registration.update();
      // Force reload with new service worker
      if (state.registration.waiting) {
        state.registration.waiting.postMessage({ type: 'SKIP_WAITING' });
        window.location.reload();
      }
    } catch (error) {
      console.error('[SW] Update failed:', error);
    }
  }, [state.registration]);

  // Subscribe to push notifications
  const subscribeToPush = useCallback(async (): Promise<PushSubscription | null> => {
    if (!state.registration) return null;

    try {
      // Request notification permission
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') {
        console.log('[SW] Notification permission denied');
        return null;
      }

      // Subscribe to push
      const subscription = await state.registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
      });

      console.log('[SW] Push subscription:', subscription);

      // Send subscription to backend
      await fetch('/api/notifications/subscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(subscription),
      });

      setState((prev) => ({ ...prev, pushSubscription: subscription }));
      return subscription;
    } catch (error) {
      console.error('[SW] Push subscription failed:', error);
      return null;
    }
  }, [state.registration]);

  // Unsubscribe from push notifications
  const unsubscribeFromPush = useCallback(async (): Promise<boolean> => {
    if (!state.pushSubscription) return false;

    try {
      await state.pushSubscription.unsubscribe();
      setState((prev) => ({ ...prev, pushSubscription: null }));
      return true;
    } catch (error) {
      console.error('[SW] Unsubscribe failed:', error);
      return false;
    }
  }, [state.pushSubscription]);

  // Save pending report to IndexedDB for offline sync
  const savePendingReport = useCallback(async (report: unknown): Promise<void> => {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open('QGP_Offline', 1);

      request.onerror = () => reject(request.error);

      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;
        if (!db.objectStoreNames.contains('pendingReports')) {
          db.createObjectStore('pendingReports', { keyPath: 'id', autoIncrement: true });
        }
      };

      request.onsuccess = () => {
        const db = request.result;
        const transaction = db.transaction('pendingReports', 'readwrite');
        const store = transaction.objectStore('pendingReports');
        
        const addRequest = store.add({
          data: report,
          timestamp: Date.now(),
        });

        addRequest.onsuccess = () => {
          console.log('[SW] Report saved for offline sync');
          resolve();
        };
        addRequest.onerror = () => reject(addRequest.error);
      };
    });
  }, []);

  // Request background sync for pending reports
  const syncPendingReports = useCallback(async (): Promise<void> => {
    if (!state.registration) return;

    try {
      if ('sync' in state.registration) {
        // @ts-expect-error - sync is not in the types
        await state.registration.sync.register('sync-reports');
        console.log('[SW] Background sync registered');
      }
    } catch (error) {
      console.error('[SW] Background sync failed:', error);
    }
  }, [state.registration]);

  // Auto-register on mount
  useEffect(() => {
    if (state.isSupported && !state.isRegistered) {
      registerSW();
    }
  }, [state.isSupported, state.isRegistered, registerSW]);

  return {
    ...state,
    registerSW,
    updateSW,
    subscribeToPush,
    unsubscribeFromPush,
    savePendingReport,
    syncPendingReports,
  };
}

// Helper: Convert base64 to Uint8Array for VAPID key
function urlBase64ToUint8Array(base64String: string): Uint8Array<ArrayBuffer> {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding)
    .replace(/-/g, '+')
    .replace(/_/g, '/');

  const rawData = window.atob(base64);
  const buffer = new ArrayBuffer(rawData.length);
  const outputArray = new Uint8Array(buffer);

  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }

  return outputArray;
}

export default useServiceWorker;
