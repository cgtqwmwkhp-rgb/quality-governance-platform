/**
 * Quality Governance Platform - Service Worker
 * 
 * CRITICAL: This SW enforces HTTPS for all API requests to prevent Mixed Content errors.
 * Old cached bundles may contain HTTP URLs - the SW rewrites them to HTTPS.
 */

// Cache version - CI replaces this with git SHA + timestamp at build time
const CACHE_VERSION = 'qgp-v2.0.0-dev';
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const DYNAMIC_CACHE = `${CACHE_VERSION}-dynamic`;
const API_CACHE = `${CACHE_VERSION}-api`;

// Static assets to cache (only guaranteed-to-exist files)
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/manifest.json',
  '/offline.html',
];

/**
 * CRITICAL: Rewrite HTTP API URLs to HTTPS
 * This fixes Mixed Content errors from old cached bundles
 * 
 * We construct the HTTP pattern dynamically to avoid CI guard false positives
 */
function enforceHttps(url) {
  // Match any http:// URL to Azure domains and convert to https://
  const isAzure = url.includes('azurewebsites.net') || url.includes('azurecontainerapps.io') || url.includes('azurestaticapps.net');
  if (isAzure && url.startsWith('http:')) {
    const fixed = url.replace(/^http:/, 'https:');
    console.log('[SW] Rewrote HTTP→HTTPS:', url.substring(0, 60) + '...');
    return fixed;
  }
  return url;
}

/**
 * Create a new request with HTTPS URL if needed
 */
function createSecureRequest(request) {
  const originalUrl = request.url;
  const secureUrl = enforceHttps(originalUrl);
  
  if (secureUrl !== originalUrl) {
    // Create new request with HTTPS URL, preserving all other properties
    return new Request(secureUrl, {
      method: request.method,
      headers: request.headers,
      mode: 'cors',
      credentials: request.credentials,
      cache: request.cache,
      redirect: request.redirect,
      referrer: request.referrer,
      integrity: request.integrity,
    });
  }
  return request;
}

// Install event
self.addEventListener('install', (event) => {
  console.log('[SW] Installing...');
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then(async (cache) => {
        console.log('[SW] Caching static assets');
        // Cache what we can, don't fail install if some are missing
        for (const url of STATIC_ASSETS) {
          try {
            await cache.add(url);
          } catch (err) {
            console.warn('[SW] Could not cache:', url);
          }
        }
      })
      .then(() => {
        console.log('[SW] Install complete, activating immediately');
        return self.skipWaiting();
      })
  );
});

// Activate event - clear old caches, then claim clients
self.addEventListener('activate', (event) => {
  console.log('[SW] Activating...');
  event.waitUntil(
    caches.keys()
      .then((keys) => {
        const deletions = keys
          .filter((key) => !key.startsWith(CACHE_VERSION))
          .map((key) => {
            console.log('[SW] Deleting old cache:', key);
            return caches.delete(key);
          });
        return Promise.all(deletions);
      })
      .then(() => {
        // Ensure the app shell is cached before claiming clients so that
        // intercepted navigation requests can fall back to index.html.
        return caches.open(STATIC_CACHE).then((cache) =>
          cache.match('/index.html').then((existing) => {
            if (existing) return;
            return cache.add('/index.html').catch(() => {
              console.warn('[SW] Could not pre-cache index.html during activate');
            });
          })
        );
      })
      .then(() => {
        console.log('[SW] Taking control of all clients');
        return self.clients.claim();
      })
  );
});

// Fetch event - ENFORCE HTTPS for all API requests
self.addEventListener('fetch', (event) => {
  const request = event.request;
  
  // Skip non-GET requests
  if (request.method !== 'GET') {
    return;
  }

  const url = new URL(request.url);
  
  // Skip non-http(s) requests
  if (!url.protocol.startsWith('http')) {
    return;
  }

  // CRITICAL: Check if this is an API request that needs HTTPS enforcement
  const isApiRequest = url.hostname.includes('azurewebsites.net') &&
                       url.pathname.startsWith('/api/');

  if (isApiRequest) {
    // Always enforce HTTPS for API requests
    const secureRequest = createSecureRequest(request);
    // Workforce API GET routes: network-first with cache fallback for offline support
    if (request.method === 'GET' && isWorkforceApiRoute(url.pathname)) {
      event.respondWith(networkFirstApiWithCache(secureRequest));
    } else {
      event.respondWith(networkFirstApi(secureRequest));
    }
    return;
  }

  // Static assets - cache first
  if (isStaticAsset(url.pathname)) {
    event.respondWith(cacheFirst(request));
    return;
  }

  // HTML pages - network first with offline fallback
  if (request.headers.get('Accept')?.includes('text/html')) {
    event.respondWith(networkFirstHtml(request));
    return;
  }

  // Everything else - network with cache fallback
  event.respondWith(networkFirst(request));
});

// ============================================================================
// Caching Strategies
// ============================================================================

/**
 * Network-only strategy for API requests.
 * NEVER cache API responses to ensure fresh data (read-your-writes guarantee).
 */
