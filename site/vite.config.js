import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  base: './',
  plugins: [react()],
  build: {
    rollupOptions: {
      input: {
        index: 'index.html',
        en: 'en.html',
      },
    },
  },
  server: {
    port: 8765,
    strictPort: true,
    host: '127.0.0.1',
  },
  preview: {
    port: 8765,
    strictPort: true,
    host: '127.0.0.1',
  },
});
