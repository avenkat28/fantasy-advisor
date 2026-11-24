import type {
  Comparison,
  WeeklyResults,
  Health,
  Performance,
  Player,
  PlayerDetails,
  PredictionHistory,
  Projection,
  Selection,
  WeeklyProjections,
} from "./types";

const configuredBase = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(/\/$/, "");
// A hosted browser must never send requests to the visitor's own computer.
function apiBase() {
  if (typeof window !== "undefined" && !["localhost", "127.0.0.1", "[::1]"].includes(window.location.hostname)) {
    try {
      if (["localhost", "127.0.0.1", "[::1]"].includes(new URL(configuredBase).hostname)) return "";
    } catch { /* An empty or relative base uses the app's origin. */ }
  }
  return configuredBase;
}
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
type Parameters = Record<string, string | number | undefined>;
async function get<T>(
  path: string,
  params: Parameters = {},
  signal?: AbortSignal,
): Promise<T> {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined) query.set(key, String(value));
  });
  const controller = new AbortController();
  const cancel = () => controller.abort(signal?.reason);
  if (signal?.aborted) cancel();
  else signal?.addEventListener("abort", cancel, { once: true });
  const timeout = setTimeout(() => controller.abort(), 60000);
  let response: Response;
  try {
    response = await fetch(
      `${apiBase()}/api${path}${query.size ? `?${query}` : ""}`,
      {
        signal: controller.signal,
        headers: { Accept: "application/json" },
        cache: "no-store",
      },
    );
  } catch (error) {
    clearTimeout(timeout);
    signal?.removeEventListener("abort", cancel);
    if (signal?.aborted) throw error;
    throw new ApiError(
      "The data service could not be reached or took too long to respond. Please try again.",
      0,
      "network_error",
    );
  }
  try {
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new ApiError(
        body?.error?.message ||
          "The data service could not complete this request.",
        response.status,
        body?.error?.code || "request_failed",
      );
    }
    try {
      return await response.json() as T;
    } catch {
      throw new ApiError(
        "The data service returned an invalid response. Please try again.",
        response.status,
        "invalid_response",
      );
    }
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener("abort", cancel);
  }
}
export const api = {
  results: (selection: Selection, signal?: AbortSignal, includeCurrent = false) =>
    get<WeeklyResults>("/results", { ...selection, include_current: includeCurrent ? 1 : undefined }, signal),
  health: (signal?: AbortSignal) => get<Health>("/health", {}, signal),
  players: (search = "", signal?: AbortSignal) =>
    get<Player[]>("/players", { search, limit: 50 }, signal),
  player: (id: string, signal?: AbortSignal) =>
    get<PlayerDetails>(`/players/${encodeURIComponent(id)}`, {}, signal),
  projection: (id: string, selection: Selection, signal?: AbortSignal) =>
    get<Projection>(
      `/projections/${encodeURIComponent(id)}`,
      { ...selection },
      signal,
    ),
  weekly: (
    selection: Selection,
    position?: string,
    signal?: AbortSignal,
    offset = 0,
    limit = 500,
    includeSaved = false,
  ) =>
    get<WeeklyProjections>(
      "/projections",
      { ...selection, position, offset, limit, include_saved: includeSaved ? 1 : undefined },
      signal,
    ),
  compare: (
    first: string,
    second: string,
    selection: Selection,
    signal?: AbortSignal,
  ) =>
    get<Comparison>(
      "/compare",
      { player1_id: first, player2_id: second, ...selection },
      signal,
    ),
  performance: (signal?: AbortSignal) =>
    get<Performance>("/model/performance", {}, signal),
  history: (id: string, signal?: AbortSignal) =>
    get<PredictionHistory>(
      "/predictions/history",
      { player_id: id, limit: 500 },
      signal,
    ),
};
