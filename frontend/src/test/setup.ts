import '@testing-library/jest-dom/vitest'

// Some test runs land in environments where jsdom's storage shims are not
// automatically wired (e.g. when a test imports a module that pre-empts the
// global before jsdom finishes setup). Provide a deterministic in-memory
// shim so storage-dependent helpers (auth.ts, session keepalive, etc.)
// always work. This is a no-op when jsdom storage is already functional.
function ensureStorage(name: 'localStorage' | 'sessionStorage') {
  try {
    const candidate = (window as unknown as Record<string, unknown>)[name]
    const looksValid =
      candidate &&
      typeof (candidate as Storage).getItem === 'function' &&
      typeof (candidate as Storage).setItem === 'function' &&
      typeof (candidate as Storage).removeItem === 'function'
    if (looksValid) return
  } catch {
    // fall through and install shim
  }

  const store = new Map<string, string>()
  const shim: Storage = {
    get length() {
      return store.size
    },
    clear: () => {
      store.clear()
    },
    getItem: (key: string) => (store.has(key) ? (store.get(key) as string) : null),
    key: (index: number) => Array.from(store.keys())[index] ?? null,
    removeItem: (key: string) => {
      store.delete(key)
    },
    setItem: (key: string, value: string) => {
      store.set(key, String(value))
    },
  }
  Object.defineProperty(window, name, { configurable: true, writable: true, value: shim })
  Object.defineProperty(globalThis, name, { configurable: true, writable: true, value: shim })
}

ensureStorage('localStorage')
ensureStorage('sessionStorage')

// Mock window.matchMedia for components that use it
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
})

// Mock IntersectionObserver
class MockIntersectionObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
Object.defineProperty(window, 'IntersectionObserver', {
  writable: true,
  value: MockIntersectionObserver,
})

// Mock navigator.sendBeacon
Object.defineProperty(navigator, 'sendBeacon', {
  writable: true,
  value: () => true,
})

Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
  writable: true,
  value: () => {},
})
