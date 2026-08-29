import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { viteSingleFile } from "vite-plugin-singlefile";

// The build is ONE html file, dist/app.html, with every script and stylesheet
// inlined. `python -m opradar.ui` drops the data into it and writes
// ui/index.html, which opens by double-click with no server and no network --
// the same deliverable the hand-written page was, now produced by Vite.
export default defineConfig({
  plugins: [react(), viteSingleFile()],
  base: "./",
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: { input: "app.html" },
    // one ~200KB inline bundle; the chunk-size warning is noise here
    chunkSizeWarningLimit: 1500,
  },
  // no SPA fallback: unknown paths (the Ask box's /ask probe, /favicon.ico) 404
  // instead of being answered with the generated ui/index.html
  appType: "mpa",
  server: { open: "/app.html" },
});
