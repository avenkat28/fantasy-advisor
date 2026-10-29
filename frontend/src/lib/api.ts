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

const BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(
  /\/$/,
  "",
);
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
  let response: Response;
  try {
    response = await fetch(
      `${BASE_URL}/api${path}${query.size ? `?${query}` : ""}`,
      {
        signal: signal
          ? AbortSignal.any([signal, AbortSignal.timeout(30000)])
          : AbortSignal.timeout(30000),
        headers: { Accept: "application/json" },
        cache: "no-store",
      },
    );
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new ApiError(
      "Prediction data cannot currently be loaded. Check that the FastAPI server is running and try again.",
      0,
      "network_error",
    );
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(
      body?.error?.message ||
        "The data service could not complete this request.",
      response.status,
      body?.error?.code || "request_failed",
    );
  }
  return response.json() as Promise<T>;
}
export const api = {
  results: (selection: Selection, signal?: AbortSignal) => get<WeeklyResults>("/results", {...selection}, signal),
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
  ) =>
    get<WeeklyProjections>(
      "/projections",
      { ...selection, position, offset, limit },
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
