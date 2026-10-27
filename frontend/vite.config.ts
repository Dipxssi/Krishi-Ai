import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: true,
    port: 5173,
    proxy: {
      // Only API auth routes — not GET /auth (that is the React page).
      "/auth/signup": "http://127.0.0.1:8000",
      "/auth/login": "http://127.0.0.1:8000",
      "/auth/me": "http://127.0.0.1:8000",
      "/farmers": "http://127.0.0.1:8000",
      "/query": "http://127.0.0.1:8000",
      "/route": "http://127.0.0.1:8000",
      "/crop": "http://127.0.0.1:8000",
      "/audit": "http://127.0.0.1:8000",
      "/voice": "http://127.0.0.1:8000",
      "/feedback": "http://127.0.0.1:8000",
      "/knowledge": "http://127.0.0.1:8000",
      "/help": "http://127.0.0.1:8000",
    },
  },
});
