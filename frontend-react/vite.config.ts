import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    environment: "jsdom",
    globals: true,
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
  },
  server: {
    port: 3000,
    proxy: {
      "/api": "http://localhost:9800",
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
  },
});
