import type { Projection } from "./types";

export const lineupSlots = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K", "DST"];
const flex = ["RB", "WR", "TE"];

export function letterGrade(ratio: number) {
  if (ratio >= 1.15) return "A+";
  if (ratio >= 1.05) return "A";
  if (ratio >= 0.95) return "B";
  if (ratio >= 0.85) return "C";
  if (ratio >= 0.75) return "D";
  return "F";
}

export function bestLineup(players: Projection[]) {
  const remaining = [...players].sort((a, b) => b.projected_ppr_points - a.projected_ppr_points);
  return lineupSlots.map((slot) => {
    const index = remaining.findIndex((p) => slot === "FLEX" ? flex.includes(p.position) : slot === p.position);
    return { slot, player: index < 0 ? undefined : remaining.splice(index, 1)[0] };
  });
}

export function leagueBaselines(pool: Projection[], teams: number) {
  const replacement = new Map<string, number>();
  let average = 0;
  const remaining = [...pool].sort((a, b) => b.projected_ppr_points - a.projected_ppr_points);
  for (const slot of lineupSlots) {
    const starters = remaining.filter((p) => slot === "FLEX" ? flex.includes(p.position) : slot === p.position).slice(0, teams);
    average += starters.reduce((sum, p) => sum + p.projected_ppr_points, 0) / teams;
    const used = new Set(starters.map((p) => p.player_id));
    for (let index = remaining.length - 1; index >= 0; index--) {
      if (used.has(remaining[index].player_id)) remaining.splice(index, 1);
    }
  }
  for (const player of remaining) {
    if (!replacement.has(player.position)) replacement.set(player.position, player.projected_ppr_points);
  }
  return { replacement, average };
}
