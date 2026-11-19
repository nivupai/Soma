import { useState } from "react";
import { Async, Panel, Warning, useResource } from "../components/Common";
import "./FEMReference.css";
type Curve = {
  spacing_mm: number;
  candidates: number;
  method: string;
  solver: string;
  noise_std_V: number;
  localization_mm: number;
  nearest_grid_mm: number;
  excess_localization_mm: number;
  localization_mm_lower: number;
  localization_mm_upper: number;
};
type Peak = {
  head: number;
  spacing_mm: number;
  method: string;
  solver: string;
  source: number;
  truth_xyz_m: number[];
  peak_xyz_m: number[];
};
type Report = {
  schema: string;
  synthetic_only: boolean;
  human_subjects: number;
  threshold: number;
  mesher: string;
  receipt: {
    computed_fields: number;
    failed_fields: number;
    matched_finest_pass: boolean;
  };
  comparisons: {
    head: number;
    level: number;
    condition: string;
    relative: number;
  }[];
  grid_summary: Curve[];
  peaks: Peak[];
  geometry: { head: number; level: number; sampled_max_mm: number }[];
};
export default function MeshGrid() {
  const r = useResource<Report>("/mesh-grid");
  const [head, setHead] = useState(0);
  const [level, setLevel] = useState(3);
  const [spacing, setSpacing] = useState(15);
  const [method, setMethod] = useState("Tikhonov");
  const [solver, setSolver] = useState("fem");
  const [source, setSource] = useState(0);
  const d =
    r.data?.schema === "soma.mesh-grid.explorer/1" &&
    r.data.synthetic_only === true &&
    r.data.human_subjects === 0 &&
    r.data.threshold === 0.1 &&
    r.data.mesher === "Gmsh4.15.2"
      ? r.data
      : undefined;
  const curves =
    d?.grid_summary
      .filter(
        (x) =>
          x.method === method && x.solver === solver && x.noise_std_V === 5e-8,
      )
      .sort((a, b) => a.candidates - b.candidates) ?? [];
  const selected = curves.find((x) => x.spacing_mm === spacing);
  const peak = d?.peaks.find(
    (x) =>
      x.head === head &&
      x.spacing_mm === spacing &&
      x.method === method &&
      x.solver === solver &&
      x.source === source,
  );
  const ymax = Math.max(1, ...curves.map((x) => x.localization_mm)) * 1.15;
  const matched = d?.comparisons.find(
    (x) => x.head === head && x.level === level && x.condition === "B matched",
  );
  const alternative = d?.comparisons.find(
    (x) =>
      x.head === head &&
      x.level === level &&
      x.condition === "C distinct boundary",
  );
  const deviation = Math.max(
    0,
    ...(d?.geometry
      .filter((x) => x.head === head && x.level === level)
      .map((x) => x.sampled_max_mm) ?? []),
  );
  return (
    <Panel
      title="Independent mesh and source-grid convergence"
      eyebrow="GMSH REPLICATION / SYNTHETIC ONLY"
    >
      <Async loading={r.loading} error={r.error}>
        {d && selected ? (
          <>
            <Warning>
              Shared-interface comparisons and independently sampled boundaries
              answer different questions. Grid-optimal distance is not actual
              inverse accuracy. Conditional six-head summaries do not establish
              human or phantom accuracy.
            </Warning>
            <div className="toolbar">
              <label>
                Head{" "}
                <select
                  aria-label="Mesh grid head"
                  value={head}
                  onChange={(e) => setHead(Number(e.target.value))}
                >
                  {[0, 1, 2, 3, 4, 5].map((x) => (
                    <option key={x}>{x}</option>
                  ))}
                </select>
              </label>
              <label>
                Forward mesh{" "}
                <select
                  aria-label="Independent forward mesh level"
                  value={level}
                  onChange={(e) => setLevel(Number(e.target.value))}
                >
                  {[1, 2, 3].map((x) => (
                    <option key={x}>{x}</option>
                  ))}
                </select>
              </label>
              <label>
                Grid{" "}
                <select
                  aria-label="Inverse grid spacing"
                  value={spacing}
                  onChange={(e) => setSpacing(Number(e.target.value))}
                >
                  {[
                    [0, "12 legacy"],
                    [30, "30 mm / 33 candidates"],
                    [20, "20 mm / 147 candidates"],
                    [15, "15 mm / 341 candidates"],
                  ].map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Method{" "}
                <select
                  aria-label="Grid inverse method"
                  value={method}
                  onChange={(e) => setMethod(e.target.value)}
                >
                  {["Tikhonov", "MNE", "dSPM"].map((x) => (
                    <option key={x}>{x}</option>
                  ))}
                </select>
              </label>
              <label>
                Model{" "}
                <select
                  aria-label="Grid inverse model"
                  value={solver}
                  onChange={(e) => setSolver(e.target.value)}
                >
                  <option value="fem">Gmsh FEM</option>
                  <option value="openmeeg">OpenMEEG</option>
                </select>
              </label>
            </div>
            <p>
              External mesher: Gmsh 4.15.2; independent tetrahedra, four
              material regions. Imported interface facets are audited after
              meshing. Alternative surfaces sample the same smooth target
              differently; their geometric mismatch is measured.
            </p>
            <p>
              Selected head/resolution, same-interface FEM/BEM difference:{" "}
              {matched
                ? (matched.relative * 100).toFixed(2) + "%"
                : "unavailable"}
              . Different-boundary comparison:{" "}
              {alternative
                ? (alternative.relative * 100).toFixed(2) + "%"
                : "unavailable"}
              . The latter includes geometry effects.
            </p>
            <p>
              Selected alternative boundary: sampled maximum deviation{" "}
              {deviation.toFixed(3)} mm at vertices/facet centroids, relative to
              standard finest surfaces. This is not a certified Hausdorff
              distance. Inverse operators remain fixed at level2; truth at
              level3.
            </p>
            <p>
              Reported configurations: {d.receipt.computed_fields} complete;{" "}
              {d.receipt.failed_fields} failed. Finest matched six-head gate:{" "}
              {d.receipt.matched_finest_pass ? "PASS" : "NOT ESTABLISHED"}.
              Physical amplitudes are never aligned to manufacture acceptance.
            </p>
            <svg
              className="fem-field-plot"
              viewBox="0 0 640 200"
              role="img"
              aria-label="Source grid localization and nearest-distance curves"
            >
              <polyline
                points={curves
                  .map(
                    (x) =>
                      `${40 + (x.candidates / 341) * 550},${160 - (x.localization_mm / ymax) * 140}`,
                  )
                  .join(" ")}
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              />
              <polyline
                points={curves
                  .map(
                    (x) =>
                      `${40 + (x.candidates / 341) * 550},${160 - (x.nearest_grid_mm / ymax) * 140}`,
                  )
                  .join(" ")}
                fill="none"
                stroke="#e5a54b"
                strokeDasharray="5 5"
              />
              {curves.map((x) => (
                <g key={x.candidates}>
                  <circle
                    cx={40 + (x.candidates / 341) * 550}
                    cy={160 - (x.localization_mm / ymax) * 140}
                    r="4"
                    fill="currentColor"
                  />
                  <text
                    x={40 + (x.candidates / 341) * 550}
                    y="185"
                    fill="currentColor"
                    fontSize="11"
                  >
                    {x.candidates}
                  </text>
                </g>
              ))}
              <text x="5" y="15" fill="currentColor" fontSize="11">
                {ymax.toFixed(1)} mm plot top
              </text>
            </svg>
            <p>
              Candidate count along x. Solid: actual peak error; dashed orange:
              nearest-grid lower bound. Curves average all six heads at .05 µV
              noise. Dense grids are not assumed to improve regularized error
              monotonically.
            </p>
            <table className="fem-reference-table">
              <thead>
                <tr>
                  <th>Candidates</th>
                  <th>Nearest (mm)</th>
                  <th>Peak error (mm)</th>
                  <th>Conditional interval (mm)</th>
                  <th>Excess (mm)</th>
                </tr>
              </thead>
              <tbody>
                {curves.map((x) => (
                  <tr key={x.candidates}>
                    <td>{x.candidates}</td>
                    <td>{x.nearest_grid_mm.toFixed(2)}</td>
                    <td>{x.localization_mm.toFixed(2)}</td>
                    <td>
                      {x.localization_mm_lower.toFixed(2)}–
                      {x.localization_mm_upper.toFixed(2)}
                    </td>
                    <td>{x.excess_localization_mm.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <label>
              Off-grid source{" "}
              <select
                aria-label="Grid truth source"
                value={source}
                onChange={(e) => setSource(Number(e.target.value))}
              >
                {Array.from({ length: 12 }, (_, i) => (
                  <option key={i}>{i}</option>
                ))}
              </select>
            </label>
            {peak && (
              <p>
                Selected head/source, first .05 µV noise draw: truth [
                {peak.truth_xyz_m.map((x) => (x * 1000).toFixed(1)).join(", ")}]
                mm; estimated peak [
                {peak.peak_xyz_m.map((x) => (x * 1000).toFixed(1)).join(", ")}]
                mm. MRI RAS coordinates. dSPM amplitudes are normalized, not
                physical dipole currents.
              </p>
            )}
          </>
        ) : (
          !r.loading && (
            <Warning>
              Unverified mesh/grid identity or modified target; results
              withheld.
            </Warning>
          )
        )}
      </Async>
    </Panel>
  );
}
