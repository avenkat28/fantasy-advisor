"use client";
import { useCallback, useState } from "react";
import { ArrowLeftRight, Check, Scale } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Player, Projection, Selection } from "@/lib/types";
import { useResource } from "@/lib/use-resource";
import { useSeason } from "@/components/season-provider";
import { PlayerSearch } from "@/components/player-search";
import {
  EmptyState,
  ErrorState,
  Loading,
  NumberValue,
  PageHeading,
  Panel,
  PositionBadge,
} from "@/components/ui";
export default function ComparisonPage() {
  const { selection } = useSeason();
  const [first, setFirst] = useState<Player | null>(null);
  const [second, setSecond] = useState<Player | null>(null);
  const [submitted, setSubmitted] = useState<{
    first: string;
    second: string;
    selection: Selection;
  } | null>(null);
  const valid =
    submitted &&
    first?.player_id === submitted.first &&
    second?.player_id === submitted.second &&
    selection?.season === submitted.selection.season &&
    selection?.week === submitted.selection.week;
  const loader = useCallback(
    (signal: AbortSignal) =>
      api.compare(
        submitted!.first,
        submitted!.second,
        submitted!.selection,
        signal,
      ),
    [submitted],
  );
  const result = useResource(valid ? loader : null);
  return (
    <>
      <PageHeading
        eyebrow="THE MATCHUP DESK"
        title="Make the call."
        description="Two players, one decision. Compare the numbers before you set your lineup."
      />
      <Panel
        title="Build your comparison"
        subtitle={
          selection
            ? `Full PPR · ${selection.season} week ${selection.week} · change week in the header`
            : "Choose a season and week in the header"
        }
      >
        <div className="comparison-inputs">
          <PlayerSearch label="Player A" selected={first} onSelect={setFirst} />
          <span className="versus">
            <ArrowLeftRight size={21} />
          </span>
          <PlayerSearch
            label="Player B"
            selected={second}
            onSelect={setSecond}
          />
        </div>
        <div className="compare-actions">
          <p>
            {first && second && first.player_id === second.player_id
              ? "Choose two different players."
              : "The recommendation comes directly from the backend model."}
          </p>
          <button
            className="button primary"
            disabled={
              !selection ||
              !first ||
              !second ||
              first.player_id === second.player_id ||
              result.loading
            }
            onClick={() =>
              selection &&
              first &&
              second &&
              setSubmitted({
                first: first.player_id,
                second: second.player_id,
                selection,
              })
            }
          >
            <ArrowLeftRight size={17} />
            Compare players
          </button>
        </div>
      </Panel>
      {result.loading ? (
        <Loading label="Comparing projections and matchup evidence…" />
      ) : result.error ? (
        <ErrorState error={result.error} retry={result.retry} />
      ) : result.data && valid ? (
        <>
          <div
            className={`recommendation ${result.data.close_call ? "close" : ""}`}
          >
            <div className="recommendation-icon">
              {result.data.close_call ? (
                <Scale size={24} />
              ) : (
                <Check size={24} />
              )}
            </div>
            <div>
              <div className="eyebrow">
                {result.data.close_call ? "CLOSE CALL" : "MODEL RECOMMENDATION"}
              </div>
              <h2>
                {result.data.recommended_player_id
                  ? `Start ${result.data.recommended_player_id === result.data.player1.player_id ? result.data.player1.player_name : result.data.player2.player_name}`
                  : "No model preference — projections are tied"}
              </h2>
              <p>{result.data.explanation}</p>
              <small>
                Close-call threshold: {result.data.close_call_threshold} PPR ·
                projected difference:{" "}
                <NumberValue
                  value={Math.abs(result.data.difference)}
                  digits={2}
                />{" "}
                PPR
              </small>
            </div>
          </div>
          <div className="two-columns">
            <ComparisonCard
              player={result.data.player1}
              recommended={
                result.data.recommended_player_id ===
                result.data.player1.player_id
              }
            />
            <ComparisonCard
              player={result.data.player2}
              recommended={
                result.data.recommended_player_id ===
                result.data.player2.player_id
              }
            />
          </div>
        </>
      ) : (
        <EmptyState
          title="Your lineup decision starts here"
          message="Select two players and compare their projections for the same NFL week."
        />
      )}
      <p className="disclaimer">
        A close call signals a small projection difference, not calibrated
        uncertainty. No injury or game-day availability claim is made.
      </p>
    </>
  );
}
function ComparisonCard({
  player,
  recommended,
}: {
  player: Projection;
  recommended: boolean;
}) {
  return (
    <Panel
      title={player.player_name}
      subtitle={`${player.team} vs ${player.opponent}`}
      action={
        recommended ? (
          <span className="recommend-badge">
            <Check size={13} /> Recommended start
          </span>
        ) : (
          <PositionBadge position={player.position} />
        )
      }
    >
      <div className="comparison-score">
        <PositionBadge position={player.position} />
        <div>
          <NumberValue value={player.projected_ppr_points} />
          <span>PROJECTED PPR</span>
        </div>
      </div>
      <dl className="facts">
        <div>
          <dt>Recent PPR · up to 3 games</dt>
          <dd>
            <NumberValue value={player.recent_ppr_mean_3} />
          </dd>
        </div>
        <div>
          <dt>Opponent PPR allowed to {player.position} · up to 3 games</dt>
          <dd>
            <NumberValue
              value={
                player.matchup_features.opponent_ppr_allowed_position_mean_3
              }
            />
          </dd>
        </div>
        <div>
          <dt>Historical games used</dt>
          <dd>{player.historical_games}</dd>
        </div>
        <div>
          <dt>Model version</dt>
          <dd>{player.model_version}</dd>
        </div>
      </dl>
      <div className="panel-footnote">
        <Link
          className="text-link"
          href={`/players/${encodeURIComponent(player.player_id)}`}
        >
          View player research →
        </Link>
      </div>
    </Panel>
  );
}
