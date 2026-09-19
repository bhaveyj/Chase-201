import type { NextConfig } from "next";

if (process.env.NODE_ENV === "production") {
  const value = process.env.NEXT_PUBLIC_API_URL;
  if (!value) {
    throw new Error("NEXT_PUBLIC_API_URL must be set for a production build");
  }
  const url = new URL(value);
  const local = url.hostname === "localhost" || url.hostname === "127.0.0.1";
  if (url.origin !== value || (url.protocol !== "https:" && !local)) {
    throw new Error(
      "NEXT_PUBLIC_API_URL must be an HTTPS origin without a path (HTTP is allowed locally)",
    );
  }
}

const config: NextConfig = {
  poweredByHeader: false,
  distDir: process.env.NEXT_OUTPUT_DIR || ".next",
  devIndicators: false,
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
        ],
      },
    ];
  },
};
export default config;
