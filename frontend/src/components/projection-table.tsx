"use client";
import Link from "next/link";
import type { Projection } from "@/lib/types";
import { EmptyState, NumberValue, PositionBadge } from "./ui";
export function ProjectionTable({
  projections,
  compact = false,
  startRank = 0,
}: {
  projections: Projection[];
  compact?: boolean;
  startRank?: number;
}) {
  if (!projections.length) return <EmptyState />;
  return (
    <div
      className="table-scroll"
      tabIndex={0}
      aria-label="Scrollable player projections"
    >
      <table>
        <caption className="sr-only">
          Projected full-PPR fantasy points for the selected season and week
        </caption>
        <thead>
          <tr>
            <th scope="col">Rank</th>
            <th scope="col">Player</th>
            <th scope="col">Matchup</th>
            {!compact && (
              <th scope="col">
                Recent PPR<small>Up to 3 games</small>
              </th>
            )}
            <th scope="col" className="numeric">
              Projected<small>Full PPR</small>
            </th>
          </tr>
        </thead>
        <tbody>
          {projections.map((player, index) => (
            <tr key={player.player_id}>
              <td className="rank">
                {String(startRank + index + 1).padStart(2, "0")}
              </td>
              <td>
                <Link
                  className="table-player"
                  href={`/players/${encodeURIComponent(player.player_id)}`}
                >
                  <strong>{player.player_name}</strong>
                  <span>
                    <PositionBadge position={player.position} />
                    {player.team}
                  </span>
                </Link>
              </td>
              <td>
                <span className="matchup">
                  {player.team}
                  <span>vs</span>
                  {player.opponent}
                </span>
              </td>
              {!compact && (
                <td>
                  <NumberValue value={player.recent_ppr_mean_3} />
                </td>
              )}
              <td className="numeric">
                <span className="projection-number">
                  <NumberValue value={player.projected_ppr_points} />
                </span>
                <span className="points-label"> pts</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
