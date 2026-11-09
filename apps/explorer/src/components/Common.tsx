import { useEffect, useState, type ReactNode } from "react";
import { api, type Result } from "../api/client";
export function useResource<T>(path: string | null) {
  const [state, setState] = useState<{
    path: string | null;
    data: T | null;
    error: string;
    loading: boolean;
  }>({ path: null, data: null, error: "", loading: false });
  useEffect(() => {
    if (!path) return;
    const controller = new AbortController();
    setState({ path, data: null, error: "", loading: true });
    api<T>(path, { signal: controller.signal })
      .then((data) => setState({ path, data, error: "", loading: false }))
      .catch((e) => {
        if (!controller.signal.aborted)
          setState({
            path,
            data: null,
            error: String(e.message),
            loading: false,
          });
      });
    return () => controller.abort();
  }, [path]);
  return state.path === path
    ? state
    : { path, data: null, error: "", loading: !!path };
}
export function Async({
  loading,
  error,
  children,
}: {
  loading?: boolean;
  error?: string;
  children: ReactNode;
}) {
  return error ? (
    <div className="empty error" role="alert">
      <strong>Result unavailable</strong>
      <span>{error}</span>
    </div>
  ) : loading ? (
    <div className="loading" role="status">
      <span className="pulse" />
      Loading scientific data…
    </div>
  ) : (
    <>{children}</>
  );
}
export function Panel({
  title,
  eyebrow,
  children,
  actions,
  className = "",
}: {
  title: string;
  eyebrow?: string;
  children: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      <header className="panel-head">
        <div>
          {eyebrow && <span className="eyebrow">{eyebrow}</span>}
          <h2>{title}</h2>
        </div>
        {actions}
      </header>
      {children}
    </section>
  );
}
export function Warning({ children }: { children: ReactNode }) {
  return (
    <div className="warning">
      <span aria-hidden="true">△</span>
      <div>{children}</div>
    </div>
  );
}
export function Evidence({ result }: { result: Result<unknown> | null }) {
  return result ? (
    <div className="evidence">
      <span className="badge">
        {result.synthetic ? "SYNTHETIC · " : ""}
        {result.state.replaceAll("_", " ")}
      </span>
      {result.warnings.map((w) => (
        <Warning key={w}>{w}</Warning>
      ))}
    </div>
  ) : null;
}
export function Json({ value }: { value: unknown }) {
  return <pre className="json">{JSON.stringify(value, null, 2)}</pre>;
}
export function Trace({
  x,
  y,
  color = "var(--cyan)",
  label,
  log = false,
}: {
  x: number[];
  y: number[];
  color?: string;
  label: string;
  log?: boolean;
}) {
  if (!y.length) return <div className="empty">No data</div>;
  const values = y.map((v) => (log ? Math.log10(Math.max(v, 1e-30)) : v));
  const lo = Math.min(...values),
    hi = Math.max(...values);
  const path = values
    .map(
      (v, i) =>
        `${i ? "L" : "M"}${20 + (560 * (x[i] - x[0])) / (x.at(-1)! - x[0] || 1)},${125 - (100 * (v - lo)) / (hi - lo || 1)}`,
    )
    .join(" ");
  return (
    <svg role="img" aria-label={label} viewBox="0 0 600 155" className="trace">
      <defs>
        <pattern id="grid" width="70" height="25" patternUnits="userSpaceOnUse">
          <path
            d="M 70 0 L 0 0 0 25"
            fill="none"
            stroke="currentColor"
            strokeWidth=".4"
          />
        </pattern>
      </defs>
      <rect
        x="20"
        y="15"
        width="560"
        height="110"
        fill="url(#grid)"
        opacity=".3"
      />
      <path
        d={path}
        fill="none"
        stroke={color}
        strokeWidth="1.4"
        vectorEffect="non-scaling-stroke"
      />
      <text x="20" y="148">
        {x[0]?.toPrecision(3)}
      </text>
      <text x="540" y="148">
        {x.at(-1)?.toPrecision(3)}
      </text>
      <text x="25" y="25">
        {hi.toExponential(1)}
      </text>
      <text x="25" y="120">
        {lo.toExponential(1)}
      </text>
    </svg>
  );
}
