/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
  },
  preview: {
    host: '0.0.0.0',
    port: 4173,
  },
  test: {
    // The components under test read the DOM: a snippet is parsed with
    // DOMParser before it is rendered, so a node environment would not do.
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/tests/setup.ts'],
    css: false,
    coverage: {
      provider: 'v8',
      // lcov is what SonarQube reads; text keeps the summary in the
      // terminal for whoever ran it.
      reporter: ['text', 'lcov'],
      include: ['src/**'],
      exclude: ['src/tests/**', 'src/**/*.d.ts', 'src/main.tsx'],
    },
  },
});
