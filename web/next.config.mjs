import { fileURLToPath } from "node:url";
import { dirname } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  // Pin the workspace root to this app so Next.js doesn't infer it from a
  // stray lockfile higher up the filesystem.
  outputFileTracingRoot: __dirname,
};

export default nextConfig;