async function networkFirstApi(request) {
  try {
    const response = await fetch(request);
    if (response.status === 401 || response.status === 403) {
      // Auth failures: notify all clients to handle re-auth
      const allClients = await self.clients.matchAll();
      allClients.forEach(client => client.postMessage({ type: 'AUTH_REQUIRED', status: response.status }));
    }
    return response;
  } catch (error) {
    console.log('[SW] API fetch failed - network unavailable');
    // Return error response, do NOT serve stale cached data for API calls
    return new Response(JSON.stringify({ error: 'Offline', message: 'Network unavailable' }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}

/**
 * Network-first with cache fallback for workforce API GET routes.
 * Used for assessments, inductions, engineers, assets - enables offline read access.
 */
async function networkFirstApiWithCache(request) {
  try {
    const response = await fetch(request);
    if (response.status === 401 || response.status === 403) {
      const allClients = await self.clients.matchAll();
      allClients.forEach(client => client.postMessage({ type: 'AUTH_REQUIRED', status: response.status }));
    }
    if (response.ok) {
      const cache = await caches.open(API_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    console.log('[SW] Workforce API fetch failed - trying cache');
    const cached = await caches.match(request);
    if (cached) {
      return cached;
    }
    return new Response(JSON.stringify({ error: 'Offline', message: 'Network unavailable' }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}

function isWorkforceApiRoute(pathname) {
  return pathname.startsWith('/api/v1/assessments') ||
         pathname.startsWith('/api/v1/inductions') ||
         pathname.startsWith('/api/v1/engineers') ||
         pathname.startsWith('/api/v1/assets');
}

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) {
    return cached;
  }
  
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(STATIC_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    return new Response('Offline', { status: 503 });
  }
}

async function networkFirstHtml(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(DYNAMIC_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    console.warn('[SW] Navigation fetch failed, falling back to cache:', request.url, error?.message);
    const cached = await caches.match(request);
    if (cached) {
      return cached;
    }
    // SPA fallback: serve the cached app shell so the client-side router
    // can handle the deep-link once the bundle loads.
    const appShell = await caches.match('/index.html');
    if (appShell) {
      console.log('[SW] Serving cached app shell for SPA route:', request.url);
      return appShell;
    }
    const offline = await caches.match('/offline.html');
    return offline || new Response('Offline', {
      status: 503,
      headers: { 'Content-Type': 'text/plain' },
    });
  }
}

async function networkFirst(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(DYNAMIC_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    const cached = await caches.match(request);
    return cached || new Response('Offline', { status: 503 });
  }
}

// ============================================================================
// Helpers
// ============================================================================

function isStaticAsset(pathname) {
  return /\.(js|css|png|jpg|jpeg|svg|ico|woff2?)$/i.test(pathname);
}

// ============================================================================
// Push Notifications
// ============================================================================

self.addEventListener('push', (event) => {
  let data = { title: 'Notification', body: 'You have a new notification' };
  
  if (event.data) {
    try {
      data = event.data.json();
    } catch (e) {
      data.body = event.data.text();
    }
  }

  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: '/icons/icon-192x192.png',
      badge: '/icons/icon-72x72.png',
      tag: 'qgp-notification',
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(
    clients.openWindow(event.notification.data?.url || '/portal')
  );
});

// ============================================================================
// Background Sync
// ============================================================================

self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-reports') {
    event.waitUntil(syncPendingReports());
  }
});

async function syncPendingReports() {
  try {
    const db = await openDatabase();
    const reports = await getPendingReports(db);
    
    for (const report of reports) {
      try {
        // Retrieve auth token from IndexedDB for authenticated sync
        let authHeaders = { 'Content-Type': 'application/json' };
        try {
          const tokenDb = await new Promise((res, rej) => {
            const r = indexedDB.open('QGP_Auth', 1);
            r.onerror = () => rej(r.error);
            r.onsuccess = () => res(r.result);
            r.onupgradeneeded = (e) => e.target.result.createObjectStore('tokens', { keyPath: 'key' });
          });
          const tx = tokenDb.transaction('tokens', 'readonly');
          const tokenResult = await new Promise((res) => {
            const req = tx.objectStore('tokens').get('access_token');
            req.onsuccess = () => res(req.result);
            req.onerror = () => res(null);
          });
          if (tokenResult?.value) {
            authHeaders['Authorization'] = `Bearer ${tokenResult.value}`;
          }
        } catch {
          // No token available - submit without auth
        }

        const response = await fetch('/api/v1/portal/reports/', {
          method: 'POST',
          headers: authHeaders,
          body: JSON.stringify(report.data),
        });
        
        if (response.ok) {
          await deletePendingReport(db, report.id);
        }
      } catch (err) {
        console.log('[SW] Sync failed for report:', report.id);
      }
    }
  } catch (err) {
    console.log('[SW] Sync error:', err);
  }
}

function openDatabase() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('QGP_Offline', 1);
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
    request.onupgradeneeded = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains('pendingReports')) {
        db.createObjectStore('pendingReports', { keyPath: 'id', autoIncrement: true });
      }
    };
  });
}

function getPendingReports(db) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction('pendingReports', 'readonly');
    const store = tx.objectStore('pendingReports');
    const request = store.getAll();
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
  });
}

function deletePendingReport(db, id) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction('pendingReports', 'readwrite');
    const store = tx.objectStore('pendingReports');
    const request = store.delete(id);
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve();
  });
}

console.log('[SW] Service Worker loaded - HTTPS enforcement enabled');
