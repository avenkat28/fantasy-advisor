"use client";

import { useCallback, useState } from "react";
import { useSeason } from "./season-provider";
import { ErrorState, Loading, Panel } from "./ui";
import { api } from "@/lib/api";
import { useResource } from "@/lib/use-resource";
import { bestLineup, leagueBaselines, letterGrade } from "@/lib/league-grades";
import type { Projection } from "@/lib/types";

function Picks({ title, pool, picks, onChange }: {
  title: string;
  pool: Projection[];
  picks: Projection[];
  onChange: (ids: string[]) => void;
}) {
  return <Panel title={title}>
    <label className="field-label">{title} · Add a player
      <select value="" onChange={(e) => onChange([...picks.map((p) => p.player_id), e.target.value])}>
        <option value="" disabled>Choose a player</option>
        {pool.map((p) => <option key={p.player_id} value={p.player_id}>{p.player_name} · {p.position} · {p.team}</option>)}
      </select>
    </label>
    <ul className="league-picks">
      {picks.map((p) => <li key={p.player_id}>
        <span>{p.player_name} · {p.position} · {p.projected_ppr_points.toFixed(1)} PPR</span>
        <button type="button" className="button" aria-label={`Remove ${p.player_name}`} onClick={() => onChange(picks.filter((item) => item !== p).map((item) => item.player_id))}>Remove</button>
      </li>)}
    </ul>
  </Panel>;
}

export function LeagueTools({ trade = false }: { trade?: boolean }) {
  const { selection } = useSeason();
  const load = useCallback(async (signal: AbortSignal) => {
    const first = await api.weekly({ season: selection!.season, week: selection!.week }, undefined, signal);
    const pool = [...first.projections];
    for (let offset = first.limit; offset < first.total; offset += first.limit) {
      const page = await api.weekly(selection!, undefined, signal, offset);
      pool.push(...page.projections);
    }
    return pool;
  }, [selection]);
  const result = useResource(selection ? load : null);
  const [teams, setTeams] = useState(12);
  const [first, setFirst] = useState<string[]>([]);
  const [second, setSecond] = useState<string[]>([]);
  const pool = result.data;
  const byId = new Map(pool?.map((p) => [p.player_id, p]));
  const selected = (ids: string[]) => ids.flatMap((id) => byId.get(id) ?? []);
  const rosterA = selected(first);
  const rosterB = selected(second);
  const missing = [...first, ...second].filter((id) => !byId.has(id));
  const available = pool?.filter((p) => !first.includes(p.player_id) && !second.includes(p.player_id))
    .sort((a, b) => a.player_name.localeCompare(b.player_name)) ?? [];
  const { replacement, average } = leagueBaselines(pool ?? [], teams);
  const value = (players: Projection[]) => players.reduce((sum, p) =>
    sum + Math.max(0, p.projected_ppr_points - Math.max(0, replacement.get(p.position) ?? 0)), 0);
  const a = value(rosterA);
  const b = value(rosterB);
  const lineup = bestLineup(rosterA);
  const points = lineup.reduce((sum, item) => sum + (item.player?.projected_ppr_points ?? 0), 0);
  const starters = new Set(lineup.map(({ player }) => player?.player_id));
  const tradeGrade = (received: number) => letterGrade(a + b ? 2 * received / (a + b) : 1);

  return <>
    <h1>{trade ? "Trade Analyzer" : "Team Evaluator"}</h1>
    <p>Full PPR · {selection ? `${selection.season} Week ${selection.week}` : "Select a season and week"} · 1 QB, 2 RB, 2 WR, 1 TE, 1 FLEX, 1 K, 1 D/ST</p>
    <label className="field-label league-size">Number of teams
      <select value={teams} onChange={(e) => setTeams(Number(e.target.value))}>
        {Array.from({ length: 13 }, (_, i) => i + 6).map((size) => <option key={size}>{size}</option>)}
      </select>
    </label>
    {result.loading && <Loading label="Loading Full PPR projections…" />}
    {result.error && <ErrorState error={result.error} retry={result.retry} />}
    {pool?.length === 0 && <p>No projections are available. Select another week.</p>}
    {!!pool?.length && <>
      {missing.length > 0 && <p role="status">{missing.length} selected player(s) have no projection this week. <button className="button" onClick={() => { setFirst(first.filter((id) => byId.has(id))); setSecond(second.filter((id) => byId.has(id))); }}>Clear unavailable picks</button></p>}
      <div className="two-columns">
        <Picks title={trade ? "Team A receives" : "Your roster"} pool={available} picks={rosterA} onChange={(ids) => setFirst([...ids, ...first.filter((id) => !byId.has(id))])} />
        {trade && <Picks title="Team B receives" pool={available} picks={rosterB} onChange={(ids) => setSecond([...ids, ...second.filter((id) => !byId.has(id))])} />}
      </div>
      {trade ? <Panel title="Trade grades">
        {rosterA.length && rosterB.length && !missing.length ? <div aria-live="polite">
          <p>Team A · <strong>{tradeGrade(a)}</strong> · {a.toFixed(1)} value points received</p>
          <p>Team B · <strong>{tradeGrade(b)}</strong> · {b.toFixed(1)} value points received</p>
        </div> : <p>Add players with projections to both sides to see grades.</p>}
        <p>Value points are weekly projected PPR above positional replacement in a {teams}-team league. Each grade reflects the side’s share of the total value. A B on both sides is a balanced deal.</p>
      </Panel> : <Panel title="Projected starting lineup">
        <p aria-live="polite">{rosterA.length > 0 && !missing.length ? <><strong>{average > 0 ? letterGrade(points / average) : "Grade unavailable"}</strong> · {points.toFixed(1)} PPR · League starter benchmark {average.toFixed(1)} PPR</> : "Add roster picks with projections to see a grade."}</p>
        <ul className="league-picks">
          {lineup.map(({ slot, player }, index) => <li key={index}><strong>{slot}</strong><span>{player ? `${player.player_name} · ${player.projected_ppr_points.toFixed(1)} PPR` : "Open slot"}</span></li>)}
        </ul>
        <p><strong>Bench</strong> · {rosterA.filter((p) => !starters.has(p.player_id)).map((p) => p.player_name).join(", ") || "Empty"}</p>
        <p>The grade compares your best starting lineup to the average projected starter total in a {teams}-team league. Open slots count as zero.</p>
      </Panel>}
    </>}
  </>;
}
