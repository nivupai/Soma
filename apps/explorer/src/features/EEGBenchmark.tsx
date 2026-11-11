import { useState } from "react";
import "./EEGBenchmark.css";
import { Panel, Async, Warning, useResource } from "../components/Common";
type Method = {
  model: string;
  mode: string;
  complete_subjects: number;
  missing_subjects: number;
  subject_distribution?: number[];
  distribution_bin_edges?: number[];
  balanced_accuracy: {
    mean: number;
    lower: number;
    upper: number;
    n_subjects: number;
  } | null;
};
type Report = {
  status: string;
  warnings: string[];
  protocol_fingerprint?: string;
  variants: {
    variant: string;
    leakage_checks?: Record<string, unknown>;
    adaptation?: unknown[];
    null_diagnostics?: Record<string, unknown>;
    methods: Method[];
    source_subjects: number;
    target_subjects: number;
    trials_retained: number;
    recordings_eligible: number;
  }[];
};
export default function EEGBenchmark() {
  const list =
    useResource<{ id: string; label: string; synthetic: boolean }[]>(
      "/eeg-benchmarks",
    );
  const [chosen, setChosen] = useState("demo-eeg-benchmark");
  const [variant, setVariant] = useState("primary");
  const report = useResource<Report>(
    `/eeg-benchmarks/${encodeURIComponent(chosen)}`,
  );
  const result = report.data?.variants?.find((v) => v.variant === variant);
  return (
    <Panel
      title="EEG decoding benchmark"
      eyebrow="HELD-OUT FITTING / HISTORICALLY REUSED DATA"
    >
      <div className="toolbar">
        <label>
          Benchmark receipt
          <select
            aria-label="Select EEG benchmark"
            value={chosen}
            onChange={(e) => setChosen(e.target.value)}
          >
            {(Array.isArray(list.data) ? list.data : []).map((item) => (
              <option key={item.id} value={item.id}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Prespecified analysis
          <select
            aria-label="EEG sensitivity"
            value={variant}
            onChange={(e) => setVariant(e.target.value)}
          >
            {report.data?.variants?.length ? (
              report.data.variants.map((v) => (
                <option key={v.variant}>{v.variant}</option>
              ))
            ) : (
              <option>primary</option>
            )}
          </select>
        </label>
      </div>
      <Async loading={report.loading} error={report.error}>
        {report.data && (
          <>
            <p className="badge">{report.data.status}</p>
            {report.data.warnings?.map((w) => (
              <Warning key={w}>{w}</Warning>
            ))}
            {report.data.protocol_fingerprint && (
              <details>
                <summary>Frozen benchmark protocol identity</summary>
                <code>{report.data.protocol_fingerprint}</code>
              </details>
            )}
            {result ? (
              <>
                <p>
                  {result.source_subjects} source subjects ·{" "}
                  {result.target_subjects} eligible target subjects ·{" "}
                  {result.recordings_eligible} recordings ·{" "}
                  {result.trials_retained} retained trials
                </p>
                <table
                  className="audit-table eeg-benchmark-table"
                  aria-label="EEG model performance"
                >
                  <thead>
                    <tr>
                      <th>Model</th>
                      <th>Evaluation</th>
                      <th>Subject mean balanced accuracy</th>
                      <th>95% subject bootstrap interval</th>
                      <th>Missing subjects</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.methods.map((m) => (
                      <tr key={m.mode + m.model}>
                        <td>{m.model}</td>
                        <td>{m.mode}</td>
                        <td>
                          {m.balanced_accuracy
                            ? `${(100 * m.balanced_accuracy.mean).toFixed(1)}%`
                            : "NOT AVAILABLE"}
                        </td>
                        <td>
                          {m.balanced_accuracy
                            ? `${(100 * m.balanced_accuracy.lower).toFixed(1)}–${(100 * m.balanced_accuracy.upper).toFixed(1)}% (N=${m.complete_subjects})`
                            : "NOT AVAILABLE"}
                        </td>
                        <td>{m.missing_subjects}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <details>
                  <summary>
                    Subject distributions (anonymous aggregate bins)
                  </summary>
                  {result.methods.map((m) => (
                    <div key={m.mode + m.model}>
                      <p>
                        {m.model} · {m.mode}
                      </p>
                      {m.subject_distribution?.map((n, i) => (
                        <label
                          key={i}
                          style={{ display: "inline-block", marginRight: 8 }}
                        >
                          {10 * i}–{10 * (i + 1)}%:{" "}
                          <meter
                            min={0}
                            max={m.complete_subjects || 1}
                            value={n}
                          />
                          {n}
                        </label>
                      ))}
                    </div>
                  ))}
                </details>
                <details>
                  <summary>
                    Leakage checks and separate adaptation/null diagnostics
                  </summary>
                  <pre>
                    {JSON.stringify(
                      {
                        leakage_checks: result.leakage_checks,
                        adaptation: result.adaptation,
                        null_diagnostics: result.null_diagnostics,
                      },
                      null,
                      2,
                    )}
                  </pre>
                </details>
                <Warning>
                  Intervals resample subjects, conditional on fitted source
                  models. Sensitivities are not independent primary findings.
                  Target-labeled adaptation is separate from zero-shot transfer.
                </Warning>
              </>
            ) : (
              <p>
                No configured completed aggregate benchmark. Protocol preview
                only; no performance or human inference is invented.
              </p>
            )}
          </>
        )}
      </Async>
    </Panel>
  );
}
