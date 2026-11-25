import type { Readiness } from "../api/client";

const DESCRIPTION: Record<Readiness, string> = {
  VALIDATED:
    "Conductor boundaries independently validated against anatomical references.",
  QC_ONLY: "Computational QC passed; no independent anatomical ground truth.",
  NOT_READY: "Not ready for a forward model or anatomical interpretation.",
};

function yesNo(value: boolean | null): string {
  return value === null ? "NOT ASSESSED" : value ? "YES" : "NO";
}

/**
 * Prominent head readiness label. Geometric validity and anatomical validation
 * are shown as separate facts; neither is inferred from the other.
 */
export default function ReadinessBanner({
  readiness,
  geometricallyValid,
  anatomicallyValidated,
  reasons = [],
  subject = "Head model",
}: {
  readiness: Readiness;
  geometricallyValid: boolean | null;
  anatomicallyValidated: boolean;
  reasons?: string[];
  subject?: string;
}) {
  // An anatomical-validation claim without VALIDATED readiness is never shown.
  const anatomical = anatomicallyValidated && readiness === "VALIDATED";
  return (
    <section
      className={`readiness-banner readiness-${readiness.toLowerCase()}`}
      aria-label={`${subject} readiness`}
      data-readiness={readiness}
    >
      <div className="readiness-label">
        <span className="eyebrow">{subject} readiness</span>
        <strong>{readiness}</strong>
        <span>{DESCRIPTION[readiness]}</span>
      </div>
      <dl className="readiness-facts">
        <dt>Geometrically valid</dt>
        <dd>{yesNo(geometricallyValid)}</dd>
        <dt>Anatomically validated</dt>
        <dd>{anatomical ? "YES" : "NO"}</dd>
      </dl>
      <p className="readiness-note">
        Geometric validity (closed, nested, finite surfaces) does not establish
        anatomical validity.
        {reasons.length > 0 && <> Limitations: {reasons.join("; ")}.</>}
      </p>
    </section>
  );
}
