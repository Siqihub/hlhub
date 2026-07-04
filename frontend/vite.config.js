import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";
export default defineConfig({
    plugins: [react()],
    build: {
        outDir: resolve(__dirname, "../src/autody/web/static"),
        emptyOutDir: true
    },
    server: {
        proxy: {
            "/api": "http://127.0.0.1:8765"
        }
    },
    test: {
        environment: "jsdom",
        setupFiles: "./src/test-setup.ts"
    }
});
