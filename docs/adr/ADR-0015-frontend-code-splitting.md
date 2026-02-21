# ADR-0015: Frontend Code Splitting Strategy

## Status
Accepted

## Context
The platform has 48+ pages and uses heavy UI libraries (Radix UI, React). Loading everything upfront would result in a large initial bundle, harming first-load performance.

## Decision
We implement a multi-layer code splitting strategy:
1. **Route-level splitting**: All 48 page components are lazy-loaded via `React.lazy()` with a shared `<Suspense>` boundary and `LoadingFallback` component
2. **Vendor chunking**: Manual chunk splitting via `rollupOptions.output.manualChunks`:
   - `vendor-react`: react, react-dom, react-router-dom
   - `vendor-ui`: @radix-ui/* components
   - `vendor-state`: zustand, axios
3. **Build-time compression**: gzip compression via vite-plugin-compression for assets > 1KB
4. **Error boundaries**: `PageErrorBoundary` wraps route content for graceful degradation
5. **Chunk size limits**: Warning threshold at 500KB to catch bundle bloat

## Consequences
- Initial load only downloads core React + router + current page
- Vendor chunks are cached independently (high cache hit rate)
- Lazy pages load on navigation with skeleton/loading feedback
- Trade-off: Slightly slower first navigation to a new page (acceptable with skeleton UX)
