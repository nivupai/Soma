import { useState } from "react";
import { Async, Panel, Warning, useResource } from "../components/Common";

type Example = {
  scenario: string;
  family: string;
  method: string;
  grid_mm: number[][];
  truth_mm: number[];
  baseline: number[];
  perturbed: number[];
  units: string;
  metrics: {
    localization_mm: number;
    dispersion_mm: number;
    nearest_grid_mm: number;
    peak_amplitude_bias_ratio: number | null;
  };
};
type Report = {
  schema: string;
  synthetic_only: boolean;
  human_subjects: number;
  protocol_fingerprint: string;
  configurations: number;
  failed_configurations: string[];
  warning: string;
  examples: Example[];
};
function Map({ data, baseline }: { data: Example; baseline: boolean }) {
  const values = baseline ? data.baseline : data.perturbed;
  const max = Math.max(...values);
  const peak = values.indexOf(max);
  const px = (v: number) => 160 + v * 2;
  const py = (v: number) => 160 - v * 2;
  return (
    <svg
      viewBox="0 0 320 320"
      role="img"
      aria-label={
        baseline ? "Baseline source estimate" : "Perturbed source estimate"
      }
      style={{ width: "100%", maxHeight: 320 }}
    >
      <circle
        cx="160"
        cy="160"
        r="145"
        fill="none"
        stroke="currentColor"
        opacity=".2"
      />
      {data.grid_mm.map((p, i) => (
        <circle
          key={i}
          cx={px(p[0])}
          cy={py(p[1])}
          r={2 + 10 * Math.sqrt(values[i] / max)}
          fill={i === peak ? "var(--amber)" : "var(--cyan)"}
          opacity={0.2 + (0.8 * values[i]) / max}
        >
          <title>
            {p.map((v) => v.toFixed(1)).join(", ")} mm ·{" "}
            {values[i].toExponential(3)} {data.units}
          </title>
        </circle>
      ))}
      <path
        d={`M${px(data.truth_mm[0]) - 7},${py(data.truth_mm[1])}h14 M${px(data.truth_mm[0])},${py(data.truth_mm[1]) - 7}v14`}
        stroke="var(--coral, #e85d75)"
        strokeWidth="3"
      >
        <title>Known ground truth</title>
      </path>
      <text x="8" y="310" fill="currentColor" fontSize="11">
        True MRI x / y (mm) · XY projection
      </text>
    </svg>
  );
}
export default function SourceUncertainty() {
  const result = useResource<Report>("/source-uncertainty");
  const [method, setMethod] = useState("MNE");
  const [scenario, setScenario] = useState("conductivity-0.01");
  const d =
    result.data?.schema === "soma.source-uncertainty.explorer/1" &&
    result.data.synthetic_only === true &&
    result.data.human_subjects === 0
      ? result.data
      : undefined;
  const options = d?.examples.filter((e) => e.method === method) || [];
  const selected = options.find((e) => e.scenario === scenario) || options[0];
  return (
    <Panel
      title="Anatomical uncertainty experiment"
      eyebrow="KNOWN SYNTHETIC TRUTH / PHYSICAL FOUR-SHELL CONDUCTOR"
    >
      <Async loading={result.loading} error={result.error}>
        {d && selected && (
          <>
            <Warning>{d.warning}</Warning>
            <div className="toolbar">
              <label>
                Inverse method{" "}
                <select
                  aria-label="Uncertainty inverse method"
                  value={method}
                  onChange={(e) => setMethod(e.target.value)}
                >
                  {["Tikhonov", "MNE", "dSPM"].map((m) => (
                    <option key={m}>{m}</option>
                  ))}
                </select>
              </label>
              <label>
                Error source{" "}
                <select
                  aria-label="Source uncertainty scenario"
                  value={selected.scenario}
                  onChange={(e) => setScenario(e.target.value)}
                >
                  {options.map((e) => (
                    <option key={e.scenario} value={e.scenario}>
                      {e.scenario}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <p>
              Selected error source: {selected.family}. Cross = known ground
              truth; amber = estimated peak.
            </p>
            <div className="two-col">
              <div>
                <h3>Baseline source estimate</h3>
                <Map data={selected} baseline />
              </div>
              <div>
                <h3>Perturbed source estimate</h3>
                <Map data={selected} baseline={false} />
              </div>
            </div>
            <div className="metrics">
              <div>
                <span>3D peak displacement</span>
                <strong>
                  {selected.metrics.localization_mm.toFixed(2)} mm
                </strong>
              </div>
              <div>
                <span>Spatial dispersion</span>
                <strong>{selected.metrics.dispersion_mm.toFixed(2)} mm</strong>
              </div>
              <div>
                <span>Nearest possible grid point</span>
                <strong>
                  {selected.metrics.nearest_grid_mm.toFixed(2)} mm
                </strong>
              </div>
              <div>
                <span>Peak amplitude bias</span>
                <strong>
                  {selected.metrics.peak_amplitude_bias_ratio === null
                    ? "Not physical (dSPM)"
                    : `${(selected.metrics.peak_amplitude_bias_ratio * 100).toFixed(1)}%`}
                </strong>
              </div>
            </div>
            <p>
              One noiseless off-grid generator example; each map has its own
              color/size scale. Quantitative differences use the underlying
              arrays. Ground truth:{" "}
              {selected.truth_mm.map((v) => v.toFixed(2)).join(" / ")} mm.
            </p>
            <details>
              <summary>
                Numerical failures retained: {d.failed_configurations.length} /{" "}
                {d.configurations}
              </summary>
              <ul>
                {d.failed_configurations.map((f) => (
                  <li key={f}>{f}</li>
                ))}
              </ul>
            </details>
            <p className="mono">Protocol {d.protocol_fingerprint}</p>
          </>
        )}
        {result.data && !d && (
          <Warning>
            Unverified uncertainty artifact: no source map displayed.
          </Warning>
        )}
      </Async>
    </Panel>
  );
}
