/// <reference types="vite/client" />

// Build-time constants injected by Vite
declare const __BUILD_VERSION__: string
declare const __BUILD_TIME__: string

interface ImportMetaEnv {
  readonly VITE_API_URL: string
  readonly VITE_PORTAL_HELP_PHONE?: string
  readonly VITE_PORTAL_HELP_EMAIL?: string
  readonly VITE_PORTAL_HELP_CHAT_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
