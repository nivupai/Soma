import { Panel, Warning } from "../components/Common";
export type Readiness = {
  status: string;
  bundle_integrity: string;
  interpretation: string;
  gates: {
    name: string;
    status: string;
    reasons: string[];
    evidence: string[];
  }[];
};
export default function ReadinessGates({ value }: { value: Readiness }) {
  return (
    <Panel
      title="Scientific readiness gates"
      eyebrow="LIVE EVIDENCE REQUIRED BEFORE NEW USE"
    >
      <Warning>
        Readiness does not establish consent, suitable statistical inference or
        longitudinal reliability. A blocked requirement always prevents an
        overall ready result.
      </Warning>
      <p>
        Recorded readiness: <strong>{value.status}</strong> · Bundle
        integrity/review: {value.bundle_integrity}
      </p>
      <p>{value.interpretation}</p>
      <table
        className="audit-table"
        aria-label="Scientific readiness requirements"
      >
        <thead>
          <tr>
            <th>Requirement</th>
            <th>Evidence state</th>
            <th>Reason / next evidence</th>
          </tr>
        </thead>
        <tbody>
          {value.gates.map((g, i) => (
            <tr key={i}>
              <td style={{ overflowWrap: "anywhere", maxWidth: "18rem" }}>
                {g.name}
              </td>
              <td>
                <span className="badge">{g.status}</span>
              </td>
              <td>{g.reasons.join("; ")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}
