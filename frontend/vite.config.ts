import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.svg", "favicon.ico", "icons.svg"],
      manifest: {
        name: "Krishi AI",
        short_name: "KrishiAI",
        description: "Multi-agent agricultural advice for farmers — works offline with a field relay.",
        theme_color: "#1B5E3B",
        background_color: "#F7F4EC",
        display: "standalone",
        start_url: "/",
        icons: [
          {
            src: "favicon.svg",
            sizes: "any",
            type: "image/svg+xml",
            purpose: "any maskable",
          },
        ],
      },
      workbox: {
        // App shell only — never cache API responses.
        navigateFallback: "/index.html",
        globPatterns: ["**/*.{js,css,html,ico,svg,png,jpg,jpeg,webp,woff2}"],
        runtimeCaching: [],
        navigateFallbackDenylist: [/^\/api/, /^\/auth\/(signup|login|me)/, /^\/conversations/],
      },
      devOptions: {
        enabled: false,
      },
    }),
  ],
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
      "/conversations": "http://127.0.0.1:8000",
      "/query": "http://127.0.0.1:8000",
      "/route": "http://127.0.0.1:8000",
      "/crop": "http://127.0.0.1:8000",
      "/audit": "http://127.0.0.1:8000",
      "/voice": "http://127.0.0.1:8000",
      "/feedback": "http://127.0.0.1:8000",
      "/knowledge": "http://127.0.0.1:8000",
      "/help": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
    },
  },
});
