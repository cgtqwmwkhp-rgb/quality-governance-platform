# ADR-0014: Frontend State Management Strategy

## Status
Accepted

## Context
The platform needs a scalable, predictable state management solution for the React frontend that balances simplicity with the ability to handle complex domain state across 48+ pages.

## Decision
We adopt Zustand as the primary client-side state management library with the following patterns:
- **3 global stores**: AppStore (auth, user context), NotificationStore (real-time alerts), PreferencesStore (UI settings)
- **Server state**: Managed via direct API calls with local component state (useState/useEffect). No global cache layer for server data to avoid staleness.
- **Component-local state**: Used for form inputs, UI toggles, and ephemeral interactions
- **Custom hooks**: 7 reusable hooks (useDataFetch, useWebSocket, useCollaboration, useServiceWorker, useFeatureFlag, useFormAutosave, useGeolocation) encapsulate cross-cutting concerns

## Consequences
- Minimal bundle impact (~2KB for Zustand vs 30KB+ for Redux)
- No boilerplate reducers/actions — stores are simple JavaScript objects
- Server data is always fresh (no stale cache issues)
- Trade-off: no built-in server data cache deduplication (acceptable given our page-level data loading pattern)
