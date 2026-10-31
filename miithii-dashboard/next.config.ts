import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // static export — the dashboard is 100% client-rendered and talks to the
  // engine API from the browser, so it hosts as plain files (Cloudflare Pages)
  output: "export",
  images: { unoptimized: true },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
