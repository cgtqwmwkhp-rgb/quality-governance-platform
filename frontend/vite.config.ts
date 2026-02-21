import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import compression from 'vite-plugin-compression'
import { visualizer } from 'rollup-plugin-visualizer'
import { execSync } from 'child_process'

// Get git commit SHA for build versioning
function getGitCommitSha(): string {
  try {
    return execSync('git rev-parse --short HEAD').toString().trim()
  } catch {
    return 'unknown'
  }
}

export default defineConfig({
  plugins: [
    react(),
    compression({ algorithm: 'gzip', threshold: 1024 }),
    ...(process.env.ANALYZE ? [visualizer({ open: true, filename: 'dist/stats.html' })] : []),
  ],
  define: {
    // Inject build version for cache busting and debugging
    __BUILD_VERSION__: JSON.stringify(getGitCommitSha()),
    __BUILD_TIME__: JSON.stringify(new Date().toISOString()),
  },
  build: {
    chunkSizeWarningLimit: 500,
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-ui': ['@radix-ui/react-dialog', '@radix-ui/react-dropdown-menu', '@radix-ui/react-toast', '@radix-ui/react-tooltip'],
          'vendor-state': ['zustand', 'axios'],
        }
      }
    }
  },
  server: {
    proxy: {
      '/api': {
        target: 'https://qgp-staging-plantexpand.azurewebsites.net',
        changeOrigin: true,
      }
    }
  }
})
