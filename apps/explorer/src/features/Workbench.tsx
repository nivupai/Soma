import EEGBenchmark from "./EEGBenchmark";
import { useEffect, useState } from "react";
import { Download, FlaskConical } from "lucide-react";
import { api, type Artifact, type Dataset, type Job } from "../api/client";
import { Panel, Json, Async, useResource, Warning } from "../components/Common";
export default function Workbench({ datasets }: { datasets: Dataset[] }) {
  const experiments = useResource<Artifact[]>("/experiments");
  const [filter, setFilter] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [comparison, setComparison] = useState<unknown>(null);
  const [error, setError] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const [recording, setRecording] = useState("demo-eeg");
  const [channel, setChannel] = useState("C3");
  useEffect(() => {
    if (!job || !["queued", "running"].includes(job.status)) return;
    const timer = setInterval(() => {
      api<Job>(`/jobs/${job.id}`)
        .then(setJob)
        .catch((e) => setError(e.message));
    }, 300);
    return () => clearInterval(timer);
  }, [job]);
  async function compare() {
    setError("");
    setComparison(null);
    try {
      setComparison(
        await api("/experiments/compare", {
          method: "POST",
          body: JSON.stringify({ ids: selected }),
        }),
      );
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function submit() {
    setError("");
    try {
      setJob(
        await api<Job>("/jobs", {
          method: "POST",
          body: JSON.stringify({
            dataset_id: recording,
            channel,
            start_s: 0,
            duration_s: 10,
          }),
        }),
      );
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <>
      <EEGBenchmark />
      <Panel
        title="Reproducible experiments"
        eyebrow="ARTIFACT BROWSER / READ ONLY"
        actions={
          <span className="unit">Historical artifacts are immutable</span>
        }
      >
        <div className="toolbar">
          <input
            aria-label="Filter experiments"
            placeholder="Filter dataset, version or metric…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
          <span className="spacer" />
          <button onClick={compare} disabled={selected.length < 2}>
            Compare selected ({selected.length})
          </button>
        </div>
        <Async loading={experiments.loading} error={experiments.error}>
          <div className="artifact-list">
            {experiments.data
              ?.filter((a) =>
                JSON.stringify(a).toLowerCase().includes(filter.toLowerCase()),
              )
              .map((a) => (
                <article key={a.id} className="artifact">
                  <div className="artifact-title">
                    <input
                      aria-label={`Compare ${a.title}`}
                      type="checkbox"
                      checked={selected.includes(a.id)}
                      onChange={() =>
                        setSelected(
                          selected.includes(a.id)
                            ? selected.filter((s) => s !== a.id)
                            : [...selected, a.id].slice(-4),
                        )
                      }
                    />
                    <FlaskConical size={18} />
                    <h3>{a.title}</h3>
                    <span className="badge">
                      {a.state.replaceAll("_", " ")}
                    </span>
                    <span className="unit">
                      {a.schema_version
                        ? `Schema ${a.schema_version}`
                        : "Legacy / unversioned"}
                    </span>
                    <span className="spacer" />
                    <a
                      className="button"
                      href={`/api/experiments/${a.id}/export?format=json`}
                      download
                    >
                      <Download size={13} /> JSON
                    </a>
                    <a
                      className="button"
                      href={`/api/experiments/${a.id}/export?format=csv`}
                      download
                    >
                      CSV
                    </a>
                  </div>
                  <p className="muted small">
                    {a.validation_status ?? "LEGACY_UNVERSIONED"} ·{" "}
                    {a.migration_status ?? "NOT_APPLIED"}
                  </p>
                  <div className="artifact-meta">
                    {Object.entries(a.compatibility).map(([k, v]) => (
                      <span key={k}>
                        {k}: {v}
                      </span>
                    ))}
                  </div>
                  <details>
                    <summary>Metrics, parameters & reproducibility</summary>
                    <Json
                      value={{
                        metrics: a.metrics,
                        parameters: a.parameters,
                        checksums: a.checksums,
                        schema: a.result_envelope,
                      }}
                    />
                  </details>
                  {a.figures.map((f, i) => (
                    <img
                      className="artifact-figure"
                      src={f}
                      key={f}
                      alt={`${a.title} figure ${i + 1}`}
                    />
                  ))}
                  {a.warnings.map((w) => (
                    <p className="muted small" key={w}>
                      {w}
                    </p>
                  ))}
                </article>
              ))}
          </div>
        </Async>
        {error && <Warning>{error}</Warning>}
        {comparison !== null && <Json value={comparison} />}
      </Panel>
      <Panel
        title="Local analysis queue"
        eyebrow="EXPLICIT SUBMISSION / ONE WORKER"
      >
        <p className="muted">
          Bounded 10-second native-sample EEG analysis. No arbitrary code, BEM,
          container or cohort execution. Cancel suppresses publication after a
          running numerical stage returns.
        </p>
        <div className="toolbar">
          <label>
            Recording
            <select
              aria-label="Job recording"
              value={recording}
              onChange={(e) => setRecording(e.target.value)}
            >
              {datasets
                .filter((d) => d.kind === "eeg")
                .map((d) => (
                  <option value={d.id} key={d.id}>
                    {d.label}
                  </option>
                ))}
            </select>
          </label>
          <label>
            Channel
            <input
              aria-label="Job channel"
              value={channel}
              onChange={(e) => setChannel(e.target.value)}
            />
          </label>
          <button className="primary" onClick={submit}>
            Submit EEG analysis
          </button>
        </div>
        {job && (
          <div className="job-status" role="status">
            <span>{job.status}</span>
            <progress max="1" value={job.progress} />
            {["queued", "running"].includes(job.status) && (
              <button
                onClick={() =>
                  api<Job>(`/jobs/${job.id}`, { method: "DELETE" }).then(setJob)
                }
              >
                Cancel job
              </button>
            )}
            {job.error && <Warning>{job.error}</Warning>}
            {job.manifest && (
              <details>
                <summary>Result manifest</summary>
                <Json value={job.manifest} />
              </details>
            )}
          </div>
        )}
      </Panel>
    </>
  );
}
