import { afterEach, describe, expect, it, vi } from "vitest";
import { PHASE_DEVELOPMENT_SERVER, PHASE_PRODUCTION_BUILD } from "next/constants";
import createConfig from "../../next.config";

afterEach(() => vi.unstubAllEnvs());

describe("same-origin local proxy", () => {
  it("does not embed a localhost backend route in a production build", async () => {
    vi.stubEnv("FANTASY_LOCAL_API_URL", undefined);
    expect(await createConfig(PHASE_PRODUCTION_BUILD).rewrites!()).toEqual([]);
  });

  it("proxies local development API calls without stripping /api", async () => {
    vi.stubEnv("FANTASY_LOCAL_API_URL", undefined);
    expect(await createConfig(PHASE_DEVELOPMENT_SERVER).rewrites!()).toEqual([
      { source: "/api/:path*", destination: "http://localhost:8000/api/:path*" },
    ]);
  });

  it("supports an explicit local integration-test proxy", async () => {
    vi.stubEnv("FANTASY_LOCAL_API_URL", "http://localhost:8765/");
    expect(await createConfig(PHASE_PRODUCTION_BUILD).rewrites!()).toEqual([
      { source: "/api/:path*", destination: "http://localhost:8765/api/:path*" },
    ]);
  });
});
