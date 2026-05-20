import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    dedupe: ["react", "react-dom"],
  },
  optimizeDeps: {
    include: [
      "react",
      "react-dom",
      "react/jsx-runtime",
      "@cloudscape-design/components/app-layout",
      "@cloudscape-design/components/box",
      "@cloudscape-design/components/button",
      "@cloudscape-design/components/container",
      "@cloudscape-design/components/content-layout",
      "@cloudscape-design/components/column-layout",
      "@cloudscape-design/components/expandable-section",
      "@cloudscape-design/components/form-field",
      "@cloudscape-design/components/header",
      "@cloudscape-design/components/key-value-pairs",
      "@cloudscape-design/components/select",
      "@cloudscape-design/components/space-between",
      "@cloudscape-design/components/status-indicator",
      "@cloudscape-design/components/spinner",
      "@cloudscape-design/components/textarea",
      "@cloudscape-design/components/top-navigation",
      "@cloudscape-design/components/badge",
      "@cloudscape-design/components/alert",
    ],
  },
  server: {
    port: 5173,
    proxy: {
      "/transcripts": "http://127.0.0.1:8080",
      "/invocations": "http://127.0.0.1:8080",
    },
  },
});
