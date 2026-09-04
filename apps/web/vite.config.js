import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies /v1 and /health to the API so the frontend can always
// call same-origin relative paths -- no CORS configuration needed in dev,
// and no VITE_API_URL to get wrong. In the built/containerized version,
// nginx.conf does the equivalent proxying (see frontend/Dockerfile).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5180,
    proxy: {
      "/v1": { target: process.env.VITE_API_PROXY_TARGET || "http://localhost:8000", changeOrigin: true },
      "/health": { target: process.env.VITE_API_PROXY_TARGET || "http://localhost:8000", changeOrigin: true },
    },
  },
});
