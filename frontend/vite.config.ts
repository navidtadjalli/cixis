/// <reference types="vitest/config" />
import { readFileSync } from "node:fs";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Window/taskbar title is brand-specific (the cafe name). Read the active brand
// (env BRAND, default cixis — same selector as scripts/gen-brand.mjs) and inject
// it into index.html's %APP_TITLE% placeholder at build/dev time. BRAND is set
// for the whole build chain by the electron:build:majaz npm script and by run.sh.
const brandId = process.env.BRAND || "cixis";
let appTitle = "خروج — صندوق کافه";
try {
  const b = JSON.parse(
    readFileSync(new URL(`./brands/${brandId}.json`, import.meta.url), "utf8"),
  );
  appTitle = `${b.cafeName} — صندوق کافه`;
} catch {
  // fall back to the default title if the brand file can't be read
}

// Electron loads the built files via relative paths, so base must be "./".
export default defineConfig({
  plugins: [
    react(),
    {
      name: "brand-html-title",
      transformIndexHtml: (html) => html.replace(/%APP_TITLE%/g, appTitle),
    },
  ],
  base: "./",
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    css: false,
  },
});
