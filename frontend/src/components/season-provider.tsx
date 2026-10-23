"use client";
import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { api } from "@/lib/api";
import type { Health, Selection } from "@/lib/types";

interface SeasonContext {
  selection: Selection | null;
  select: (value: Selection) => void;
  health: Health | null;
  connectionError: string | null;
}
const Context = createContext<SeasonContext | null>(null);
export function SeasonProvider({ children }: { children: ReactNode }) {
  const [selection, setSelection] = useState<Selection | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    async function initialize() {
      let initial: Selection = { season: new Date().getUTCFullYear(), week: 1 };
      try {
        const data = await api.health(controller.signal);
        if (controller.signal.aborted) return;
        setHealth(data);
        const season = data.snapshot?.season;
        const weeks = season
          ? data.snapshot?.roster_weeks?.[String(season)]
          : undefined;
        if (season)
          initial = { season, week: weeks?.length ? Math.max(...weeks) : 1 };
      } catch (error) {
        if (controller.signal.aborted) return;
        setConnectionError(
          error instanceof Error
            ? error.message
            : "The data service is unavailable.",
        );
      }
      try {
        const saved: Selection | null = JSON.parse(
          localStorage.getItem("fantasy-selection") || "null",
        );
        if (
          saved &&
          Number.isInteger(saved.season) &&
          saved.season >= 2023 &&
          saved.season <= 2100 &&
          Number.isInteger(saved.week) &&
          saved.week >= 1 &&
          saved.week <= 18
        )
          initial = saved;
      } catch {
        /* Storage may be unavailable. The backend-derived default still works. */
      }
      setSelection(initial);
    }
    void initialize();
    return () => controller.abort();
  }, []);
  function select(value: Selection) {
    setSelection(value);
    try {
      localStorage.setItem("fantasy-selection", JSON.stringify(value));
    } catch {
      /* Selection still works without storage. */
    }
  }
  return (
    <Context.Provider value={{ selection, select, health, connectionError }}>
      {children}
    </Context.Provider>
  );
}
export function useSeason() {
  const context = useContext(Context);
  if (!context) throw new Error("SeasonProvider is required");
  return context;
}
export function WeekPicker() {
  const { selection, select, health } = useSeason();
  const season =
    selection?.season ??
    health?.snapshot?.season ??
    new Date().getUTCFullYear();
  const years = Array.from(
    new Set([
      season,
      new Date().getUTCFullYear() + 1,
      ...Array.from(
        { length: Math.max(1, new Date().getUTCFullYear() - 2022) },
        (_, i) => 2023 + i,
      ),
    ]),
  ).sort((a, b) => b - a);
  return (
    <div className="week-picker">
      <label>
        <span>Season</span>
        <select
          aria-label="NFL season"
          disabled={!selection}
          value={season}
          onChange={(e) =>
            select({
              season: Number(e.target.value),
              week: selection?.week ?? 1,
            })
          }
        >
          {years.map((year) => (
            <option key={year}>{year}</option>
          ))}
        </select>
      </label>
      <span className="picker-divider" />
      <label>
        <span>Regular season</span>
        <select
          aria-label="NFL week"
          disabled={!selection}
          value={selection?.week ?? 1}
          onChange={(e) => select({ season, week: Number(e.target.value) })}
        >
          {Array.from({ length: 18 }, (_, i) => (
            <option key={i} value={i + 1}>
              Week {String(i + 1).padStart(2, "0")}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
