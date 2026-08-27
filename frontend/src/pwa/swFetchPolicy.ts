/**
 * Fetch-interception policy for the app-shell service worker.
 *
 * `frontend/public/sw.js` cannot import this module (classic SW script).
 * The origin/API-host check in sw.js MUST stay identical to
 * {@link serviceWorkerShouldHandleFetch}.
 */

export function serviceWorkerShouldHandleFetch(requestUrl: string, swOrigin: string): boolean {
  let url: URL
  try {
    url = new URL(requestUrl)
  } catch {
    return false
  }
  if (url.protocol !== 'http:' && url.protocol !== 'https:') {
    return false
  }
  const isApiRequest =
    url.hostname.endsWith('.azurewebsites.net') && url.pathname.startsWith('/api/')
  return url.origin === swOrigin || isApiRequest
}
