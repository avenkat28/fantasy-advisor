import { AlertCircle, ArrowUpRight, LoaderCircle, SearchX } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

export function PageHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </div>
  );
}
export function Panel({
  title,
  subtitle,
  action,
  children,
  className = "",
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-heading">
        <div>
          <h2>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
export function Loading({ label = "Loading analytics…" }: { label?: string }) {
  return (
    <div className="state-box" role="status">
      <LoaderCircle className="spin" size={24} />
      <p>{label}</p>
      <div className="skeleton" />
      <div className="skeleton short" />
    </div>
  );
}
export function ErrorState({
  error,
  retry,
}: {
  error: Error | string;
  retry?: () => void;
}) {
  return (
    <div className="state-box error-state" role="alert">
      <AlertCircle size={24} />
      <h3>Data unavailable</h3>
      <p>{typeof error === "string" ? error : error.message}</p>
      {retry && (
        <button className="button secondary" onClick={retry}>
          Try again
        </button>
      )}
    </div>
  );
}
export function EmptyState({
  title = "No results for this selection",
  message = "Try another player, position, season, or week.",
}: {
  title?: string;
  message?: string;
}) {
  return (
    <div className="state-box">
      <SearchX size={26} />
      <h3>{title}</h3>
      <p>{message}</p>
    </div>
  );
}
export function PositionBadge({ position }: { position: string }) {
  return (
    <span className={`position ${position === "WR" ? "wide" : ""}`}>
      {position}
    </span>
  );
}
export function TextLink({
  href,
  children,
}: {
  href: string;
  children: ReactNode;
}) {
  return (
    <Link className="text-link" href={href}>
      {children}
      <ArrowUpRight size={15} aria-hidden="true" />
    </Link>
  );
}
export function NumberValue({
  value,
  digits = 1,
}: {
  value: number | null | undefined;
  digits?: number;
}) {
  return (
    <>
      {value == null || !Number.isFinite(value) ? "—" : value.toFixed(digits)}
    </>
  );
}
export function Stat({
  label,
  value,
  note,
  accent = false,
}: {
  label: string;
  value: ReactNode;
  note?: ReactNode;
  accent?: boolean;
}) {
  return (
    <div className={`stat-card ${accent ? "accent-stat" : ""}`}>
      <span className="stat-label">{label}</span>
      <div className="stat-value">{value}</div>
      {note && <p>{note}</p>}
    </div>
  );
}
export function dateLabel(value: string | null | undefined) {
  if (!value) return "Not available";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Not available"
    : date.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        timeZone: "UTC",
      });
}
