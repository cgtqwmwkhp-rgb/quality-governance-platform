import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    testTimeout: 10000,
    hookTimeout: 15000,
    teardownTimeout: 15000,
    retry: 2,
    // Parallel+coverage has hung a worker at 100% CPU in CI (Frontend Tests).
    // Cap forks in CI; keep local default concurrency.
    pool: 'forks',
    fileParallelism: true,
    maxWorkers: process.env.CI ? 2 : undefined,
    minWorkers: process.env.CI ? 1 : undefined,
    poolOptions: {
      forks: {
        singleFork: false,
        isolate: true,
      },
    },
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/test/**', 'src/**/*.d.ts', 'src/**/*.stories.{ts,tsx}'],
      thresholds: {
        statements: 39,
      },
    },
  },
});
