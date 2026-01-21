/// <reference types="vite/client" />

// Build-time constants injected by Vite
declare const __BUILD_VERSION__: string;
declare const __BUILD_TIME__: string;

interface ImportMetaEnv {
  readonly VITE_API_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
