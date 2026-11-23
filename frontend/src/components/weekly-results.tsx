"use client";
import { useCallback } from "react";
import { api } from "@/lib/api";
import { useResource } from "@/lib/use-resource";
import { useSeason } from "./season-provider";
import { Panel, NumberValue, Loading, ErrorState } from "./ui";

export function WeeklyResultsPanel() {
  const { selection } = useSeason();
  const load = useCallback((signal: AbortSignal) => api.results(selection!, signal), [selection]);
  const result = useResource(selection ? load : null, 60_000);
  const records = result.data?.records ?? [];
  const reported = records.filter((row) => row.actual !== null);
  const ordered = [...reported, ...records.filter((row) => row.actual === null)];
  return <Panel title={`Weekly results${selection ? ` · ${selection.season} week ${selection.week}` : ""}`}
    subtitle={result.data ? `${reported.length} players with actual points` : "Saved pregame forecasts versus actual points"}
    action={<button type="button" className="button secondary small" disabled={!selection || result.loading} onClick={result.retry}>Refresh results</button>}>
    {result.loading ? <Loading /> : result.error ? <ErrorState error={result.error} retry={result.retry} /> : <>
      <p>{result.data?.message}</p>
      {result.data?.metrics.map(m => <p key={m.model}><strong>{m.model}</strong> · {m.count} matched games · MAE <NumberValue value={m.mae} digits={2} /> · RMSE <NumberValue value={m.rmse} digits={2} /> · Bias <NumberValue value={m.bias} digits={2} /></p>)}
      {!ordered.length ? <p>No results or saved forecasts for this week yet.</p> : <div className="table-scroll"><table><thead><tr>{["Player", "Forecast", "Actual", "Recent average", "Error"].map(c => <th key={c}>{c}</th>)}</tr></thead><tbody>{ordered.map(r => <tr key={r.player_id}><td>{r.player_name} · {r.position}</td><td><NumberValue value={r.projected} /></td><td>{r.actual === null ? "Pending" : <NumberValue value={r.actual} />}</td><td><NumberValue value={r.baseline} /></td><td><NumberValue value={r.error} /></td></tr>)}</tbody></table></div>}
    </>}
  </Panel>;
}
