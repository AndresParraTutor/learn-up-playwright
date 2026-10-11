/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => ({
  define: {
    __LEARNUP_HOSTED__: JSON.stringify(mode === "hosted"),
  },
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8011",
      "/media": "http://127.0.0.1:8011"
    }
  },
  test: {
    environment: "jsdom"
  }
}));
