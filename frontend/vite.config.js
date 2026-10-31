import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // `npm run dev` talks to a locally running backend (uvicorn on :8000)
    proxy: { '/api': 'http://localhost:8000' },
  },
  test: { environment: 'node' },
});
