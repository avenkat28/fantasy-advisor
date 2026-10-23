"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  ArrowLeftRight,
  BarChart3,
  ChevronRight,
  LayoutDashboard,
  Search,
  ShieldCheck,
  TrendingUp,
} from "lucide-react";
import type { ReactNode } from "react";
import { SeasonProvider, useSeason, WeekPicker } from "./season-provider";
import { dateLabel } from "./ui";
const links = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/projections", label: "Weekly Projections", icon: TrendingUp },
  { href: "/players", label: "Player Search", icon: Search },
  { href: "/compare", label: "Start/Sit Comparison", icon: ArrowLeftRight },
  { href: "/performance", label: "Model Performance", icon: BarChart3 },
];
export function Navigation() {
  const pathname = usePathname();
  return (
    <nav aria-label="Main navigation">
      {links.map(({ href, label, icon: Icon }) => {
        const active =
          href === "/" ? pathname === "/" : pathname.startsWith(href);
        return (
          <Link
            href={href}
            key={href}
            className={`nav-link ${active ? "active" : ""}`}
            aria-current={active ? "page" : undefined}
          >
            <Icon size={19} aria-hidden="true" />
            <span>{label}</span>
            {active && <ChevronRight className="nav-chevron" size={14} />}
          </Link>
        );
      })}
    </nav>
  );
}
function Frame({ children }: { children: ReactNode }) {
  const { health, connectionError } = useSeason();
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <aside className="sidebar">
        <Link href="/" className="brand" aria-label="FantasyAdvisor dashboard">
          <span className="brand-icon">
            <Activity size={24} />
          </span>
          <span>
            Fantasy<span className="brand-light">Advisor</span>
            <small>THE NUMBERS. YOUR EDGE.</small>
          </span>
        </Link>
        <div className="nav-caption">WORKSPACE</div>
        <Navigation />
        <div className="sidebar-bottom">
          <div className="model-note">
            <ShieldCheck size={20} />
            <div>
              <strong>Built on the numbers</strong>
              <p>
                Full-PPR · RB & WR
                <br />
                XGBoost projections
              </p>
            </div>
          </div>
          <div className="sidebar-foot">
            <span className="status-dot" />
            NFL analytics workspace<span>v0.5</span>
          </div>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="workspace-title">
            <span className="topbar-icon">
              <BarChart3 size={17} />
            </span>{" "}
            NFL Fantasy Intelligence <span className="tag">FULL PPR</span>
          </div>
          <WeekPicker />
        </header>
        <main id="main-content" tabIndex={-1}>
          {children}
        </main>
        <footer className="footer">
          <span>
            FantasyAdvisor <span className="muted">/</span> Informed decisions.
            Every week.
          </span>
          <span className="snapshot-label">
            <span
              className={`status-dot ${connectionError || health?.status === "degraded" ? "warning" : ""}`}
            />
            {health?.snapshot
              ? `Snapshot · ${dateLabel(health.snapshot.observed_at)}`
              : connectionError
                ? "Data service unavailable"
                : "Historical data snapshots"}
          </span>
        </footer>
      </div>
    </div>
  );
}
export function Shell({ children }: { children: ReactNode }) {
  return (
    <SeasonProvider>
      <Frame>{children}</Frame>
    </SeasonProvider>
  );
}
