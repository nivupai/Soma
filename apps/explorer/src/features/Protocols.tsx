import { useState } from "react";
import { Async, Json, Panel, Warning, useResource } from "../components/Common";
import { Diagram, type WorkflowGraph } from "./Workflows";

type Item = { id: string; label: string; status: string; sequence?: number };
export type DriftRow = {
  unit_id: string;
  maximum_absolute_error: number;
  numerically_equivalent: boolean | null;
  equivalence_applicable: boolean;
  axes: string[];
  units: string[];
  left_values: number[];
  right_values: number[];
  atol: number;
  rtol: number;
};
type Comparison = {
  status: string;
  authorized: boolean;
  reasons: string[];
  numerical_comparisons: DriftRow[];
  drift: { category: string; observed: unknown }[];
  numerically_identical: boolean | null;
  numerically_equivalent: boolean | null;
  numerical_equivalence_applicable: boolean;
  artifact_byte_identical: boolean;
  unit_counts: { left: number; right: number; added: number; removed: number };
  protocol_comparison: { scientific_change: boolean };
  [key: string]: unknown;
};
export function DriftPlot({ rows }: { rows: DriftRow[] }) {
  if (!rows.length)
    return (
      <p>
        No aligned completed outcomes. Numerical equivalence is indeterminate.
      </p>
    );
  const components = rows.flatMap((r) =>
    r.axes.map((axis, i) => {
      const bound = r.atol + r.rtol * Math.abs(r.right_values[i]);
      const error = Math.abs(r.left_values[i] - r.right_values[i]);
      return {
        label: `${r.unit_id} / ${axis} (${r.units[i]})`,
        ratio: bound > 0 ? error / bound : error === 0 ? 0 : Infinity,
        applicable: r.equivalence_applicable,
      };
    }),
  );
  const maximum = Math.max(
    1,
    ...components.filter((c) => Number.isFinite(c.ratio)).map((c) => c.ratio),
  );
  return (
    <figure>
      <div style={{ maxHeight: 500, overflow: "auto" }}>
        <svg
          viewBox={`0 0 750 ${components.length * 28 + 25}`}
          role="img"
          aria-label="Selected summary absolute drift"
        >
          {components.map((c, i) => (
            <g
              key={`${c.label}-${i}`}
              transform={`translate(0,${i * 28 + 16})`}
            >
              <text x="0" fill="currentColor" fontSize="10">
                {c.label}
              </text>
              <rect
                x="360"
                y="-12"
                width={Math.max(
                  1,
                  (280 * (Number.isFinite(c.ratio) ? c.ratio : maximum)) /
                    maximum,
                )}
                height="12"
                fill={c.applicable && c.ratio <= 1 ? "#46bca0" : "#dfa54e"}
              />
              <text x="655" fill="currentColor" fontSize="11">
                {Number.isFinite(c.ratio) ? c.ratio.toExponential(2) : "∞"}
              </text>
            </g>
          ))}
        </svg>
      </div>
      <figcaption>
        Absolute error divided by each axis's frozen absolute + relative bound
        (dimensionless). A ratio above 1 exceeds that bound. Under changed
        inputs or methods this is a descriptive scale only; equivalence is
        inapplicable. This is not a significance test.
      </figcaption>
    </figure>
  );
}
export function ComparisonSummary({ value }: { value: Comparison }) {
  return (
    <>
      <table>
        <thead>
          <tr>
            <th>Evidence</th>
            <th>Observation</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Scientific methods and estimand</td>
            <td>
              {value.protocol_comparison.scientific_change
                ? "CHANGED — amendment required"
                : "FIXED"}
            </td>
          </tr>
          <tr>
            <td>Scheduled units</td>
            <td>
              {value.unit_counts.left} → {value.unit_counts.right}; added{" "}
              {value.unit_counts.added}, removed {value.unit_counts.removed}
            </td>
          </tr>
          <tr>
            <td>Output file bytes identical</td>
            <td>{String(value.artifact_byte_identical)}</td>
          </tr>
          <tr>
            <td>Selected numbers identical</td>
            <td>
              {value.numerically_identical === null
                ? "INAPPLICABLE / INDETERMINATE"
                : String(value.numerically_identical)}
            </td>
          </tr>
          <tr>
            <td>Selected numbers within frozen bounds</td>
            <td>
              {value.numerical_equivalence_applicable
                ? String(value.numerically_equivalent)
                : "INAPPLICABLE / INDETERMINATE"}
            </td>
          </tr>
        </tbody>
      </table>
      <p>
        {value.reasons.length
          ? value.reasons.join("; ")
          : "No replay authorization deviations detected within the declared evidence scope."}
      </p>
      <table>
        <thead>
          <tr>
            <th>Observed drift</th>
            <th>Evidence</th>
          </tr>
        </thead>
        <tbody>
          {value.drift.map((d) => (
            <tr key={d.category}>
              <td>{d.category.replaceAll("_", " ")}</td>
              <td>
                <Json value={d.observed} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function Evidence({ identity }: { identity: string }) {
  const record = useResource<{
    snapshot: { id: string };
    sequence: number;
    status: string;
    mode: string;
    members: { status: string }[];
    deviations: unknown[];
  }>(identity ? `/replays/${identity}` : null);
  const lineage = useResource<WorkflowGraph>(
    identity ? `/replays/${identity}/lineage/0` : null,
  );
  return (
    <>
      <Async loading={record.loading} error={record.error}>
        {record.data && (
          <>
            <dl>
              <dt>Snapshot</dt>
              <dd>{record.data.snapshot.id}</dd>
              <dt>Sequence / mode</dt>
              <dd>
                {record.data.sequence} / {record.data.mode}
              </dd>
              <dt>Completion</dt>
              <dd>{record.data.status}</dd>
              <dt>Unit status</dt>
              <dd>{record.data.members.map((m) => m.status).join(", ")}</dd>
              <dt>Deviations</dt>
              <dd>{record.data.deviations.length}</dd>
            </dl>
            <details>
              <summary>Full QC and conformance record</summary>
              <Json value={record.data} />
            </details>
          </>
        )}
      </Async>
      <details>
        <summary>Upstream / downstream lineage</summary>
        <Async loading={lineage.loading} error={lineage.error}>
          {lineage.data && <Diagram graph={lineage.data} />}
        </Async>
      </details>
    </>
  );
}
export default function Protocols() {
  const list = useResource<Item[]>("/protocols");
  const runs = useResource<Item[]>("/replays");
  const [chosen, setChosen] = useState("");
  const [revision, setRevision] = useState("");
  const [left, setLeft] = useState("");
  const [right, setRight] = useState("");
  const [mode, setMode] = useState("EXACT");
  const id = chosen || list.data?.[0]?.id || "";
  const seal = useResource<Record<string, unknown>>(
    id ? `/protocols/${id}` : null,
  );
  const versions = useResource<Record<string, unknown>>(
    id && revision
      ? `/protocol-comparison?left=${encodeURIComponent(id)}&right=${encodeURIComponent(revision)}`
      : null,
  );
  const comparison = useResource<Comparison>(
    left && right
      ? `/replay-comparison?left=${encodeURIComponent(left)}&right=${encodeURIComponent(right)}&mode=${mode}`
      : null,
  );
  return (
    <>
      <Warning>
        Local seals are not external preregistration. All current replay
        adapters are synthetic and descriptive. Repeated runs do not establish a
        human longitudinal study or biological drift.
      </Warning>
      <Panel title="Research protocols" eyebrow="FROZEN METHODS / READ ONLY">
        <Async loading={list.loading} error={list.error}>
          <label>
            Protocol{" "}
            <select
              aria-label="Select protocol"
              value={id}
              onChange={(e) => setChosen(e.target.value)}
            >
              {list.data?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </select>
          </label>
        </Async>
        <p className="badge">LOCAL SEAL · NOT PREREGISTERED</p>
        <details>
          <summary>Sealed protocol and validation receipt</summary>
          <Async loading={seal.loading} error={seal.error}>
            <Json value={seal.data} />
          </Async>
        </details>
        <label>
          Compare version{" "}
          <select
            aria-label="Compare protocol version"
            value={revision}
            onChange={(e) => setRevision(e.target.value)}
          >
            <option value="">Select registered revision</option>
            {list.data?.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>
        </label>
        <Async loading={versions.loading} error={versions.error}>
          {versions.data && (
            <div role="region" aria-label="Protocol version comparison">
              <Json value={versions.data} />
            </div>
          )}
        </Async>
      </Panel>
      <Panel
        title="Execution history and comparison"
        eyebrow="EXPLICIT SEQUENCE / RECORDED EVIDENCE"
      >
        <Async loading={runs.loading} error={runs.error}>
          {!runs.data?.length && (
            <p>
              No registered execution history. Preparing a history is an
              explicit operator action; this page never runs workflows.
            </p>
          )}
          <div className="toolbar">
            {(["Left execution", "Right execution"] as const).map(
              (label, i) => (
                <label key={label}>
                  {label}
                  <select
                    aria-label={label}
                    value={i ? right : left}
                    onChange={(e) => (i ? setRight : setLeft)(e.target.value)}
                  >
                    <option value="">Select execution</option>
                    {runs.data?.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.label} · sequence {r.sequence} · {r.status}
                      </option>
                    ))}
                  </select>
                </label>
              ),
            )}
            <label>
              Replay mode
              <select
                aria-label="Replay mode"
                value={mode}
                onChange={(e) => setMode(e.target.value)}
              >
                {["EXACT", "CONTROLLED", "EXPLORATORY"].map((m) => (
                  <option key={m}>{m}</option>
                ))}
              </select>
            </label>
          </div>
        </Async>
        <Async loading={comparison.loading} error={comparison.error}>
          {comparison.data && (
            <>
              <h3 data-testid="replay-status">{comparison.data.status}</h3>
              <Warning>
                Authorization: {String(comparison.data.authorized)}.
                Confirmatory replication and cache interchange remain
                unauthorized.
              </Warning>
              <ComparisonSummary value={comparison.data} />
              <DriftPlot rows={comparison.data.numerical_comparisons || []} />
              <details open>
                <summary>
                  Changed, fixed, comparable and indeterminate evidence
                </summary>
                <Json value={comparison.data} />
              </details>
            </>
          )}
        </Async>
      </Panel>
      {(left || right) && (
        <div className="two-col">
          <Panel
            title="Left execution"
            eyebrow="SNAPSHOT / QC / CONFORMANCE / DEVIATIONS"
          >
            <Evidence identity={left} />
          </Panel>
          <Panel
            title="Right execution"
            eyebrow="SNAPSHOT / QC / CONFORMANCE / DEVIATIONS"
          >
            <Evidence identity={right} />
          </Panel>
        </div>
      )}
    </>
  );
}
