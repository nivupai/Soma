import { useState } from "react";
import { Async, Panel, Warning, useResource } from "../components/Common";
type Report = {
  schema?: string;
  status: string;
  source_dataset?: string;
  target_dataset?: string;
  mode?: string;
  split?: string;
  license?: string;
  permission_status?: string;
  local_data?: string;
  observed_subjects?: number;
  observed_sessions?: number;
  observed_trials?: number;
  model_compatibility?: unknown;
  domain_shift?: unknown;
  warnings?: string[];
  blockers?: string[];
  performance?: {
    model: string;
    planned_subjects: number;
    missing_subjects: number;
    balanced_accuracy: { mean: number; lower: number; upper: number } | null;
  }[];
};
export default function ExternalEEG() {
  const choices = useResource<{ id: string; label: string }[]>("/external-eeg");
  const [id, setId] = useState("demo-external-eeg");
  const report = useResource<Report>(`/external-eeg/${encodeURIComponent(id)}`);
  const d = report.data?.schema?.startsWith("soma.external-eeg.")
    ? report.data
    : undefined;
  return (
    <Panel
      title="External EEG replication"
      eyebrow="PERMISSION / FROZEN MODEL FIDELITY"
    >
      <label>
        External evidence
        <select
          aria-label="Select external EEG receipt"
          value={id}
          onChange={(e) => setId(e.target.value)}
        >
          {(Array.isArray(choices.data) ? choices.data : []).map((c) => (
            <option key={c.id} value={c.id}>
              {c.label}
            </option>
          ))}
        </select>
      </label>
      <Async loading={report.loading} error={report.error}>
        {d && (
          <>
            <p className="badge">External audit: {d.status}</p>
            <p>
              {d.source_dataset ?? "Source-role fit"} →{" "}
              {d.target_dataset ?? "External dataset"}
            </p>
            <p>
              Mode:{" "}
              {d.mode ?? "Exact / harmonized / refitted feasibility audit"} ·
              Split: {d.split ?? "NOT EXECUTED"}
            </p>
            <p>
              License: {d.license ?? "See configured evidence"} · Permission:{" "}
              {d.permission_status ?? "See verified receipt"}
            </p>
            <p>
              Observed human coverage: {d.observed_subjects ?? 0} subjects ·{" "}
              {d.observed_sessions ?? 0} sessions · {d.observed_trials ?? 0}{" "}
              trials
            </p>
            {(d.warnings ?? []).map((w) => (
              <Warning key={w}>{w}</Warning>
            ))}
            {(d.blockers ?? []).map((w) => (
              <Warning key={w}>{w}</Warning>
            ))}
            <details>
              <summary>Model and feature compatibility</summary>
              <pre>{JSON.stringify(d.model_compatibility ?? {}, null, 2)}</pre>
            </details>
            <details>
              <summary>Domain shift and measurement differences</summary>
              <pre>{JSON.stringify(d.domain_shift ?? {}, null, 2)}</pre>
            </details>
            {d.performance?.length ? (
              <table
                className="eeg-benchmark-table"
                aria-label="External EEG performance"
              >
                <thead>
                  <tr>
                    <th>Method</th>
                    <th>Subject mean BA</th>
                    <th>95% subject interval</th>
                    <th>Missing / planned</th>
                  </tr>
                </thead>
                <tbody>
                  {d.performance.map((r) => (
                    <tr key={r.model}>
                      <td>{r.model}</td>
                      <td>
                        {r.balanced_accuracy
                          ? `${(100 * r.balanced_accuracy.mean).toFixed(1)}%`
                          : "NOT AVAILABLE"}
                      </td>
                      <td>
                        {r.balanced_accuracy
                          ? `${(100 * r.balanced_accuracy.lower).toFixed(1)}–${(100 * r.balanced_accuracy.upper).toFixed(1)}%`
                          : "NOT AVAILABLE"}
                      </td>
                      <td>
                        {r.missing_subjects} / {r.planned_subjects}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <Warning>
                No human external decoding outcomes. A blocked audit is not a
                completed replication.
              </Warning>
            )}
            <Warning>
              Refitting is distinct from unchanged-model transfer. No data
              download, model fit or permission override executes from this
              view.
            </Warning>
          </>
        )}
      </Async>
    </Panel>
  );
}
