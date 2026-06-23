/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tsconfigPaths from 'vite-tsconfig-paths'

export default defineConfig({
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: [],
    include: ['tests/**/*.test.{ts,tsx}'],
    exclude: ['tests/**/*.test.tsx'],  // tsx handled by Playwright
  },
  plugins: [react(), tsconfigPaths()],
  define: {
    'process.env.VITE_API_URL': JSON.stringify(
      process.env.VITE_API_URL || 'http://localhost:8000',
    ),
    'process.env.VITE_SENTRY_DSN': JSON.stringify(
      process.env.VITE_SENTRY_DSN || '',
    ),
  },
  server: {
    port: 3000,
  },
})
