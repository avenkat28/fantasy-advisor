"use client";
import { useCallback } from "react";
import Link from "next/link";
import { ArrowLeft, Info } from "lucide-react";
import { api } from "@/lib/api";
import { useResource } from "@/lib/use-resource";
import { useSeason } from "./season-provider";
import { AccuracyChart, RecentChart } from "./charts";
import {
  dateLabel,
  EmptyState,
  ErrorState,
  Loading,
  NumberValue,
  PageHeading,
  Panel,
  PositionBadge,
  Stat,
} from "./ui";
import type { HistoricalGame } from "@/lib/types";
function average(games: HistoricalGame[]) {
  const values = games
    .map((g) => g.fantasy_points_ppr)
    .filter((v): v is number => v != null);
  return values.length
    ? values.reduce((a, b) => a + b, 0) / values.length
    : null;
}
export function PlayerProfile({ id }: { id: string }) {
  const { selection } = useSeason();
  const detail = useResource(
    useCallback((signal: AbortSignal) => api.player(id, signal), [id]),
  );
  const projectionLoader = useCallback(
    (signal: AbortSignal) => api.projection(id, selection!, signal),
    [id, selection],
  );
  const projection = useResource(selection ? projectionLoader : null);
  const history = useResource(
    useCallback((signal: AbortSignal) => api.history(id, signal), [id]),
  );
  const player = detail.data;
  if (detail.loading) return <Loading label="Loading player research…" />;
  if (detail.error)
    return <ErrorState error={detail.error} retry={detail.retry} />;
  if (!player) return <EmptyState title="No player details available" />;
  const recent = player.recent_games;
  return (
    <>
      <Link className="back-link" href="/players">
        <ArrowLeft size={15} />
        Player research
      </Link>
      <PageHeading
        eyebrow="PLAYER PROFILE"
        title={player.player_name}
        description={`${player.team} · ${player.position} · ${player.upcoming_opponent ? `Next scheduled opponent: ${player.upcoming_opponent}` : "No future opponent available in this snapshot"}`}
        action={<PositionBadge position={player.position} />}
      />
      <div className="stats-grid four">
        <Stat
          label={
            selection
              ? `PROJECTED PPR · ${selection.season} W${selection.week}`
              : "PROJECTED PPR"
          }
          value={
            projection.loading ? (
              "…"
            ) : (
              <NumberValue value={projection.data?.projected_ppr_points} />
            )
          }
          note={
            projection.data
              ? `${projection.data.team} vs ${projection.data.opponent} · pregame estimate`
              : "Prediction requires sufficient pregame data"
          }
          accent
        />
        <Stat
          label="RECENT PPR · UP TO 3 GAMES"
          value={<NumberValue value={average(recent.slice(-3))} />}
          note={`${recent.slice(-3).length} observed historical games`}
        />
        <Stat
          label="RECENT PPR · UP TO 5 GAMES"
          value={<NumberValue value={average(recent.slice(-5))} />}
          note={`${recent.slice(-5).length} observed historical games`}
        />
        <Stat
          label="HISTORICAL PPR AVERAGE"
          value={
            <NumberValue
              value={player.historical_averages.fantasy_points_ppr}
            />
          }
          note="All recorded games in the local snapshot"
        />
      </div>
      {projection.error && (
        <ErrorState error={projection.error} retry={projection.retry} />
      )}
      <div className="two-columns profile-columns">
        <Panel
          title="Recent production"
          subtitle="Historical full-PPR points · latest five recorded appearances"
        >
          {recent.some((g) => g.fantasy_points_ppr != null) ? (
            <RecentChart games={recent} />
          ) : (
            <EmptyState
              title="No historical scoring available"
              message="This player has no recorded fantasy production in the local snapshot."
            />
          )}
        </Panel>
        <Panel
          title="The matchup context"
          subtitle={
            projection.data
              ? `${projection.data.team} vs ${projection.data.opponent} · ${selection?.season} week ${selection?.week}`
              : "Available when a projection can be generated"
          }
        >
          {projection.loading ? (
            <Loading label="Loading matchup context…" />
          ) : projection.data ? (
            <dl className="facts">
              <div>
                <dt>
                  Opponent PPR allowed to {player.position} · up to 3 games
                </dt>
                <dd>
                  <NumberValue
                    value={
                      projection.data.matchup_features
                        .opponent_ppr_allowed_position_mean_3
                    }
                  />
                </dd>
              </div>
              <div>
                <dt>Opponent PPR allowed · up to 5 games</dt>
                <dd>
                  <NumberValue
                    value={
                      projection.data.matchup_features
                        .opponent_ppr_allowed_position_mean_5
                    }
                  />
                </dd>
              </div>
              <div>
                <dt>Opponent rushing yards allowed · up to 3 games</dt>
                <dd>
                  <NumberValue
                    value={
                      projection.data.matchup_features
                        .opponent_rushing_yards_allowed_mean_3
                    }
                  />
                </dd>
              </div>
              <div>
                <dt>Player historical games used</dt>
                <dd>{projection.data.historical_games}</dd>
              </div>
              <div>
                <dt>Last included player game</dt>
                <dd>{dateLabel(projection.data.last_statistical_game)}</dd>
              </div>
              <div>
                <dt>Model</dt>
                <dd>{projection.data.model_version}</dd>
              </div>
            </dl>
          ) : (
            <EmptyState
              title="Matchup context unavailable"
              message="Historical player research remains available when a projection is unavailable."
            />
          )}
        </Panel>
      </div>
      <Panel
        title="Recent game log"
        subtitle={`Historical observations · latest recorded: ${player.season} week ${player.week}`}
      >
        {recent.length ? (
          <div
            className="table-scroll"
            tabIndex={0}
            aria-label="Scrollable recent game statistics"
          >
            <table>
              <caption className="sr-only">
                Recent historical rushing, receiving and opportunity statistics
              </caption>
              <thead>
                <tr>
                  {[
                    "Season / week",
                    "Type",
                    "Team",
                    "PPR",
                    "Rush yds",
                    "Rec yds",
                    "Rec",
                    "Targets",
                    "Carries",
                  ].map((c) => (
                    <th key={c} scope="col">
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {recent.map((g) => (
                  <tr key={`${g.season}-${g.season_type}-${g.week}`}>
                    <td>
                      {g.season} · W{g.week}
                    </td>
                    <td>{g.season_type}</td>
                    <td>{g.team}</td>
                    {(
                      [
                        "fantasy_points_ppr",
                        "rushing_yards",
                        "receiving_yards",
                        "receptions",
                        "targets",
                        "carries",
                      ] as const
                    ).map((key) => (
                      <td key={key}>
                        <NumberValue
                          value={g[key]}
                          digits={key === "fantasy_points_ppr" ? 1 : 0}
                        />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            title="No games recorded"
            message="Roster membership alone does not create historical statistics."
          />
        )}
      </Panel>
      <Panel
        title="How accurate were past predictions?"
        subtitle="Saved out-of-sample test records · separate from current-week estimates"
      >
        {history.loading ? (
          <Loading label="Loading held-out predictions…" />
        ) : history.error ? (
          <ErrorState error={history.error} retry={history.retry} />
        ) : !history.data?.available || !history.data.records.length ? (
          <EmptyState
            title="No held-out predictions for this player"
            message={
              history.data?.message ||
              "This player has no saved records in the original model test period."
            }
          />
        ) : (
          <>
            <AccuracyChart records={history.data.records} />
            <div
              className="table-scroll"
              tabIndex={0}
              aria-label="Scrollable historical prediction accuracy"
            >
              <table>
                <caption className="sr-only">
                  Out-of-sample predicted and actual fantasy points
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Season / week</th>
                    <th scope="col">Predicted PPR</th>
                    <th scope="col">Actual PPR</th>
                    <th scope="col">Absolute error</th>
                  </tr>
                </thead>
                <tbody>
                  {history.data.records.map((g) => (
                    <tr key={`${g.season}-${g.week}`}>
                      <td>
                        {g.season} · W{g.week}
                      </td>
                      <td>
                        <NumberValue value={g.predicted_ppr_points} />
                      </td>
                      <td>
                        <NumberValue value={g.actual_ppr_points} />
                      </td>
                      <td>
                        <NumberValue value={g.absolute_error} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Panel>
      {projection.data && (
        <details className="panel provenance">
          <summary>Prediction provenance and limitations</summary>
          <dl className="facts">
            <div>
              <dt>Data as of (UTC)</dt>
              <dd>{projection.data.data_as_of}</dd>
            </div>
            <div>
              <dt>Prediction generated (UTC)</dt>
              <dd>{projection.data.prediction_timestamp}</dd>
            </div>
            <div>
              <dt>Eligibility source</dt>
              <dd>{projection.data.eligibility_source.replaceAll("_", " ")}</dd>
            </div>
            <div>
              <dt>Missing features</dt>
              <dd>
                {projection.data.missing_features.length
                  ? projection.data.missing_features.join(", ")
                  : "None"}
              </dd>
            </div>
          </dl>
          <ul>
            {projection.data.limitations.map((limit) => (
              <li key={limit}>{limit}</li>
            ))}
          </ul>
        </details>
      )}
      <div className="info-note">
        <Info size={18} />
        <p>
          Historical summaries describe the latest recorded games, which may
          differ from the games available before your selected projection week.
          They are not live statistics or injury reports.
        </p>
      </div>
    </>
  );
}
