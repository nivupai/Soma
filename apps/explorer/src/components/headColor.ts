import type { Readiness, SourceUncertaintyOverlay } from "../api/client";

/** Sequential ramp stops (dark blue -> teal -> yellow), perceptually ordered. */
export const RAMP: [number, number, number][] = [
  [0.19, 0.2, 0.55],
  [0.13, 0.45, 0.56],
  [0.15, 0.68, 0.5],
  [0.55, 0.82, 0.28],
  [0.99, 0.9, 0.15],
];

export function rampColor(q: number): [number, number, number] {
  const t = Number.isFinite(q) ? Math.min(1, Math.max(0, q)) : 0;
  const x = t * (RAMP.length - 1);
  const i = Math.min(RAMP.length - 2, Math.floor(x));
  const f = x - i;
  const [a, b] = [RAMP[i], RAMP[i + 1]];
  return [0, 1, 2].map((k) => a[k] + (b[k] - a[k]) * f) as [
    number,
    number,
    number,
  ];
}

export function rampCss(q: number): string {
  const [r, g, b] = rampColor(q).map((c) => Math.round(c * 255));
  return `rgb(${r}, ${g}, ${b})`;
}

export function scalarRange(values: number[]): [number, number] {
  const finite = values.filter(Number.isFinite);
  if (!finite.length) return [0, 1];
  let lo = finite[0],
    hi = finite[0];
  for (const v of finite) {
    if (v < lo) lo = v;
    if (v > hi) hi = v;
  }
  return lo === hi ? [lo, lo + 1] : [lo, hi];
}

/** Flattened RGB triples for a scalar per source, normalized to range. */
export function colorsFor(values: number[], range: [number, number]): number[] {
  const [lo, hi] = range;
  const span = hi - lo || 1;
  return values.flatMap((v) => rampColor((v - lo) / span));
}

const LONG: Record<string, Readiness> = {
  VALIDATED_ANATOMY: "VALIDATED",
  QC_ONLY_ANATOMY: "QC_ONLY",
  NOT_READY_FOR_FORWARD_MODEL: "NOT_READY",
  VALIDATED: "VALIDATED",
  QC_ONLY: "QC_ONLY",
  NOT_READY: "NOT_READY",
};

/** Unknown or missing statuses never upgrade: they read as NOT_READY. */
export function readinessLabel(status: string | null | undefined): Readiness {
  return (status && LONG[status]) || "NOT_READY";
}

export type OverlayMode = "mean" | "width";

/** Returns an error message, or null when the overlay matches the sources. */
export function validateOverlay(
  overlay: SourceUncertaintyOverlay,
  nSources: number,
): string | null {
  if (overlay.contract !== "soma.explorer.source-uncertainty-overlay/1")
    return "Unsupported uncertainty contract";
  const { mean, lower, upper } = overlay;
  if (
    overlay.n_sources !== nSources ||
    mean.length !== nSources ||
    lower.length !== nSources ||
    upper.length !== nSources
  )
    return "Uncertainty overlay does not match the source space";
  for (let i = 0; i < nSources; i++)
    if (
      ![mean[i], lower[i], upper[i]].every(Number.isFinite) ||
      !(0 <= lower[i] && lower[i] <= mean[i] && mean[i] <= upper[i])
    )
      return `Invalid interval at source ${i}`;
  if (overlay.fixture !== (overlay.origin === "MOCK_FIXTURE"))
    return "Fixture flag contradicts the declared origin";
  return null;
}

export function overlayValues(
  overlay: SourceUncertaintyOverlay,
  mode: OverlayMode,
): number[] {
  return mode === "mean"
    ? overlay.mean
    : overlay.upper.map((u, i) => u - overlay.lower[i]);
}
