import Link from "next/link";
export default function NotFound() {
  return (
    <div className="state-box">
      <h1>Page not found</h1>
      <p>Return to the dashboard to explore player projections.</p>
      <Link className="button primary" href="/">
        Back to dashboard
      </Link>
    </div>
  );
}
