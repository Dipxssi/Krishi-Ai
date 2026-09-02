import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/farmers": "http://127.0.0.1:8000",
      "/query": "http://127.0.0.1:8000",
      "/route": "http://127.0.0.1:8000",
      "/crop": "http://127.0.0.1:8000",
      "/audit": "http://127.0.0.1:8000",
      "/voice": "http://127.0.0.1:8000",
      "/feedback": "http://127.0.0.1:8000",
      "/knowledge": "http://127.0.0.1:8000",
    },
  },
});
