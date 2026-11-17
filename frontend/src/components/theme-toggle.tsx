"use client";

import { useSyncExternalStore } from "react";
import { Moon, Sun } from "lucide-react";

const storageKey = "fantasy-advisor-theme";
type Theme = "light" | "dark";

function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", theme === "dark" ? "#191b1a" : "#f4f1e9");
  window.dispatchEvent(new Event("fantasy-theme-change"));
}

function subscribe(notify: () => void) {
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  const followSystem = () => {
    try {
      if (localStorage.getItem(storageKey)) return;
    } catch { /* A blocked store still allows theme switching. */ }
    applyTheme(media.matches ? "dark" : "light");
  };
  const syncStorage = (event: StorageEvent) => {
    if (event.key !== storageKey && event.key !== null) return;
    const theme = event.newValue;
    applyTheme(theme === "dark" || theme === "light" ? theme : media.matches ? "dark" : "light");
  };
  window.addEventListener("fantasy-theme-change", notify);
  window.addEventListener("storage", syncStorage);
  media.addEventListener("change", followSystem);
  return () => {
    window.removeEventListener("fantasy-theme-change", notify);
    window.removeEventListener("storage", syncStorage);
    media.removeEventListener("change", followSystem);
  };
}

export function ThemeToggle() {
  const theme = useSyncExternalStore(subscribe, () => document.documentElement.dataset.theme ?? "dark", () => "dark");
  const next: Theme = theme === "dark" ? "light" : "dark";
  return (
    <button type="button" className="theme-toggle" aria-label={`Switch to ${next} mode`} title={`Switch to ${next} mode`} onClick={() => {
      try { localStorage.setItem(storageKey, next); } catch { /* Apply for this visit. */ }
      applyTheme(next);
    }}>
      {theme === "dark" ? <Sun size={17} aria-hidden="true" /> : <Moon size={17} aria-hidden="true" />}
      <span>{next === "light" ? "Light mode" : "Dark mode"}</span>
    </button>
  );
}

