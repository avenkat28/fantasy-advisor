"use client";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type {
  HistoricalGame,
  HistoryRecord,
  Metric,
  Projection,
} from "@/lib/types";
const grid = "var(--border)";
const tooltipStyle = {
  background: "var(--surface)",
  border: "1px solid var(--border)",
  borderRadius: 10,
  color: "var(--text)",
};
const tick = { fill: "var(--muted)", fontSize: 11 };
export function RecentChart({ games }: { games: HistoricalGame[] }) {
  const rows = games.map((g) => ({
    label: `${g.season} W${g.week}`,
    Points: g.fantasy_points_ppr ?? null,
  }));
  return (
    <div
      className="chart"
      role="img"
      aria-label="Recent historical fantasy points; exact values are in the recent games table"
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={rows}
          margin={{ left: -20, right: 18, top: 15, bottom: 8 }}
        >
          <CartesianGrid stroke={grid} strokeDasharray="3 5" vertical={false} />
          <XAxis
            dataKey="label"
            tick={tick}
            axisLine={false}
            tickLine={false}
          />
          <YAxis tick={tick} axisLine={false} tickLine={false} />
          <Tooltip contentStyle={tooltipStyle} />
          <Line
            type="monotone"
            dataKey="Points"
            stroke="var(--mint)"
            strokeWidth={3}
            dot={{ r: 4, fill: "var(--surface)", strokeWidth: 2 }}
            connectNulls={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
export function RankingChart({ players }: { players: Projection[] }) {
  return (
    <div
      className="chart"
      role="img"
      aria-label="Top selected-week projections; exact values are in the player ranking tables"
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={players
            .slice(0, 7)
            .map((p) => ({
              name: p.player_name,
              "Projected Points": p.projected_ppr_points,
            }))}
          layout="vertical"
          margin={{ left: 16, right: 20 }}
        >
          <CartesianGrid
            stroke={grid}
            strokeDasharray="3 5"
            horizontal={false}
          />
          <XAxis type="number" tick={tick} axisLine={false} tickLine={false} />
          <YAxis
            type="category"
            dataKey="name"
            width={125}
            tick={tick}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "var(--surface-raised)" }} />
          <Bar
            dataKey="Projected Points"
            fill="var(--mint)"
            barSize={12}
            radius={[0, 4, 4, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
export function MetricsChart({ metrics }: { metrics: Metric[] }) {
  const models = Array.from(new Set(metrics.map((m) => m.model)));
  const positions = Array.from(new Set(metrics.map((m) => m.position)));
  const colors = ["var(--mint)", "var(--blue)", "var(--warning)", "var(--chart-purple)", "var(--chart-rose)", "var(--chart-teal)"];
  const rows = models.map((model) => Object.fromEntries([
    ["model", model],
    ...positions.map((position) => [position, metrics.find((m) => m.model === model && m.position === position)?.mae]),
  ]));
  return (
    <div
      className="chart"
      role="img"
      aria-label="Historical model MAE by position; exact values are in the metrics table"
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ left: -15, right: 15 }}>
          <CartesianGrid stroke={grid} strokeDasharray="3 5" vertical={false} />
          <XAxis
            dataKey="model"
            tick={tick}
            axisLine={false}
            tickLine={false}
          />
          <YAxis tick={tick} axisLine={false} tickLine={false} />
          <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "var(--surface-raised)" }} />
          <Legend />
          {positions.map((position, index) => <Bar key={position} dataKey={position} name={`${position === "DST" ? "D/ST" : position} MAE`} fill={colors[index % colors.length]} radius={[4, 4, 0, 0]} />)}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
export function AccuracyChart({ records }: { records: HistoryRecord[] }) {
  return (
    <div
      className="chart"
      role="img"
      aria-label="Held-out predictions versus actual points; exact values are in the accuracy table"
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={records.map((r) => ({
            label: `${r.season} W${r.week}`,
            Actual: r.actual_ppr_points,
            Predicted: r.predicted_ppr_points,
          }))}
          margin={{ left: -15, right: 18 }}
        >
          <CartesianGrid stroke={grid} strokeDasharray="3 5" vertical={false} />
          <XAxis
            dataKey="label"
            tick={tick}
            axisLine={false}
            tickLine={false}
          />
          <YAxis tick={tick} axisLine={false} tickLine={false} />
          <Tooltip contentStyle={tooltipStyle} />
          <Legend />
          <Line dataKey="Actual" stroke="var(--mint)" strokeWidth={2} />
          <Line
            dataKey="Predicted"
            stroke="var(--blue)"
            strokeDasharray="5 5"
            strokeWidth={2}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
