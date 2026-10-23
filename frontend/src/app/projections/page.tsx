"use client";
import { useCallback, useMemo, useState } from "react";
import Link from "next/link";
import { Search, ArrowDownWideNarrow, Info } from "lucide-react";
import { api } from "@/lib/api";
import { useResource } from "@/lib/use-resource";
import { useSeason } from "@/components/season-provider";
import { ProjectionTable } from "@/components/projection-table";
import { ErrorState, Loading, PageHeading, Panel } from "@/components/ui";
export default function ProjectionsPage() {
  const { selection } = useSeason();
  const [position, setPosition] = useState("");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("desc");
  const [page, setPage] = useState(0);
  const loader = useCallback(
    (signal: AbortSignal) =>
      api.weekly(selection!, position || undefined, signal),
    [selection, position],
  );
  const result = useResource(selection ? loader : null);
  const filtered = useMemo(
    () =>
      (result.data?.projections ?? [])
        .filter((p) =>
          p.player_name.toLowerCase().includes(query.toLowerCase()),
        )
        .sort((a, b) =>
          sort === "desc"
            ? b.projected_ppr_points - a.projected_ppr_points
            : a.projected_ppr_points - b.projected_ppr_points,
        ),
    [result.data, query, sort],
  );
  const safePage = Math.min(
    page,
    Math.max(0, Math.ceil(filtered.length / 25) - 1),
  );
  return (
    <>
      <PageHeading
        eyebrow="THE WEEKLY BOARD"
        title="Weekly projections"
        description="Find the opportunity. Compare every available RB and WR projection."
      />
      <Panel
        title={
          selection
            ? `${selection.season} · Week ${selection.week}`
            : "Select a week"
        }
        subtitle="Pregame estimates · full-PPR scoring"
        action={<span className="tag">RB + WR</span>}
      >
        <div className="table-toolbar">
          <div className="segmented" aria-label="Position filter">
            {[
              ["", "All positions"],
              ["RB", "Running backs"],
              ["WR", "Wide receivers"],
            ].map(([value, label]) => (
              <button
                key={value}
                aria-pressed={position === value}
                className={position === value ? "selected" : ""}
                onClick={() => {
                  setPosition(value);
                  setPage(0);
                }}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="toolbar-right">
            <div className="search-input">
              <Search size={17} />
              <input
                aria-label="Search projected players"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setPage(0);
                }}
                placeholder="Find a player…"
              />
            </div>
            <label className="sort-control">
              <ArrowDownWideNarrow size={17} />
              <select
                aria-label="Sort projected points"
                value={sort}
                onChange={(e) => {
                  setSort(e.target.value);
                  setPage(0);
                }}
              >
                <option value="desc">Highest PPR</option>
                <option value="asc">Lowest PPR</option>
              </select>
            </label>
          </div>
        </div>
        {!selection || result.loading ? (
          <Loading label="Loading weekly projections…" />
        ) : result.error ? (
          <ErrorState error={result.error} retry={result.retry} />
        ) : (
          <>
            <ProjectionTable
              projections={filtered.slice(safePage * 25, (safePage + 1) * 25)}
              startRank={safePage * 25}
            />
            <div className="pagination">
              <span>
                {filtered.length
                  ? `${safePage * 25 + 1}–${Math.min((safePage + 1) * 25, filtered.length)} of ${filtered.length}`
                  : "0 results"}
                {result.data &&
                result.data.total > result.data.projections.length
                  ? ` · showing top ${result.data.projections.length} of ${result.data.total} available`
                  : ""}
              </span>
              <div>
                <button
                  className="button secondary small"
                  disabled={safePage === 0}
                  onClick={() => setPage(safePage - 1)}
                >
                  Previous
                </button>
                <button
                  className="button secondary small"
                  disabled={(safePage + 1) * 25 >= filtered.length}
                  onClick={() => setPage(safePage + 1)}
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </Panel>
      {result.data && (
        <>
          <div className="info-note">
            <Info size={18} />
            <p>{result.data.eligibility}</p>
          </div>
          {result.data.unavailable.length > 0 && (
            <details className="panel unavailable">
              <summary>
                {result.data.unavailable.length} players unavailable for
                projection
              </summary>
              <p>
                These players are not assigned a zero. The backend reports why a
                projection cannot be generated.
              </p>
              <ul>
                {result.data.unavailable.map((p) => (
                  <li key={p.player_id}>
                    <Link href={`/players/${encodeURIComponent(p.player_id)}`}>
                      {p.player_id}
                    </Link>
                    <span>{p.message}</span>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </>
      )}
      <p className="disclaimer">
        Search and sorting apply to the loaded results (up to 500). Rankings are
        projection estimates, not verified player availability.
      </p>
    </>
  );
}
