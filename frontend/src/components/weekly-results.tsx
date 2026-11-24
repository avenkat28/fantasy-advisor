"use client";
import { useCallback } from "react";
import { api } from "@/lib/api";
import { useResource } from "@/lib/use-resource";
import { useSeason } from "./season-provider";
import { Panel, NumberValue, Loading, ErrorState } from "./ui";

export function WeeklyResultsPanel({ showCurrentProjection = false }: { showCurrentProjection?: boolean }) {
  const { selection } = useSeason();
  const load = useCallback(
    (signal: AbortSignal) => api.results(selection!, signal, showCurrentProjection),
    [selection, showCurrentProjection],
  );
  const result = useResource(selection ? load : null, 60_000);
  const records = result.data?.records ?? [];
  const reported = records.filter((row) => row.actual !== null);
  const ordered = [...reported, ...records.filter((row) => row.actual === null)];
  const columns = showCurrentProjection
    ? ["Player", "Projected", "Saved forecast", "Actual", "Recent average", "Forecast error"]
    : ["Player", "Forecast", "Actual", "Recent average", "Error"];
  return <Panel title={`Weekly results${selection ? ` · ${selection.season} week ${selection.week}` : ""}`}
    subtitle={result.data ? `${reported.length} players with actual points` : "Saved pregame forecasts versus actual points"}
    action={<button type="button" className="button secondary small" disabled={!selection || result.loading} onClick={result.retry}>Refresh results</button>}>
    {result.loading ? <Loading /> : result.error ? <ErrorState error={result.error} retry={result.retry} /> : <>
      <p>{result.data?.message}</p>
      {showCurrentProjection && <p>Projected uses the current model and data, just like the player page. The saved forecast is the estimate recorded before kickoff and used to calculate forecast error.</p>}
      {result.data?.metrics.map(m => <p key={m.model}><strong>{m.model}</strong> · {m.count} matched games · MAE <NumberValue value={m.mae} digits={2} /> · RMSE <NumberValue value={m.rmse} digits={2} /> · Bias <NumberValue value={m.bias} digits={2} /></p>)}
      {!ordered.length ? <p>No results or projections for this week yet.</p> : (
        <div className="table-scroll">
          <table>
            <thead><tr>{columns.map((column) => <th key={column} scope="col">{column}</th>)}</tr></thead>
            <tbody>
              {ordered.map((row) => <tr key={row.player_id}>
                <td>{row.player_name} · {row.position}</td>
                {showCurrentProjection && <td><NumberValue value={row.current_projection} /></td>}
                <td><NumberValue value={row.projected} /></td>
                <td>{row.actual === null ? "Pending" : <NumberValue value={row.actual} />}</td>
                <td><NumberValue value={row.baseline} /></td>
                <td><NumberValue value={row.error} /></td>
              </tr>)}
            </tbody>
          </table>
        </div>
      )}
    </>}
  </Panel>;
}
