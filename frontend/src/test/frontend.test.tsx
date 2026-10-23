import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Dashboard from "@/app/page";
import ProjectionsPage from "@/app/projections/page";
import ComparisonPage from "@/app/compare/page";
import PerformancePage from "@/app/performance/page";
import { Navigation } from "@/components/shell";
import { PlayerSearch } from "@/components/player-search";
import { PlayerProfile } from "@/components/player-profile";
import { ProjectionTable } from "@/components/projection-table";
import { SeasonProvider, WeekPicker } from "@/components/season-provider";
import { api, ApiError } from "@/lib/api";
import {
  comparison,
  details,
  health,
  history,
  performance,
  player,
  receiver,
  weekly,
} from "./fixtures";
vi.mock("next/navigation", () => ({ usePathname: () => "/projections" }));
vi.mock("@/components/charts", () => ({
  RankingChart: () => <div>Ranking chart</div>,
  MetricsChart: () => <div>Metrics chart</div>,
  RecentChart: () => <div>Recent chart</div>,
  AccuracyChart: () => <div>Accuracy chart</div>,
}));
vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...original,
    api: {
      health: vi.fn(),
      weekly: vi.fn(),
      players: vi.fn(),
      compare: vi.fn(),
      performance: vi.fn(),
      player: vi.fn(),
      projection: vi.fn(),
      history: vi.fn(),
    },
  };
});
beforeEach(() => {
  localStorage.clear();
  vi.mocked(api.health).mockResolvedValue(health);
  vi.mocked(api.weekly).mockResolvedValue(weekly);
  vi.mocked(api.players).mockResolvedValue([player, receiver]);
  vi.mocked(api.performance).mockResolvedValue(performance);
  vi.mocked(api.compare).mockResolvedValue(comparison);
  vi.mocked(api.player).mockResolvedValue(details);
  vi.mocked(api.projection).mockResolvedValue(player);
  vi.mocked(api.history).mockResolvedValue(history);
});
function renderWithSeason(ui: React.ReactNode) {
  return render(<SeasonProvider>{ui}</SeasonProvider>);
}

