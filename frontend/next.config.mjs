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

/** @type {import('next').NextConfig} */
const nextConfig = {
  basePath: process.env.NEXT_PUBLIC_BASE_PATH || "",
  reactStrictMode: true,
  // Produces .next/standalone for minimal Docker image (no node_modules copy needed).
  output: "standalone",
  async rewrites() {
    const backendUrl =
      process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          {
            key: "X-Frame-Options",
            value: "SAMEORIGIN",
          },
          {
            key: "Content-Security-Policy",
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
