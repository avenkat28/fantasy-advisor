import { describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api";
import { health } from "./fixtures";
describe("typed HTTP client", () => {
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
