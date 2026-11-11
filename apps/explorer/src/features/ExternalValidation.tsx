import { useState } from "react";
import { Async, Panel, Warning, useResource } from "../components/Common";
type Report = {
  schema: string;
  status: string;
  dataset: string;
  release_id: string;
  synthetic_only: boolean;
  mode: string;
  scientific_compatibility: string;
  acquisition_status: string;
  human_external_subjects: number;
  human_external_sessions: number;
  human_external_trials: number;
  performance: unknown[];
  domain_shift: unknown;
  blockers: string[];
  refitted_components: number;
};
export default function ExternalValidation() {
  const choices = useResource<{ id: string; label: string }[]>(
    "/external-validations",
  );
  const [id, setId] = useState("demo-external-validation");
  const report = useResource<Report>(
    `/external-validations/${encodeURIComponent(id)}`,
  );
  const d =
    report.data?.schema === "soma.external-validation/1"
      ? report.data
      : undefined;
  return (
    <Panel
      title="Frozen external EEG validation"
      eyebrow="ACQUISITION / HARMONIZATION / INDEPENDENT COHORT"
    >
      <label>
        Validation receipt
        <select
          aria-label="Select external validation"
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
            <p className="badge">External validation: {d.status}</p>
            <p>
              Dataset: {d.dataset} · Mode: {d.mode}
            </p>
            <p>Authentic source release: {d.release_id}</p>
            <p>Acquisition approval: {d.acquisition_status}</p>
            <p>
              Scientific feature compatibility: {d.scientific_compatibility}
            </p>
            <p>
              Human external coverage: {d.human_external_subjects} subjects ·{" "}
              {d.human_external_sessions} sessions · {d.human_external_trials}{" "}
              trials
            </p>
            <p>Refitted components: {d.refitted_components}</p>
            <Warning>
              {d.synthetic_only
                ? "SYNTHETIC TEST ONLY: these scores are not human external validation."
                : "No external human accuracy is available while acquisition or compatibility is blocked."}
            </Warning>
            {d.blockers.map((b) => (
              <Warning key={b}>{b}</Warning>
            ))}
            <details>
              <summary>Observable domain shift</summary>
              <pre>{JSON.stringify(d.domain_shift, null, 2)}</pre>
            </details>
            {d.performance.length > 0 && (
              <details>
                <summary>
                  {d.synthetic_only
                    ? "Fictional numerical outcomes"
                    : "External descriptive outcomes"}
                </summary>
                <pre>{JSON.stringify(d.performance, null, 2)}</pre>
              </details>
            )}
          </>
        )}
      </Async>
    </Panel>
  );
}
