import type { NextConfig } from "next";

const issuer = process.env.NEXT_PUBLIC_KB_OIDC_ISSUER ? new URL(process.env.NEXT_PUBLIC_KB_OIDC_ISSUER).origin : "";
const dev = process.env.NODE_ENV !== "production";
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${dev ? " 'unsafe-eval'" : ""}`, // Next.js inline bootstrap; no third-party scripts
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' blob: data:",
  "font-src 'self'",
  `connect-src 'self' ${issuer}${dev ? " ws:" : ""}`,
  "frame-ancestors 'none'",
  "base-uri 'self'",
  `form-action 'self' ${issuer}`,
  "object-src 'none'",
].join("; ");

const config: NextConfig = {
  serverExternalPackages: ["pg"],
  poweredByHeader: false,
  async headers() {
    return [{
      source: "/:path*",
      headers: [
        { key: "Content-Security-Policy", value: csp },
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "Referrer-Policy", value: "no-referrer" },
        { key: "X-Frame-Options", value: "DENY" },
        { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
      ],
    }];
  },
};
export default config;
