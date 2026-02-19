import path from "node:path";
import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react-swc";
import { defineConfig, loadEnv } from "vite";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_ALLOWED_HOSTS = ["localhost", "127.0.0.1", ".ngrok-free.app"];

function parseAllowedHosts(rawValue: string | undefined): string[] {
  if (!rawValue) {
    return [];
  }
  return rawValue
    .split(",")
    .map((host) => host.trim())
    .filter(Boolean);
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, __dirname, "");
  const allowedHosts = Array.from(
    new Set([
      ...DEFAULT_ALLOWED_HOSTS,
      ...parseAllowedHosts(env.VITE_ALLOWED_HOSTS),
    ]),
  );

  return {
    plugins: [react()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "src"),
      },
    },
    server: {
      host: "0.0.0.0",
      allowedHosts,
    },
    preview: {
      host: "0.0.0.0",
      allowedHosts,
    },
    build: {
      rollupOptions: {
        input: {
          app: path.resolve(__dirname, "index.html"),
          miniapp: path.resolve(__dirname, "miniapp.html"),
          publicStats: path.resolve(__dirname, "public-stats.html"),
        },
      },
    },
  };
});
