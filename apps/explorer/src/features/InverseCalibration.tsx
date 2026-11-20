import { useState } from "react";
import { Async, Panel, Warning, useResource } from "../components/Common";

type Row = {
  grid: string;
  candidates: number;
  prior: string;
  method: string;
  policy: string;
  noise_std_V: number;
  localization_mm: number;
  excess_mm: number;
  dispersion_mm: number;
  localization_mm_lower: number;
  localization_mm_upper: number;
};
type Source = Row & {
  head: number;
  source: number;
  depth_radius_mm: number;
  brain_surface_depth_mm: number;
  orientation_radial_cosine: number;
};
type Example = Row & {
  grid_mm: number[][];
  truth_mm: number[];
  amplitude: number[];
  PSF: number[];
  units: string;
};
type Report = {
  schema: string;
  synthetic_only: boolean;
  human_subjects: number;
  design_sha256: string;
  warning: string;
  summary: Row[];
  source_metrics: Source[];
  examples: Example[];
  failures: unknown[];
  receipt: {
    heads: number;
    original_sources: number;
    new_heldout_sources: number;
    failed_configurations: number;
  };
};

export default function InverseCalibration() {
  const r = useResource<Report>("/inverse-calibration");
  const [grid, setGrid] = useState("nested2");
  const [prior, setPrior] = useState("cell_volume");
  const [policy, setPolicy] = useState("spectral");
  const [method, setMethod] = useState("MNE");
  const [noise, setNoise] = useState("5e-8");
  const [depth, setDepth] = useState(0);
  const valid =
    r.data?.schema === "soma.inverse-calibration.explorer/1" &&
    r.data.synthetic_only === true &&
    r.data.human_subjects === 0;
  const report = valid ? r.data : null;
  const match = (a: Row) =>
    a.prior === prior &&
    a.policy === policy &&
    a.method === method &&
    a.noise_std_V === Number(noise);
  const rows =
    report?.summary.filter(match).sort((a, b) => a.candidates - b.candidates) ??
    [];
  const selected = rows.find((a) => a.grid === grid);
  const sources =
    report?.source_metrics.filter(
      (a) => match(a) && a.grid === grid && a.brain_surface_depth_mm >= depth,
    ) ?? [];
  const example = report?.examples.find((a) => match(a) && a.grid === grid);
  return (
    <Panel
      title="Inverse priors and source-density calibration"
      eyebrow="M31 · frozen synthetic experiment"
    >
      <Async
        loading={r.loading}
        error={
          r.error ||
          (r.data && !valid ? "Unsupported synthetic inverse result" : "")
        }
      >
        {report && (
          <>
            <Warning>{report.warning}</Warning>
            <p>
              {report.receipt.heads} synthetic heads ·{" "}
              {report.receipt.original_sources} original sources +{" "}
              {report.receipt.new_heldout_sources} new held-out sources.
              Calibration uses source IDs 0–5; combined test uses IDs 6–15. No
              human validation.
            </p>
            <div className="controls">
              <label>
                Candidate grid{" "}
                <select
                  aria-label="Prior candidate grid"
                  value={grid}
                  onChange={(e) => setGrid(e.target.value)}
                >
                  {[
                    "legacy12",
                    "cart30",
                    "cart20",
                    "cart15",
                    "nested0",
                    "nested1",
                    "nested2",
                  ].map((v) => (
                    <option key={v}>{v}</option>
                  ))}
                </select>
              </label>
              <label>
                Prior{" "}
                <select
                  aria-label="Source prior"
                  value={prior}
                  onChange={(e) => setPrior(e.target.value)}
                >
                  {["unweighted", "cell_volume", "total_variance"].map((v) => (
                    <option key={v}>{v}</option>
                  ))}
                </select>
              </label>
              <label>
                Regularization{" "}
                <select
                  aria-label="Prior regularization"
                  value={policy}
                  onChange={(e) => setPolicy(e.target.value)}
                >
                  {["historical", "spectral", "prediction"].map((v) => (
                    <option key={v}>{v}</option>
                  ))}
                </select>
              </label>
              <label>
                Inverse{" "}
                <select
                  aria-label="Prior inverse method"
                  value={method}
                  onChange={(e) => setMethod(e.target.value)}
                >
                  {["Tikhonov", "MNE", "dSPM"].map((v) => (
                    <option key={v}>{v}</option>
                  ))}
                </select>
              </label>
              <label>
                Noise{" "}
                <select
                  aria-label="Prior noise"
                  value={noise}
                  onChange={(e) => setNoise(e.target.value)}
                >
                  <option value="0">0 µV</option>
                  <option value="5e-8">0.05 µV</option>
                  <option value="1.5e-7">0.15 µV</option>
                </select>
              </label>
            </div>
            {selected && (
              <p aria-live="polite">
                {selected.candidates} candidates · peak error{" "}
                {selected.localization_mm.toFixed(2)} mm (conditional 95%
                interval {selected.localization_mm_lower.toFixed(2)}–
                {selected.localization_mm_upper.toFixed(2)}) · excess{" "}
                {selected.excess_mm.toFixed(2)} mm · dispersion{" "}
                {selected.dispersion_mm.toFixed(2)} mm.
              </p>
            )}
            <table>
              <caption>
                Computed held-out FEM results; source repeats averaged before
                clustered uncertainty
              </caption>
              <thead>
                <tr>
                  <th>Grid</th>
                  <th>Candidates</th>
                  <th>Peak error (mm)</th>
                  <th>Excess (mm)</th>
                  <th>Dispersion (mm)</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((v) => (
                  <tr key={v.grid}>
                    <td>{v.grid}</td>
                    <td>{v.candidates}</td>
                    <td>{v.localization_mm.toFixed(2)}</td>
                    <td>{v.excess_mm.toFixed(2)}</td>
                    <td>{v.dispersion_mm.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <label>
              Head 0 source detail: minimum distance below brain interface (mm){" "}
              <input
                aria-label="Source brain depth"
                type="range"
                min="0"
                max="60"
                value={depth}
                onChange={(e) => setDepth(Number(e.target.value))}
              />
              {depth}
            </label>
            <p>
              Depth/orientation detail is a bounded head 0 slice at 0.05 µV. The
              table above always uses all 60 test sources across six heads.
              Depth is minimum distance to the finest synthetic brain interface;
              radius is retained separately.
            </p>
            <svg
              viewBox="0 0 420 180"
              role="img"
              aria-label="Observed source depth and localization error"
              style={{ width: "100%", maxHeight: 220 }}
            >
              {sources.map((s) => (
                <circle
                  key={s.source}
                  cx={20 + s.brain_surface_depth_mm * 7}
                  cy={160 - Math.min(s.localization_mm, 140)}
                  r="5"
                  fill="var(--cyan)"
                >
                  <title>
                    Source {s.source}: radius {s.depth_radius_mm.toFixed(2)} mm,
                    error {s.localization_mm.toFixed(2)} mm, radial orientation
                    cosine {s.orientation_radial_cosine.toFixed(3)}
                  </title>
                </circle>
              ))}
              <text x="8" y="178" fill="currentColor" fontSize="10">
                Brain depth → · Error ↑ · hover for orientation · observed
                points only
              </text>
            </svg>
            {example ? (
              <>
                <p>
                  Actual head 0, new source 12, XY projection. {example.units};
                  dSPM is dimensionless and cannot be interpreted as dipole
                  current. Point-spread response units:{" "}
                  {method === "dSPM" ? "1/(A·m)" : "1"}.
                </p>
                <div className="two-col">
                  {(["amplitude", "PSF"] as const).map((key) => {
                    const values = example[key];
                    const max = Math.max(...values);
                    return (
                      <svg
                        key={key}
                        viewBox="0 0 320 320"
                        role="img"
                        aria-label={
                          key === "PSF"
                            ? "Computed inverse point-spread response"
                            : "Computed source estimate"
                        }
                        style={{ width: "100%", maxHeight: 300 }}
                      >
                        {example.grid_mm.map((p, i) => (
                          <circle
                            key={i}
                            cx={160 + 2 * p[0]}
                            cy={160 - 2 * p[1]}
                            r={1 + 6 * Math.sqrt(values[i] / max)}
                            fill="var(--cyan)"
                            opacity={0.15 + (0.85 * values[i]) / max}
                          >
                            <title>
                              {p.map((v) => v.toFixed(1)).join(", ")} mm:{" "}
                              {values[i].toExponential(3)}
                            </title>
                          </circle>
                        ))}
                        <path
                          d={`M${153 + 2 * example.truth_mm[0]},${160 - 2 * example.truth_mm[1]}h14 M${160 + 2 * example.truth_mm[0]},${153 - 2 * example.truth_mm[1]}v14`}
                          stroke="var(--amber)"
                        />
                        <text x="8" y="310" fill="currentColor">
                          {key === "PSF"
                            ? "Orientation-block PSF; nearest candidate probe"
                            : "Known truth cross; actual estimate"}
                        </text>
                      </svg>
                    );
                  })}
                </div>
              </>
            ) : (
              <p>
                Spatial and point-spread detail is archived for nested2,
                spectral policy, 0.05 µV. Other combinations are available in
                the computed tables, without synthesized spatial maps.
              </p>
            )}
            <p>
              Reported numerical failures: {report.failures.length}. Frozen
              protocol SHA256: <code>{report.design_sha256}</code>.
              Independent-repeat tuning can reach a sweep boundary, especially
              without noise. The native M30 portability diagnostic remains a
              separate release blocker.
            </p>
          </>
        )}
      </Async>
    </Panel>
  );
}
