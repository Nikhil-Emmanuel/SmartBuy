import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  server: {
    // 5173 by default, but let the environment win: tooling that assigns a
    // port (and CI runners sharing a machine) cannot use a hardcoded one.
    port: Number(process.env.PORT) || 5173,
    // The backend runs on 8000. Proxying keeps dev same-origin, so CORS
    // misconfiguration on stage cannot silently break the demo.
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
