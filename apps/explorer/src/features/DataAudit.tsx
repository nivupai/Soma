import { useState } from "react";
import "./DataAudit.css";
import { Panel, Warning, Json, Async, useResource } from "../components/Common";
type Item = { id: string; label: string; synthetic: boolean };
export type AuditUnit = {
  participant_key: string;
  session: string | null;
  task: string;
  modality: string;
  status: string;
  permission: string;
  eligibility: string;
  missing_preprocessing: string;
  deviations: string[];
  lineage?: unknown;
};
type Audit = {
  dataset: string;
  status: string;
  synthetic: boolean;
  units: AuditUnit[];
  registration: unknown;
  warnings: string[];
};
export function UnitTable({ units }: { units: AuditUnit[] }) {
  return (
    <div style={{ overflowX: "auto" }}>
      <table className="audit-table" aria-label="Subject and session integrity">
        <thead>
          <tr>
            <th>Dataset-scoped participant</th>
            <th>Session</th>
            <th>Task / modality</th>
            <th>Use evidence</th>
            <th>Eligibility / execution</th>
          </tr>
        </thead>
        <tbody>
          {units.map((u, i) => (
            <tr key={i}>
              <td>{u.participant_key}</td>
              <td>{u.session ?? "NOT PROVIDED"}</td>
              <td>
                {u.task} / {u.modality}
              </td>
              <td>{u.permission}</td>
              <td>
                {u.eligibility} / {u.status}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export default function DataAudit({
  mode = "demo",
}: {
  mode?: "demo" | "local";
}) {
  const list = useResource<Item[]>("/human-audits");
  const [chosen, setChosen] = useState("");
  const available =
    list.data?.filter((item) => (mode === "demo") === item.synthetic) || [];
  const id = available.some((item) => item.id === chosen)
    ? chosen
    : available[0]?.id || "";
  const report = useResource<Audit>(
    id ? `/human-audits/${encodeURIComponent(id)}` : null,
  );
  return (
    <>
      <Warning>
        Access, use authorization, consent, identity consistency, protocol
        compliance and scientific validity are separate evidence. This interface
        never executes an analysis or contacts a registration provider.
      </Warning>
      <Panel
        title="Research data audit"
        eyebrow="LOCAL BOUNDARY / DATASET-SCOPED IDENTITY"
      >
        <Async loading={list.loading} error={list.error}>
          <label>
            Audit record{" "}
            <select
              aria-label="Select data audit"
              value={id}
              onChange={(e) => setChosen(e.target.value)}
            >
              {available.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
        </Async>
        <Async loading={report.loading} error={report.error}>
          {report.data && (
            <>
              <p className="badge">
                {report.data.synthetic
                  ? "SYNTHETIC · "
                  : "LOCAL HUMAN RECORD · "}
                {report.data.status}
              </p>
              <h3>{report.data.dataset}</h3>
              <UnitTable units={report.data.units} />
              {report.data.warnings.map((w) => (
                <Warning key={w}>{w}</Warning>
              ))}
            </>
          )}
        </Async>
      </Panel>
      {report.data && (
        <>
          <Panel
            title="Preprocessing and deviations"
            eyebrow="MISSING EVIDENCE / NO INFERENCE OVERRIDE"
          >
            {report.data.units.map((u, i) => (
              <details key={i}>
                <summary>
                  {u.session ?? "Session not provided"} · {u.status}
                </summary>
                <p>{u.missing_preprocessing}</p>
                <Json value={u.deviations} />
                {Boolean(u.lineage) && (
                  <details>
                    <summary>
                      Recorded workflow lineage and frozen parameters
                    </summary>
                    <Json value={u.lineage} />
                  </details>
                )}
              </details>
            ))}
          </Panel>
          <Panel
            title="External registration evidence"
            eyebrow="LOCAL SEAL ≠ EXTERNAL PREREGISTRATION"
          >
            <Json value={report.data.registration} />
            <p>
              Offline receipts are not automatically revalidated. No
              registration creates human confirmatory authorization.
            </p>
          </Panel>
        </>
      )}
    </>
  );
}
