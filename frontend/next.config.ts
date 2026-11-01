import type { NextConfig } from "next";

// All browser calls go to same-origin /api/* and are proxied to FastAPI.
// This avoids CORS and lets phones on your LAN use the app via one URL.
const backend = process.env.BACKEND_URL || "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  experimental: { proxyTimeout: 120_000 },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
  async headers() {
    return [
      {
        source: "/sw.js",
        headers: [
          { key: "Cache-Control", value: "no-cache, no-store, must-revalidate" },
          { key: "Service-Worker-Allowed", value: "/" },
        ],
      },
    ];
  },
};

export default nextConfig;
