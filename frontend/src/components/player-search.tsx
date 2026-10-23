"use client";
import { useCallback, useEffect, useId, useState } from "react";
import { Search, X } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useResource } from "@/lib/use-resource";
import type { Player } from "@/lib/types";
import { EmptyState, ErrorState, Loading, PositionBadge } from "./ui";

export function PlayerSearch({
  label = "Search players",
  onSelect,
  selected,
}: {
  label?: string;
  onSelect?: (player: Player | null) => void;
  selected?: Player | null;
}) {
  const id = useId();
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(query.trim()), 250);
    return () => clearTimeout(timer);
  }, [query]);
  const load = useCallback(
    (signal: AbortSignal) => api.players(debounced, signal),
    [debounced],
  );
  const result = useResource(onSelect && selected ? null : load);
  return (
    <div className="player-search">
      <label className="field-label" htmlFor={id}>
        {label}
      </label>
      {onSelect && selected ? (
        <div className="selected-player">
          <div>
            <PositionBadge position={selected.position} />
            <strong>{selected.player_name}</strong>
            <span>{selected.team}</span>
          </div>
          <button
            className="icon-button"
            aria-label={`Clear ${label}`}
            onClick={() => onSelect(null)}
          >
            <X size={18} />
          </button>
        </div>
      ) : (
        <>
          <div className="search-input">
            <Search size={18} aria-hidden="true" />
            <input
              id={id}
              autoComplete="off"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by player name…"
              type="search"
            />
            <kbd>/ NFL</kbd>
          </div>
          {result.loading ? (
            <Loading label="Searching players…" />
          ) : result.error ? (
            <ErrorState error={result.error} retry={result.retry} />
          ) : result.data?.length === 0 ? (
            <EmptyState
              title="No players found"
              message="Try a partial first or last name. Only RB and WR are supported."
            />
          ) : (
            <ul
              className={`search-results ${onSelect ? "compact-results" : ""}`}
              aria-label={`${label} results`}
            >
              {result.data?.map((player) => (
                <li key={player.player_id}>
                  {onSelect ? (
                    <button type="button" onClick={() => onSelect(player)}>
                      <PlayerResult player={player} />
                    </button>
                  ) : (
                    <Link
                      href={`/players/${encodeURIComponent(player.player_id)}`}
                    >
                      <PlayerResult player={player} />
                    </Link>
                  )}
                </li>
              ))}
            </ul>
          )}
          {result.data?.length === 50 && (
            <p className="helper">
              Showing the first 50 matches. Refine your search to find more
              players.
            </p>
          )}
        </>
      )}
    </div>
  );
}
function PlayerResult({ player }: { player: Player }) {
  return (
    <>
      <span className="player-avatar">
        {player.player_name
          .split(/[ .]+/)
          .filter(Boolean)
          .map((n) => n[0])
          .slice(0, 2)
          .join("")}
      </span>
      <span className="result-name">
        <strong>{player.player_name}</strong>
        <small>
          {player.team} · {player.player_id}
        </small>
      </span>
      <PositionBadge position={player.position} />
    </>
  );
}
