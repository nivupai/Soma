import { useState } from "react";
import { Async, Panel, Warning, useResource } from "../components/Common";

type Surface = { xyz_mm: number[][]; faces: number[][] };
type Head = {
  head: number;
  family: string;
  analysis_level: number;
  display_level: number;
  surfaces: Surface[];
  display_meshes?: Record<string, Surface[]>;
  sensors_mm: number[][];
  truth_mm: number[];
  grid_mm: number[][];
  estimates: Record<string, number[]>;
};
type Report = {
  schema: string;
  synthetic_only: boolean;
  human_subjects: number;
  heads: Head[];
  convergence: { head: number; status: string; errors: number[] }[];
  failures: { head: number; case: string; reason: string }[];
};
export default function Nonspherical() {
  const result = useResource<Report>("/nonspherical");
  const [head, setHead] = useState(0);
  const [level, setLevel] = useState(1);
  const [layer, setLayer] = useState(3);
  const [method, setMethod] = useState("MNE");
  const [view, setView] = useState("xy");
  const d =
    result.data?.schema === "soma.nonspherical.explorer/1" &&
    result.data.synthetic_only === true &&
    result.data.human_subjects === 0
      ? result.data
      : undefined;
  const h = d?.heads.find((h) => h.head === head);
  const x = (p: number[]) => 170 + p[0] * 1.5;
  const y = (p: number[]) => 170 - p[view === "xy" ? 1 : 2] * 1.5;
  const surfaces = h?.display_meshes?.[String(level)] || h?.surfaces;
  const cv = d?.convergence.find((c) => c.head === head);
  const values = h?.estimates[method] || [];
  const max = Math.max(...values, 1e-30);
  const failures = d?.failures.filter((f) => f.head === head) || [];
  return (
    <Panel
      title="Nonspherical conductor validation"
      eyebrow="SYNTHETIC BEM / CONDITIONAL SIMULATION"
    >
      <Async loading={result.loading} error={result.error}>
        {d && h && (
          <>
            <Warning>
              Six generated heads; no human MRI accuracy, FEM or measured
              phantom validation. Independent numerical control covers three
              layers only.
            </Warning>
            <div className="toolbar">
              <label>
                Display mesh{" "}
                <select
                  aria-label="Display mesh level"
                  value={level}
                  onChange={(e) => setLevel(Number(e.target.value))}
                >
                  {[0, 1, 2].map((l) => (
                    <option key={l} value={l}>
                      Level {l}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Synthetic head{" "}
                <select
                  aria-label="Synthetic head"
                  value={head}
                  onChange={(e) => setHead(Number(e.target.value))}
                >
                  {d.heads.map((h) => (
                    <option key={h.head} value={h.head}>
                      {h.head}: {h.family}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Surface{" "}
                <select
                  aria-label="Conductor surface"
                  value={layer}
                  onChange={(e) => setLayer(Number(e.target.value))}
                >
                  {["Brain", "CSF", "Skull", "Scalp"].map((s, i) => (
                    <option key={s} value={i}>
                      {s}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Method{" "}
                <select
                  aria-label="Nonspherical method"
                  value={method}
                  onChange={(e) => setMethod(e.target.value)}
                >
                  {["Tikhonov", "MNE", "dSPM"].map((m) => (
                    <option key={m}>{m}</option>
                  ))}
                </select>
              </label>
              <label>
                Projection{" "}
                <select
                  aria-label="Geometry projection"
                  value={view}
                  onChange={(e) => setView(e.target.value)}
                >
                  <option value="xy">XY</option>
                  <option value="xz">XZ</option>
                </select>
              </label>
            </div>
            <div className="two-col">
              <svg
                viewBox="0 0 340 350"
                role="img"
                aria-label="Synthetic conductor mesh and source distribution"
                style={{ width: "100%", maxHeight: 400 }}
              >
                {surfaces![layer].faces.map((f, i) => (
                  <polygon
                    key={i}
                    points={f
                      .map(
                        (j) =>
                          `${x(surfaces![layer].xyz_mm[j])},${y(surfaces![layer].xyz_mm[j])}`,
                      )
                      .join(" ")}
                    fill="none"
                    stroke="currentColor"
                    strokeWidth=".6"
                    opacity=".25"
                  />
                ))}
                {h.sensors_mm.map((p, i) => (
                  <circle
                    key={`s${i}`}
                    cx={x(p)}
                    cy={y(p)}
                    r="2"
                    fill="var(--cyan)"
                  />
                ))}
                {h.grid_mm.map((p, i) => (
                  <circle
                    key={`g${i}`}
                    cx={x(p)}
                    cy={y(p)}
                    r={1 + 6 * Math.sqrt(values[i] / max)}
                    fill="var(--amber)"
                    opacity={0.2 + (0.8 * values[i]) / max}
                  >
                    <title>
                      {p.map((v) => v.toFixed(1)).join(" / ")} mm;{" "}
                      {values[i].toExponential(3)}{" "}
                      {method === "dSPM" ? "normalized" : "A m"}
                    </title>
                  </circle>
                ))}
                <path
                  d={`M${x(h.truth_mm) - 6},${y(h.truth_mm)}h12 M${x(h.truth_mm)},${y(h.truth_mm) - 6}v12`}
                  stroke="red"
                  strokeWidth="3"
                >
                  <title>Off-grid truth source 0</title>
                </path>
                {failures.length > 0 && (
                  <text x="10" y="20" fill="red">
                    {failures.length} failed configurations retained
                  </text>
                )}
                <text x="10" y="340" fill="currentColor">
                  MRI RAS mm · {view.toUpperCase()} projection
                </text>
              </svg>
              <div>
                <h3>Mesh refinement relative field error</h3>
                {cv && (
                  <>
                    <p>
                      Head {head}: {cv.status}
                    </p>
                    <svg
                      viewBox="0 0 320 180"
                      role="img"
                      aria-label="Mesh convergence graph"
                      style={{ width: "100%", maxHeight: 220 }}
                    >
                      <polyline
                        points={cv.errors
                          .map(
                            (e, i) =>
                              `${40 + i * 100},${150 - Math.min(e, 1) * 120}`,
                          )
                          .join(" ")}
                        fill="none"
                        stroke="var(--cyan)"
                        strokeWidth="2"
                      />
                      {cv.errors.map((e, i) => (
                        <g key={i}>
                          <circle
                            cx={40 + i * 100}
                            cy={150 - Math.min(e, 1) * 120}
                            r="4"
                            fill="var(--amber)"
                          />
                          <text x={20 + i * 100} y="170" fill="currentColor">
                            L{i}: {(e * 100).toFixed(2)}%
                          </text>
                        </g>
                      ))}
                    </svg>
                  </>
                )}
                <p>
                  Estimated levels 0/1/2: 20/80/320 triangles per interface.
                  Reference level 3: 1280. Whole-model convergence includes
                  scalp sensor projection.
                </p>
                <p>
                  Display level {level} is a visualization example.
                  Reconstruction uses level {h.analysis_level}; noiseless source
                  0. Red cross: truth; amber: source amplitude; cyan: sensors.
                  Each method has its own size scale.
                </p>
                <details>
                  <summary>
                    Head {head} failures: {failures.length}
                  </summary>
                  {failures.map((f) => (
                    <p key={f.case}>
                      {f.case}: {f.reason}
                    </p>
                  ))}
                </details>
              </div>
            </div>
          </>
        )}
        {result.data && !d && (
          <Warning>
            Unverified nonspherical artifact; geometry withheld.
          </Warning>
        )}
      </Async>
    </Panel>
  );
}
