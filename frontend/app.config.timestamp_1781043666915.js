// app.config.ts
import { defineConfig } from "@tanstack/start/config";
var app_config_default = defineConfig({
  server: {
    preset: "node-server"
  },
  vite: {
    define: {
      "process.env.VITE_API_URL": JSON.stringify(process.env.VITE_API_URL || "http://localhost:8000")
    }
  }
});
export {
  app_config_default as default
};
