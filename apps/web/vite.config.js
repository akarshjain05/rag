import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5180,
    proxy: {
      "/v1": { target: process.env.VITE_API_PROXY_TARGET || "http://localhost:8000", changeOrigin: true },
      "/health": { target: process.env.VITE_API_PROXY_TARGET || "http://localhost:8000", changeOrigin: true },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './setupTests.js',
  },
});
