import type { NextConfig } from "next";
import { PHASE_DEVELOPMENT_SERVER } from "next/constants";

export default function config(phase: string): NextConfig {
  // Vercel Services owns production routing. This proxy is only for local dev,
  // or an explicit local integration-test build; never set it on Vercel.
  const localBackend =
    process.env.FANTASY_LOCAL_API_URL ||
    (phase === PHASE_DEVELOPMENT_SERVER ? "http://localhost:8000" : undefined);
  return {
    agentRules: false,
    async rewrites() {
      return localBackend
        ? [
            {
              source: "/api/:path*",
              destination: `${localBackend.replace(/\/$/, "")}/api/:path*`,
            },
          ]
        : [];
    },
  };
}
