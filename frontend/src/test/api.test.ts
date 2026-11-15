import { describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api";
import { health } from "./fixtures";
describe("typed HTTP client", () => {
  it("uses the hosted app origin when a localhost API URL was configured", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    vi.stubGlobal("window", { location: { hostname: "fantasy.example.com" } });
    vi.resetModules();
    try {
      const { api: hostedApi } = await import("@/lib/api");
      const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(health)));
      await hostedApi.health();
      expect(fetchMock).toHaveBeenCalledWith("/api/health", expect.any(Object));
    } finally {
      vi.unstubAllEnvs();
      vi.unstubAllGlobals();
      vi.resetModules();
    }
  });
  it("calls the real backend path with encoded search parameters", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify([])));
    await api.players("A & B");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/players?search=A+%26+B&limit=50",
      expect.objectContaining({ cache: "no-store" }),
    );
  });
  it("preserves structured backend errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          error: { code: "model_unavailable", message: "WR model is missing." },
        }),
        { status: 503 },
      ),
    );
    await expect(
      api.projection("test", { season: 2026, week: 7 }),
    ).rejects.toMatchObject({
      message: "WR model is missing.",
      code: "model_unavailable",
      status: 503,
    });
  });
  it("explains network failures and handles malformed error bodies", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockRejectedValueOnce(new TypeError("Failed to fetch"));
    await expect(api.health()).rejects.toMatchObject({ code: "network_error" });
    fetchMock.mockResolvedValueOnce(
      new Response("Bad gateway", { status: 502 }),
    );
    await expect(api.health()).rejects.toMatchObject({
      status: 502,
      code: "request_failed",
    });
  });
  it("explains a successful HTML response instead of exposing a JSON parse error", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("<html>Fallback</html>"));
    await expect(api.health()).rejects.toMatchObject({ code: "invalid_response", status: 200 });
  });
  it("loads health metadata without substituting sample data", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(health)),
    );
    expect(await api.health()).toEqual(health);
  });
  it("lets intentional request cancellations abort without a network warning", async () => {
    const controller = new AbortController();
    controller.abort();
    vi.spyOn(globalThis, "fetch").mockRejectedValue(
      new DOMException("Aborted", "AbortError"),
    );
    await expect(api.health(controller.signal)).rejects.toMatchObject({
      name: "AbortError",
    });
  });
});
