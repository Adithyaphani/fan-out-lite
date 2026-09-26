import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The backend runs on :8100 by default (override with VITE_BACKEND). In dev we
// proxy /api to it so the frontend can use same-origin relative URLs everywhere.
// Port 8000 is avoided because other tooling in this environment squats on it.
const BACKEND = process.env.VITE_BACKEND || "http://localhost:8100";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": BACKEND,
    },
  },
});
