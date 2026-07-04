import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: resolve(here, "../src/autody/web/static"),
    emptyOutDir: true
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8765"
    }
  }
});
