import { useState } from "react";
import { Async, Panel, Warning, useResource } from "../components/Common";
type Report = {
  schema: string;
  status: string;
  release_id: string | null;
  protocol_fingerprint: string | null;
  training_cohort: string;
  models: string[];
  fitted_state: string;
  source_validation: unknown;
  external_acquisition: string;
  warnings: string[];
};
export default function ModelArchive() {
  const choices =
    useResource<{ id: string; label: string }[]>("/model-archives");
  const [id, setId] = useState("demo-model-archive");
  const report = useResource<Report>(
    `/model-archives/${encodeURIComponent(id)}`,
  );
  const d =
    report.data?.schema === "soma.model-release-summary/1"
      ? report.data
      : undefined;
  return (
    <Panel
      title="Prospective EEG model archive"
      eyebrow="FITTED STATE / VERIFIED RELOAD"
    >
      <label>
        Model release
        <select
          aria-label="Select model release"
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
            <p className="badge">Model archive: {d.status}</p>
            <p>Release: {d.release_id ?? "No human release selected"}</p>
            <p>Training cohort: {d.training_cohort}</p>
            <p>Protocol: {d.protocol_fingerprint ?? "Preview only"}</p>
            <p>Families: {d.models.join(", ")}</p>
            <p>Fitted state: {d.fitted_state}</p>
            <p>External acquisition: {d.external_acquisition}</p>
            <details>
              <summary>Feature and transfer compatibility</summary>
              <p>
                Sealed nine-channel source order, 160 Hz, volts, cue-relative
                1–3 s epochs and average reference before ROI selection.
                Matching dimensions alone do not establish comparability.
              </p>
              <p>
                Exact external transfer is not comparable. BNCI001 and Cho2017
                need reviewed reference, sampling and timing harmonization.
                BNCI004 lacks six required channels; interpolation is
                unsupported.
              </p>
              <p>
                Explicit acquisition approval and current dataset, protocol and
                permission evidence are required before human transfer
                inference.
              </p>
            </details>
            <details>
              <summary>Source validation and uncertainty</summary>
              <pre>{JSON.stringify(d.source_validation, null, 2)}</pre>
            </details>
            <Warning>
              No human external accuracy is available. Archived state integrity
              is not independent scientific validation.
            </Warning>
            {d.warnings.map((w) => (
              <Warning key={w}>{w}</Warning>
            ))}
          </>
        )}
      </Async>
    </Panel>
  );
}
