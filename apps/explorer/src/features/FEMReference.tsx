import { useState } from "react";
import "./FEMReference.css";
import { Async, Panel, Warning, useResource } from "../components/Common";
type Row = {
  head: number;
  level: number;
  relative: number;
  alpha: number;
  aligned: number;
};
type Source = {
  head: number;
  level: number;
  source: number;
  relative: number;
  depth_radius_mm: number;
};
type Report = {
  schema: string;
  synthetic_only: boolean;
  human_subjects: number;
  threshold: number;
  heads: Row[];
  source_fields: Source[];
  receipt: {
    models_computed: number;
    models_failed: number;
    analytical_limit_pass: boolean;
    independent_four_layer_agreement_pass: boolean;
  };
  inverse: {
    method: string;
    solver: string;
    noise_std_V: number;
    localization_mm: number;
    dispersion_mm: number;
  }[];
};
export default function FEMReference() {
  const result = useResource<Report>("/fem-reference");
  const [head, setHead] = useState(0);
  const [level, setLevel] = useState(3);
  const d =
    result.data?.schema === "soma.fem-reference.explorer/1" &&
    result.data.synthetic_only === true &&
    result.data.human_subjects === 0 &&
    result.data.threshold === 0.1
      ? result.data
      : undefined;
  const row = d?.heads.find((r) => r.head === head && r.level === level);
  const sources =
    d?.source_fields.filter((r) => r.head === head && r.level === level) ?? [];
  const plotMax = Math.max(0.01, ...sources.map((s) => s.relative)) * 1.2;
  return (
    <Panel
      title="Independent four-layer FEM reference"
      eyebrow="SYNTHETIC / GALERKIN FULL SUBTRACTION"
    >
      <Async loading={result.loading} error={result.error}>
        {d && row ? (
          <>
            <Warning>
              Independent synthetic discretizations share physical boundaries.
              The finest FEM is an approximation. This comparison does not
              establish human or phantom accuracy. M28 findings remain
              unchanged.
            </Warning>
            <div className="toolbar">
              <label>
                Head{" "}
                <select
                  aria-label="FEM synthetic head"
                  value={head}
                  onChange={(e) => setHead(Number(e.target.value))}
                >
                  {[0, 1, 2, 3, 4, 5].map((h) => (
                    <option key={h} value={h}>
                      {h}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Resolution{" "}
                <select
                  aria-label="FEM mesh level"
                  value={level}
                  onChange={(e) => setLevel(Number(e.target.value))}
                >
                  {[1, 2, 3].map((l) => (
                    <option key={l} value={l}>
                      {l}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <p>
              Four isotropic compartments: brain .33, CSF 1, skull .004, scalp
              .33 S/m. Exact shared polyhedral surface facets; canonical
              sensors; average reference; source-major XYZ in V/(A m).
            </p>
            <p>
              Unscaled OpenMEEG / FEM difference:{" "}
              <strong>{(100 * row.relative).toFixed(2)}%</strong>. Frozen
              engineering target: 10%.{" "}
              {row.relative <= 0.1
                ? "Selected comparison passes."
                : "Selected comparison fails."}
            </p>
            <p>
              Overall finest four-layer gate:{" "}
              {d.receipt.independent_four_layer_agreement_pass
                ? "PASS"
                : "NOT ESTABLISHED"}
              . Analytical homogeneous gate:{" "}
              {d.receipt.analytical_limit_pass ? "PASS" : "NOT ESTABLISHED"}.
              Computed configurations: {d.receipt.models_computed}; retained
              failures: {d.receipt.models_failed}.
            </p>
            <p>
              Diagnostic scalar {row.alpha.toFixed(4)}; aligned residual{" "}
              {(row.aligned * 100).toFixed(2)}%. Alignment is never applied to
              the primary physical comparison.
            </p>
            <svg
              viewBox="0 0 640 180"
              className="fem-field-plot"
              role="img"
              aria-label="FEM source-wise physical field differences"
            >
              {sources.map((s, i) => (
                <g key={s.source}>
                  <rect
                    x={i * 50 + 15}
                    y={155 - (s.relative / plotMax) * 140}
                    width="30"
                    height={(s.relative / plotMax) * 140}
                    fill="currentColor"
                  >
                    <title>{`Source ${s.source - 12}: radius ${s.depth_radius_mm.toFixed(1)} mm, ${(s.relative * 100).toFixed(2)}%`}</title>
                  </rect>
                  <text
                    x={i * 50 + 15}
                    y="175"
                    fontSize="10"
                    fill="currentColor"
                  >
                    {s.source - 12}
                  </text>
                </g>
              ))}
              <text x="5" y="12" fontSize="10" fill="currentColor">
                {(plotMax * 100).toFixed(2)}% plot top
              </text>
              {plotMax >= 0.1 && (
                <line
                  x1="0"
                  y1={155 - (0.1 / plotMax) * 140}
                  x2="640"
                  y2={155 - (0.1 / plotMax) * 140}
                  stroke="red"
                  strokeDasharray="5 5"
                />
              )}
            </svg>
            <p>
              12 independently drawn sources per head; XYZ is combined per
              source.{" "}
              {plotMax >= 0.1
                ? "Red line: 10% target."
                : "The 10% target lies above the displayed range."}{" "}
              Mesh levels are repeated computations.
            </p>
            <table className="fem-reference-table">
              <caption>
                Frozen level2 inverse estimates, .05 µV noise; finest FEM truth.
                Shared truth favors neither a human nor a clinical claim.
              </caption>
              <thead>
                <tr>
                  <th>Method</th>
                  <th>Model</th>
                  <th>Peak error (mm)</th>
                  <th>Dispersion (mm)</th>
                </tr>
              </thead>
              <tbody>
                {d.inverse
                  .filter((r) => r.noise_std_V === 5e-8)
                  .map((r) => (
                    <tr key={r.method + r.solver}>
                      <td>{r.method}</td>
                      <td>{r.solver}</td>
                      <td>{r.localization_mm.toFixed(2)}</td>
                      <td>{r.dispersion_mm.toFixed(2)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </>
        ) : (
          !result.loading && (
            <Warning>
              Unverified FEM identity or modified threshold; results withheld.
            </Warning>
          )
        )}
      </Async>
    </Panel>
  );
}