describe("workspace and data views", () => {
  it("renders the main dashboard with real API-derived rankings and metrics", async () => {
    renderWithSeason(<Dashboard />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Your edge starts here",
    );
    expect(
      await screen.findByRole("link", { name: /Test Runner/ }),
    ).toHaveAttribute("href", "/players/test-a");
    expect(screen.getByText("4.12")).toBeInTheDocument();
    expect(api.weekly).toHaveBeenCalledWith(
      { season: 2026, week: 7 },
      undefined,
      expect.any(AbortSignal),
    );
  });
  it("provides all five navigation links and marks the active page", () => {
    render(<Navigation />);
    expect(screen.getAllByRole("link")).toHaveLength(5);
    expect(
      screen.getByRole("link", { name: "Weekly Projections" }),
    ).toHaveAttribute("aria-current", "page");
    expect(
      screen.getByRole("link", { name: "Start/Sit Comparison" }),
    ).toHaveAttribute("href", "/compare");
  });
  it("uses coverage metadata and persists an explicitly selected week", async () => {
    renderWithSeason(<WeekPicker />);
    await waitFor(() =>
      expect(screen.getByLabelText("NFL week")).toHaveValue("7"),
    );
    fireEvent.change(screen.getByLabelText("NFL week"), {
      target: { value: "8" },
    });
    expect(JSON.parse(localStorage.getItem("fantasy-selection")!)).toEqual({
      season: 2026,
      week: 8,
    });
  });
  it("searches by partial name and renders links for matches", async () => {
    const user = userEvent.setup();
    render(<PlayerSearch />);
    await user.type(screen.getByLabelText("Search players"), "runner");
    await waitFor(() =>
      expect(api.players).toHaveBeenLastCalledWith(
        "runner",
        expect.any(AbortSignal),
      ),
    );
    expect(screen.getByRole("link", { name: /Test Runner/ })).toHaveAttribute(
      "href",
      "/players/test-a",
    );
  });
  it("handles unknown players and allows recovery from an API error", async () => {
    vi.mocked(api.players).mockRejectedValueOnce(
      new ApiError("Source unavailable", 503, "data_unavailable"),
    );
    render(<PlayerSearch />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Source unavailable",
    );
    vi.mocked(api.players).mockResolvedValue([]);
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("No players found")).toBeInTheDocument();
  });
  it("renders projection values, missing values and empty tables accurately", () => {
    const { rerender } = render(
      <ProjectionTable
        projections={[{ ...player, recent_ppr_mean_3: null }]}
      />,
    );
    expect(screen.getByText("18.5")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
    rerender(<ProjectionTable projections={[]} />);
    expect(
      screen.getByText("No results for this selection"),
    ).toBeInTheDocument();
  });
  it("filters projection names and sorts loaded points", async () => {
    renderWithSeason(<ProjectionsPage />);
    await screen.findByRole("link", { name: /Test Runner/ });
    fireEvent.change(screen.getByLabelText("Sort projected points"), {
      target: { value: "asc" },
    });
    const rows = screen.getAllByRole("row");
    expect(within(rows[1]).getByText("Test Receiver")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Search projected players"), {
      target: { value: "Runner" },
    });
    expect(screen.queryByText("Test Receiver")).not.toBeInTheDocument();
  });
  it("shows unavailable-week messages instead of fabricated rankings", async () => {
    vi.mocked(api.weekly).mockRejectedValue(
      new ApiError(
        "No weekly roster has been published.",
        422,
        "roster_unavailable",
      ),
    );
    renderWithSeason(<ProjectionsPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "No weekly roster has been published.",
    );
    expect(screen.queryByText("0.0")).not.toBeInTheDocument();
  });
  it("explains players excluded from weekly projections", async () => {
    vi.mocked(api.weekly).mockResolvedValue({
      ...weekly,
      unavailable: [
        {
          player_id: "missing",
          code: "insufficient_data",
          message: "No earlier statistics.",
        },
      ],
    });
    renderWithSeason(<ProjectionsPage />);
    expect(
      await screen.findByText("1 players unavailable for projection"),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByText("1 players unavailable for projection"));
    expect(screen.getByText("No earlier statistics.")).toBeInTheDocument();
  });
  it("uses the backend recommendation and close-call explanation", async () => {
    renderWithSeason(<ComparisonPage />);
    const first = await screen.findByRole("list", { name: "Player A results" });
    const second = screen.getByRole("list", { name: "Player B results" });
    fireEvent.click(within(first).getByRole("button", { name: /Test Runner/ }));
    fireEvent.click(
      within(second).getByRole("button", { name: /Test Receiver/ }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Compare players" }));
    expect(
      await screen.findByRole("heading", { name: "Start Test Runner" }),
    ).toBeInTheDocument();
    expect(screen.getByText(comparison.explanation)).toBeInTheDocument();
    expect(screen.getByText("CLOSE CALL")).toBeInTheDocument();
    expect(api.compare).toHaveBeenCalledWith(
      "test-a",
      "test-b",
      { season: 2026, week: 7 },
      expect.any(AbortSignal),
    );
  });
  it("keeps player history usable when projections are missing", async () => {
    vi.mocked(api.projection).mockRejectedValue(
      new ApiError("No trained model available.", 503, "model_unavailable"),
    );
    renderWithSeason(<PlayerProfile id="test-a" />);
    expect(
      await screen.findByRole("heading", { name: "Test Runner" }),
    ).toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "No trained model available.",
    );
    expect(
      screen.getByRole("heading", { name: "Recent game log" }),
    ).toBeInTheDocument();
    expect(
      await screen.findByText("No held-out predictions for this player"),
    ).toBeInTheDocument();
  });
  it("shows actual evaluation periods and unavailable evaluation states", async () => {
    vi.mocked(api.performance).mockResolvedValueOnce({
      ...performance,
      available: false,
      metrics: [],
      message: "Missing evaluation export.",
    });
    render(<PerformancePage />);
    expect(
      await screen.findByText("Missing evaluation export."),
    ).toBeInTheDocument();
  });
  it("renders the model metrics and chronological test period", async () => {
    render(<PerformancePage />);
    expect(await screen.findByText("Test held-out period")).toBeInTheDocument();
    expect(screen.getByText("4.120")).toBeInTheDocument();
    expect(
      screen.getByText(/Historical performance does not guarantee/),
    ).toBeInTheDocument();
  });
  it("displays useful failure states when FastAPI is unavailable", async () => {
    vi.mocked(api.weekly).mockRejectedValue(
      new ApiError(
        "Prediction data cannot currently be loaded.",
        0,
        "network_error",
      ),
    );
    renderWithSeason(<Dashboard />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Prediction data cannot currently be loaded.",
    );
    expect(
      screen.getByRole("button", { name: "Try again" }),
    ).toBeInTheDocument();
  });
});
