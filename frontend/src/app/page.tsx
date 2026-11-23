"use client";
import { useCallback } from "react";
import Link from "next/link";
import {
  ArrowLeftRight,
  ArrowUpRight,
} from "lucide-react";
import { api } from "@/lib/api";
import { useResource } from "@/lib/use-resource";
import { useSeason } from "@/components/season-provider";
import {
  dateLabel,
  EmptyState,
  ErrorState,
  Loading,
  NumberValue,
  Panel,
  Stat,
  TextLink,
} from "@/components/ui";
import { ProjectionTable } from "@/components/projection-table";
import { RankingChart } from "@/components/charts";

export default function Dashboard() {
  const { selection, health } = useSeason();
  const load = useCallback(
    (signal: AbortSignal) => api.weekly(selection!, undefined, signal),
    [selection],
  );
  const weekly = useResource(selection ? load : null);
  const performance = useResource(
    useCallback((signal: AbortSignal) => api.performance(signal), []),
  );
  const metrics = performance.data?.metrics.filter(
    (m) => m.model === "xgboost",
  );
  const players = weekly.data?.projections ?? [];
  return (
    <>
      <div className="dashboard-heading">
        <div>
          <h1>Fantasy dashboard</h1>
          <p className="dashboard-meta">
            {selection ? `${selection.season} / Week ${selection.week}` : "Loading week…"}
            <span>Full PPR</span>
            {health?.snapshot && <span>Stats through {dateLabel(health.snapshot.latest_statistical_game)}</span>}
          </p>
        </div>
        <Link href="/compare" className="button">
          <ArrowLeftRight size={17} /> Compare players
        </Link>
      </div>
      <div className="stats-grid dashboard-stats">
        <Stat
          label="Players projected"
          value={weekly.data ? weekly.data.total : "—"}
          note={
            weekly.data ? undefined : "Awaiting weekly data"
          }
        />
        <Stat
          label="RB average error"
          value={
            <>
              <NumberValue
                value={metrics?.find((m) => m.position === "RB")?.mae}
                digits={2}
              />
              <small> PPR</small>
            </>
          }
          note={
            performance.error ? (
              <button className="inline-button" onClick={performance.retry}>
                Metrics unavailable · retry
              </button>
            ) : (
              performance.data?.periods.test || "Historical held-out evaluation"
            )
          }
        />
        <Stat
          label="WR average error"
          value={
            <>
              <NumberValue
                value={metrics?.find((m) => m.position === "WR")?.mae}
                digits={2}
              />
              <small> PPR</small>
            </>
          }
          note={performance.data?.periods.test}
        />
      </div>
      <div className="section-title">
        <div>
          <h2>Top projections</h2>
        </div>
        <TextLink href="/projections">All projections</TextLink>
      </div>
      {!selection || weekly.loading ? (
        <Loading label="Loading projections…" />
      ) : weekly.error ? (
        <Panel title="Projections unavailable">
          <ErrorState error={weekly.error} retry={weekly.retry} />
          <p className="panel-footnote">
            Choose a different week above. Player research and saved model
            evaluation can still be explored independently.
          </p>
        </Panel>
      ) : players.length === 0 ? (
        <EmptyState
          title="No projections available"
          message="The selected week has no supported player projections. Try a different week."
        />
      ) : (
        <div className="two-columns">
          {[["QB", "Quarterbacks"], ["RB", "Running backs"], ["WR", "Wide receivers"], ["TE", "Tight ends"], ["K", "Kickers"], ["DST", "Defense / special teams"]].map(([position, title]) => (
            <Panel key={position} title={title} subtitle="Top 5 · projected fantasy points" action={<span className="position">{position}</span>}>
              <ProjectionTable projections={players.filter((p) => p.position === position).slice(0, 5)} compact />
            </Panel>
          ))}
        </div>
      )}
      <div className="dashboard-lower">
        <Panel
          title="Projected scoring leaders"
        >
          {players.length ? (
            <RankingChart players={players} />
          ) : (
            <EmptyState
              title="Waiting for projections"
              message="A ranking chart appears when the selected week has data."
            />
          )}
        </Panel>
        <Panel title="Tools">
          <div className="dashboard-tools">
            {[
              ["/players", "Player search"],
              ["/trade", "Trade analyzer"],
              ["/team", "Team evaluator"],
              ["/performance", "Model performance"],
            ].map(([href, label]) => (
              <Link key={href} href={href}>{label}<ArrowUpRight size={16} aria-hidden="true" /></Link>
            ))}
          </div>
        </Panel>
      </div>
    </>
  );
}
