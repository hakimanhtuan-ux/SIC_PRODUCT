/** @type {import('next').NextConfig} */
const isStaticExport =
  process.env.GITHUB_PAGES === "true" || process.env.STATIC_EXPORT === "true";
const basePath =
  process.env.GITHUB_PAGES === "true"
    ? process.env.NEXT_PUBLIC_BASE_PATH || ""
    : "";

const nextConfig = {
  reactStrictMode: true,
  eslint: {
    ignoreDuringBuilds: true,
  },
  ...(isStaticExport
    ? {
      output: "export",
      trailingSlash: true,
      basePath,
      assetPrefix: basePath,
      images: {
        unoptimized: true,
      },
    }
    : {
      experimental: {
        proxyTimeout: 120000,
      },
      async rewrites() {
        const backendUrl = (
          process.env.BACKEND_INTERNAL_URL ||
          process.env.NEXT_PUBLIC_API_URL ||
          "https://sic-product-1.onrender.com"
        ).replace(/\/$/, "");
        return [
          {
            source: "/api/v1/:path*",
            destination: `${backendUrl}/api/v1/:path*`,
          },
        ];
      },
    }),
};

export default nextConfig;
