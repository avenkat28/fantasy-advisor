"use client";
import { useCallback } from "react";
import Link from "next/link";
import {
  ArrowRight,
  ArrowLeftRight,
  ArrowUpRight,
  Database,
  ScanLine,
  Search,
  ShieldCheck,
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
          <div className="eyebrow">
            <span className="status-dot" /> YOUR WEEKLY GAME PLAN
          </div>
          <h1>
            Your edge starts here<span className="mint">.</span>
          </h1>
          <p>Less guesswork. More game plan. Put the numbers on your side.</p>
        </div>
        <Link href="/compare" className="button primary">
          <ArrowLeftRight size={17} /> Make a start/sit call
          <ArrowUpRight size={16} />
        </Link>
      </div>
      <div className="insight-strip">
        <div>
          <Database size={17} />
          <span>
            {selection
              ? `${selection.season} · Week ${selection.week}`
              : "Connecting to your data"}
          </span>
          <span className="strip-dot">/</span>
          <span>Full-PPR projections</span>
        </div>
        <span>
          Statistical snapshot:{" "}
          {dateLabel(health?.snapshot?.latest_statistical_game)}
        </span>
      </div>
      <div className="stats-grid">
        <Stat
          label="AVAILABLE PROJECTIONS"
          value={weekly.data ? weekly.data.total : "—"}
          note={
            weekly.data
              ? "RB + WR · selected week"
              : "Awaiting selected-week data"
          }
          accent
        />
        <Stat
          label="RB MODEL · TEST MAE"
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
          label="WR MODEL · TEST MAE"
          value={
            <>
              <NumberValue
                value={metrics?.find((m) => m.position === "WR")?.mae}
                digits={2}
              />
              <small> PPR</small>
            </>
          }
          note="Typical absolute error · lower is better"
        />
      </div>
      <div className="section-title">
        <div>
          <h2>The projection board</h2>
          <p>The highest estimates for your selected week.</p>
        </div>
        <TextLink href="/projections">Explore all projections</TextLink>
      </div>
      {!selection || weekly.loading ? (
        <Loading label="Building your weekly projection board…" />
      ) : weekly.error ? (
        <Panel title="The board is waiting on data">
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
          <Panel
            title="Running backs"
            subtitle="Top 5 · projected full PPR"
            action={<span className="position">RB</span>}
          >
            <ProjectionTable
              projections={players
                .filter((p) => p.position === "RB")
                .slice(0, 5)}
              compact
            />
          </Panel>
          <Panel
            title="Wide receivers"
            subtitle="Top 5 · projected full PPR"
            action={<span className="position wide">WR</span>}
          >
            <ProjectionTable
              projections={players
                .filter((p) => p.position === "WR")
                .slice(0, 5)}
              compact
            />
          </Panel>
        </div>
      )}
      <div className="dashboard-lower">
        <Panel
          title="A look at the leaders"
          subtitle="Selected-week estimates · not guaranteed outcomes"
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
        <section className="decision-card">
          <div className="eyebrow">
            <ScanLine size={15} /> THE MATCHUP DESK
          </div>
          <h2>
            Two players.
            <br />
            One lineup spot.
          </h2>
          <p>
            Compare projections, recent usage, and defensive matchups. See the
            evidence behind the call.
          </p>
          <div className="field-art" aria-hidden="true">
            <span />
            <span />
            <span />
            <span />
            <i className="field-marker first">A</i>
            <i className="field-marker second">B</i>
            <ArrowLeftRight size={28} />
          </div>
          <Link href="/compare" className="button primary">
            Compare players
            <ArrowRight size={16} />
          </Link>
        </section>
      </div>
      <div className="quick-links">
        <Link href="/players">
          <Search size={21} />
          <div>
            <strong>Find your next starter</strong>
            <span>Search players and explore their production.</span>
          </div>
          <ArrowUpRight size={18} />
        </Link>
        <Link href="/performance">
          <ShieldCheck size={21} />
          <div>
            <strong>Know the model’s limits</strong>
            <span>Real test results. Transparent evaluation.</span>
          </div>
          <ArrowUpRight size={18} />
        </Link>
      </div>
      <p className="disclaimer">
        Projections are estimates, not promises. No calibrated confidence
        intervals or verified game-day availability are provided.
      </p>
    </>
  );
}
