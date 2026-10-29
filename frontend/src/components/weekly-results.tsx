"use client";
import { useCallback } from "react";
import { api } from "@/lib/api";
import { useResource } from "@/lib/use-resource";
import { useSeason } from "./season-provider";
import { Panel, NumberValue, Loading, ErrorState } from "./ui";

export function WeeklyResultsPanel() {
  const { selection } = useSeason();
  const load = useCallback((signal: AbortSignal) => api.results(selection!, signal), [selection]);
  const result = useResource(selection ? load : null);
  return <Panel title={`Weekly results${selection ? ` · ${selection.season} week ${selection.week}` : ""}`} subtitle="Saved pregame forecasts versus actual PPR">
    {result.loading ? <Loading /> : result.error ? <ErrorState error={result.error} retry={result.retry} /> : <>
      <p>{result.data?.message}</p>
      {result.data?.metrics.map(m => <p key={m.model}><strong>{m.model}</strong> · {m.count} matched games · MAE <NumberValue value={m.mae} digits={2} /> · RMSE <NumberValue value={m.rmse} digits={2} /> · Bias <NumberValue value={m.bias} digits={2} /></p>)}
      {!result.data?.records.length ? <p>No results or saved forecasts for this week yet.</p> : <div className="table-scroll"><table><thead><tr>{["Player", "Forecast", "Actual", "Recent average", "Error"].map(c => <th key={c}>{c}</th>)}</tr></thead><tbody>{result.data.records.map(r => <tr key={r.player_id}><td>{r.player_name} · {r.position}</td><td><NumberValue value={r.projected} /></td><td><NumberValue value={r.actual} /></td><td><NumberValue value={r.baseline} /></td><td><NumberValue value={r.error} /></td></tr>)}</tbody></table></div>}
    </>}
  </Panel>;
}
