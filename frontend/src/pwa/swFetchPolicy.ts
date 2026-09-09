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

/**
 * When the SW fetch fails, classic sw.js used to return a synthetic 503
 * `{error:Offline}`. Axios then sees a response, so execute cannot treat a
 * failed GET as a transport error. Audit GET must reject instead.
 *
 * `frontend/public/sw.js` `networkFirstApi` catch MUST match this.
 */
export function serviceWorkerShouldSynthesizeApiOffline(
  requestUrl: string,
  method: string,
): boolean {
  if (method.toUpperCase() !== 'GET') return true
  try {
    const url = new URL(requestUrl)
    return !url.pathname.startsWith('/api/v1/audits')
  } catch {
    return true
  }
}
