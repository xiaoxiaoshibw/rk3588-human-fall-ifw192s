import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// dev 模式把 /api 代理到本地 Python API 服务器（server.py，默认 8902）。
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5180,
    strictPort: false,
    proxy: {
      "/api": "http://127.0.0.1:8902",
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
  },
  worker: {
    format: "es",
  },
});
