import type { NextConfig } from "next";

/**
 * Confluence domains that are allowed to embed this app in an iframe.
 * Add your Confluence site URLs to NEXT_PUBLIC_CONFLUENCE_ORIGINS (comma-separated)
 * or extend the defaults below.
 */
const confluenceOrigins = [
  "https://*.atlassian.net",
  "https://*.confluence.com",
  ...(process.env.NEXT_PUBLIC_CONFLUENCE_ORIGINS?.split(",").map((s) => s.trim()) ?? []),
].join(" ");

const nextConfig: NextConfig = {
  // Produces .next/standalone for minimal Docker image (no node_modules copy needed).
  output: "standalone",
  async headers() {
    return [
      {
        // Apply to all routes
        source: "/(.*)",
        headers: [
          {
            key: "X-Frame-Options",
            // ALLOW-FROM is deprecated; we rely on CSP frame-ancestors instead
            value: "SAMEORIGIN",
          },
          {
            key: "Content-Security-Policy",
            // frame-ancestors controls who can embed this app.
            // 'self' allows same-origin; confluence origins allow Confluence.
            value: `frame-ancestors 'self' ${confluenceOrigins}`,
          },
          {
            key: "X-Content-Type-Options",
            value: "nosniff",
          },
          {
            key: "Referrer-Policy",
            value: "strict-origin-when-cross-origin",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
