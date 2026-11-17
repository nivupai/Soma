import { useState } from "react";
import { Async, Panel, Warning, useResource } from "../components/Common";
type Level = {
  level: number;
  relative: number;
  alignment_scalar?: number;
  aligned_residual?: number;
  source_relative?: number[];
  geometry_match?: boolean;
  sensor_reference_match?: boolean;
  openmeeg_error?: number;
  mne_error?: number;
};
type Report = {
  schema: string;
  synthetic_only: boolean;
  human_subjects: number;
  threshold: number;
  solver_pair: string;
  heads: { head: number; levels: Level[] }[];
  controls: { reference: string; levels: Level[] }[];
};
export default function BEMDiagnostics() {
  const result = useResource<Report>("/bem-discrepancy");
  const [head, setHead] = useState(0);
  const [level, setLevel] = useState(3);
  const [reference, setReference] = useState("C");
  const [comparison, setComparison] = useState("pair");
  const d =
    result.data?.schema === "soma.bem-diagnostic.explorer/1" &&
    result.data.synthetic_only === true &&
    result.data.human_subjects === 0 &&
    result.data.threshold === 0.1
      ? result.data
      : undefined;
  const rows =
    reference === "C"
      ? d?.heads.find((h) => h.head === head)?.levels
      : d?.controls.find((c) => c.reference === reference)?.levels;
  const selected = rows?.find((r) => r.level === level);
  const value = (r: Level) =>
    comparison === "OM" && reference !== "C"
      ? r.openmeeg_error!
      : comparison === "MNE" && reference !== "C"
        ? r.mne_error!
        : r.relative;
  return (
    <Panel
      title="Independent BEM diagnostics"
      eyebrow="MATCHED SYNTHETIC PHYSICS / UNRESOLVED AGREEMENT"
    >
      <Async loading={result.loading} error={result.error}>
        {d && selected && (
          <>
            <Warning>
              Physical inputs match; discrete formulations differ. The finest
              nonspherical fields still fail the original 10% agreement target.
              No human accuracy, independent four-layer, FEM or phantom
              validation.
            </Warning>
            <div className="toolbar">
              <label>
                Physical reference{" "}
                <select
                  aria-label="BEM physical reference"
                  value={reference}
                  onChange={(e) => {
                    setReference(e.target.value);
                    setComparison("pair");
                  }}
                >
                  <option value="A">A: exact homogeneous sphere</option>
                  <option value="B">B: layered semi-analytical sphere</option>
                  <option value="C">C: nonspherical three-layer head</option>
                </select>
              </label>
              {reference === "C" && (
                <label>
                  Synthetic head{" "}
                  <select
                    aria-label="BEM synthetic head"
                    value={head}
                    onChange={(e) => setHead(Number(e.target.value))}
                  >
                    {d.heads.map((h) => (
                      <option key={h.head} value={h.head}>
                        Head {h.head}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <label>
                Resolution{" "}
                <select
                  aria-label="BEM mesh level"
                  value={level}
                  onChange={(e) => setLevel(Number(e.target.value))}
                >
                  {[1, 2, 3].map((l) => (
                    <option key={l} value={l}>
                      Level {l}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Solver comparison{" "}
                <select
                  aria-label="BEM solver comparison"
                  value={comparison}
                  onChange={(e) => setComparison(e.target.value)}
                >
                  <option value="pair">OpenMEEG / MNE pair</option>
                  {reference !== "C" && (
                    <>
                      <option value="OM">OpenMEEG / reference</option>
                      <option value="MNE">MNE / reference</option>
                    </>
                  )}
                </select>
              </label>
            </div>
            <p>
              {d.solver_pair}. Three merged brain/CSF, skull and scalp
              compartments. Canonical coordinates and average reference shared;
              no solver-specific sensor projection.
            </p>
            <div className="metrics">
              <div>
                <span>Physical relative field difference</span>
                <strong>{(value(selected) * 100).toFixed(2)}%</strong>
              </div>
              <div>
                <span>Original independent-pair target</span>
                <strong>10.00%</strong>
              </div>
              <div>
                <span>Geometry / sensor reference</span>
                <strong>Matched inputs</strong>
              </div>
            </div>
            <p>
              Pair evidence:{" "}
              {selected.relative <= 0.1
                ? "WITHIN FROZEN THRESHOLD"
                : "AGREEMENT NOT ESTABLISHED"}
              . Analytical acceptance is a separate 2% finest-level gate; a
              passing control does not validate nonspherical or human anatomy.
            </p>
            <svg
              viewBox="0 0 440 190"
              role="img"
              aria-label="BEM physical field refinement graph"
              style={{ width: "100%", maxHeight: 260 }}
            >
              <line
                x1="30"
                y1="120"
                x2="410"
                y2="120"
                stroke="red"
                strokeDasharray="4 4"
              />
              <text x="300" y="115" fill="currentColor">
                10% pair target
              </text>
              <polyline
                points={rows!
                  .map(
                    (r, i) =>
                      `${55 + i * 160},${160 - Math.min(value(r), 0.4) * 400}`,
                  )
                  .join(" ")}
                fill="none"
                stroke="var(--cyan)"
                strokeWidth="2"
              />
              {rows!.map((r, i) => (
                <g key={r.level}>
                  <circle
                    cx={55 + i * 160}
                    cy={160 - Math.min(value(r), 0.4) * 400}
                    r="5"
                    fill="var(--amber)"
                  />
                  <text x={25 + i * 160} y="180" fill="currentColor">
                    L{r.level}: {(value(r) * 100).toFixed(2)}%
                  </text>
                </g>
              ))}
            </svg>
            {selected.source_relative && (
              <>
                <h3>Off-grid source-wise field disagreement</h3>
                <svg
                  viewBox="0 0 600 180"
                  role="img"
                  aria-label="BEM off-grid source error plot"
                  style={{ width: "100%", maxHeight: 220 }}
                >
                  {selected.source_relative.map((v, i) => (
                    <g key={i}>
                      <rect
                        x={i * 49 + 5}
                        y={145 - Math.min(v, 0.5) * 250}
                        width="30"
                        height={Math.min(v, 0.5) * 250}
                        fill="var(--cyan)"
                      />
                      <text x={i * 49 + 5} y="170" fill="currentColor">
                        {i}
                      </text>
                      <title>
                        Source {i}: {(v * 100).toFixed(2)}%
                      </title>
                    </g>
                  ))}
                </svg>
                <p>
                  Twelve generators nested within this head; XYZ components
                  combined. Vertical scale 0–50%; repeated meshes and
                  orientations are not independent participants.
                </p>
                <p>
                  Scale-alignment diagnostic:{" "}
                  {selected.alignment_scalar?.toFixed(4)}; residual{" "}
                  {(selected.aligned_residual! * 100).toFixed(2)}%. These values
                  never rescale physical fields or determine acceptance.
                </p>
              </>
            )}
          </>
        )}
        {result.data && !d && (
          <Warning>
            Unverified BEM identity or modified threshold; scientific comparison
            withheld.
          </Warning>
        )}
      </Async>
    </Panel>
  );
}
