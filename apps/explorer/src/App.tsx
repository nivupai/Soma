import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useReducer,
  useState,
} from "react";
import {
  Activity,
  ArrowUpRight,
  Box,
  BrainCircuit,
  ChevronRight,
  Database,
  FlaskConical,
  LayoutDashboard,
  Layers,
  Microscope,
  Moon,
  Settings,
  ShieldCheck,
  Sun,
  Workflow,
} from "lucide-react";
import {
  type Catalog,
  type Result,
  type Dataset,
  type EEGWindow,
} from "./api/client";
import { initial, reducer, type Page } from "./state";
import {
  Async,
  Json,
  Panel,
  Trace,
  useResource,
  Warning,
} from "./components/Common";
import EEG from "./features/EEG";
import MRI from "./features/MRI";
const Source = lazy(() => import("./features/Source"));
import FMRI from "./features/FMRI";
import Workbench from "./features/Workbench";
const pages: [Page, typeof Activity][] = [
  ["Overview", LayoutDashboard],
  ["Datasets", Database],
  ["EEG Laboratory", Activity],
  ["MRI Anatomy", Layers],
  ["Source Models", BrainCircuit],
  ["fMRI Laboratory", Box],
  ["Experiments", FlaskConical],
  ["Validation", ShieldCheck],
  ["Settings", Settings],
];
const descriptions: Record<Page, string> = {
  Overview: "A workspace for reproducible neuroscience.",
  Datasets: "Inspect registered recordings and their scientific context.",
  "EEG Laboratory": "From continuous signals to oscillatory dynamics.",
  "MRI Anatomy": "Explore anatomy in physical space.",
  "Source Models": "Inspect geometry, currents and model evidence.",
  "fMRI Laboratory": "Task models, effect maps and calibrated interpretation.",
  Experiments: "Trace every result back to its scientific definition.",
  Validation: "Evidence, limitations and anatomical readiness.",
  Settings: "Local preferences and data boundaries.",
};
function Overview({
  catalog,
  navigate,
}: {
  catalog: Catalog | null;
  navigate: (p: Page) => void;
}) {
  const eeg = useResource<Result<EEGWindow>>(
    "/eeg/demo-eeg/window?channels=C3&duration_s=10",
  );
  return (
    <>
      <div className="hero">
        <div>
          <span className="eyebrow">SOMA / RESEARCH WORKSPACE</span>
          <h2>
            Follow the signal.
            <br />
            <em>Keep the evidence.</em>
          </h2>
          <p>
            Explore electrophysiology, anatomy and functional models
            <br />
            with scientific provenance in every view.
          </p>
          <button
            className="primary"
            onClick={() => navigate("EEG Laboratory")}
          >
            Open EEG laboratory <ArrowUpRight size={16} />
          </button>
        </div>
        <div className="hero-art">
          <div className="orbital o1" />
          <div className="orbital o2" />
          <div className="orbital o3" />
          <BrainCircuit size={112} strokeWidth={0.75} />
          <span className="orbital-label">SIGNAL · SPACE · INFERENCE</span>
        </div>
      </div>
      <div className="metrics">
        <div>
          <span>Registered resources</span>
          <strong>{catalog?.datasets.length || "—"}</strong>
        </div>
        <div>
          <span>Demo modalities</span>
          <strong>
            04<small> deterministic</small>
          </strong>
        </div>
        <div>
          <span>Inference policy</span>
          <strong>
            14.1<small> enforced</small>
          </strong>
        </div>
        <div>
          <span>Execution</span>
          <strong>
            Local<small> no telemetry</small>
          </strong>
        </div>
      </div>
      <div className="two-col">
        <Panel
          title="Signal preview"
          eyebrow="SYNTHETIC EEG / C3 · 160 Hz"
          actions={
            <button
              className="text-button"
              onClick={() => navigate("EEG Laboratory")}
            >
              Inspect <ArrowUpRight size={14} />
            </button>
          }
        >
          <Async loading={eeg.loading} error={eeg.error}>
            {eeg.data && (
              <Trace
                x={eeg.data.data.times_s}
                y={eeg.data.data.values_V[0].map((v) => v * 1e6)}
                label="Synthetic C3 EEG overview"
              />
            )}
          </Async>
          <p className="plot-caption">
            Amplitude µV · time s · deterministic seed15042
          </p>
        </Panel>
        <Panel
          title="Scientific readiness"
          eyebrow="INTERPRETATION / CURRENT BOUNDARIES"
        >
          <div className="readiness-row">
            <span className="status-dot" />
            Synthetic numerical viewers
            <span className="status-text">AVAILABLE</span>
          </div>
          <div className="readiness-row">
            <span className="status-dot amber" />
            Human fMRI preprocessing
            <span className="status-text amber-text">UNAVAILABLE</span>
          </div>
          <div className="readiness-row">
            <span className="status-dot amber" />
            Human confirmatory inference
            <span className="status-text amber-text">RESTRICTED</span>
          </div>
          <Warning>
            Numerical validation is not anatomical or clinical validation.
          </Warning>
        </Panel>
      </div>
      <Panel
        title="Research laboratories"
        eyebrow="EXPLORE / FOUR CONNECTED MODALITIES"
      >
        <div className="lab-grid">
          {[pages[2], pages[3], pages[4], pages[5]].map(([name, Icon]) => (
            <button
              className="lab-card"
              key={name}
              onClick={() => navigate(name)}
            >
              <Icon size={25} />
              <h3>{name}</h3>
              <p>{descriptions[name]}</p>
              <ArrowUpRight size={17} />
            </button>
          ))}
        </div>
      </Panel>
    </>
  );
}
export default function App() {
  const [state, dispatch] = useReducer(reducer, initial);
  const [theme, setTheme] = useState(
    () => localStorage.getItem("soma-theme") || "dark",
  );
  const [inspector, setInspector] = useState(true);
  const [evidence, setEvidence] = useState<Result<unknown> | null>(null);
  const catalog = useResource<Catalog>("/catalog");
  const qc = useResource<Record<string, unknown>>(
    state.page === "Validation" ? "/qc" : null,
  );
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("soma-theme", theme);
  }, [theme]);
  const navigate = useCallback((page: Page) => {
    dispatch({ type: "page", page });
    setEvidence(null);
  }, []);
  const kind =
    state.page === "EEG Laboratory"
      ? "eeg"
      : state.page === "MRI Anatomy"
        ? "mri"
        : state.page === "Source Models"
          ? "source"
          : state.page === "fMRI Laboratory"
            ? "fmri"
            : "";
  const available =
    catalog.data?.datasets.filter(
      (d) =>
        (state.mode === "demo"
          ? d.id.startsWith("demo-")
          : !d.id.startsWith("demo-")) && d.kind === kind,
    ) || [];
  const id = available.some((d) => d.id === state.dataset)
    ? state.dataset
    : available[0]?.id || "";
  const dataset = available.find((d) => d.id === id);
  const report = useCallback((r: Result<unknown> | null) => setEvidence(r), []);
  function selectDataset(id: string) {
    dispatch({ type: "dataset", id });
    setEvidence(null);
  }
  const viewerProps = { id, state, dispatch, onResult: report };
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            navigate("Overview");
          }}
        >
          <div className="brand-mark">
            <Workflow size={24} />
          </div>
          <span>
            soma<small>RESEARCH EXPLORER</small>
          </span>
        </a>
        <div className="workspace-label">
          WORKSPACE <span>LOCAL</span>
        </div>
        <nav aria-label="Main navigation">
          {pages.map(([name, Icon], i) => (
            <button
              key={name}
              aria-label={name}
              className={`${state.page === name ? "active" : ""} ${i === 6 ? "nav-divider" : ""}`}
              onClick={() => navigate(name)}
            >
              <Icon size={18} />
              <span>{name}</span>
              {state.page === name && <ChevronRight size={14} />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="local-state">
            <span className="status-dot" />
            <div>
              Local research instance<small>Bound to localhost · private</small>
            </div>
          </div>
          <div className="version">
            <span>SOMA v{catalog.data?.version || "0.15.0"}</span>
            <Microscope size={15} />
          </div>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="breadcrumbs">
            <span>Workspace</span>
            <ChevronRight size={12} />
            <strong>{state.page}</strong>
          </div>
          <span className="spacer" />
          <div className="mode-switch" role="group" aria-label="Data mode">
            <button
              className={state.mode === "demo" ? "selected" : ""}
              onClick={() => {
                dispatch({ type: "mode", mode: "demo" });
                setEvidence(null);
              }}
            >
              Synthetic demo
            </button>
            <button
              className={state.mode === "local" ? "selected" : ""}
              onClick={() => {
                dispatch({ type: "mode", mode: "local" });
                setEvidence(null);
              }}
            >
              Local data
            </button>
          </div>
          <button
            className="icon-button"
            aria-label="Toggle theme"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          >
            {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
          </button>
          <button
            className="icon-button"
            aria-label="Toggle inspector"
            aria-pressed={inspector}
            onClick={() => setInspector(!inspector)}
          >
            <PanelIcon />
          </button>
        </header>
        <div className="workspace-body">
          <main>
            <div className="page-heading">
              <div>
                <span className="eyebrow">
                  {state.mode === "demo"
                    ? "SYNTHETIC DEMONSTRATION"
                    : "CONFIGURED LOCAL RESOURCES"}
                </span>
                <h1>{state.page}</h1>
                <p>{descriptions[state.page]}</p>
              </div>
              {kind && (
                <div className="dataset-select">
                  <label>
                    Dataset / subject / session
                    <select
                      aria-label="Dataset selection"
                      value={id}
                      onChange={(e) => selectDataset(e.target.value)}
                    >
                      {available.map((d) => (
                        <option value={d.id} key={d.id}>
                          {d.label} · {d.subjects.join(",")} /{" "}
                          {d.sessions.join(",")}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              )}
            </div>
            <Async loading={catalog.loading} error={catalog.error}>
              {state.page === "Overview" && (
                <Overview catalog={catalog.data} navigate={navigate} />
              )}
              {state.page === "Datasets" && (
                <Panel
                  title="Registered scientific resources"
                  eyebrow="ALLOWLISTED / METADATA"
                >
                  <p className="muted">
                    Only operator-configured local files are exposed. Browser
                    requests use opaque identities, never filesystem paths.
                  </p>
                  <div className="dataset-grid">
                    {catalog.data?.datasets
                      .filter((d) =>
                        state.mode === "demo"
                          ? d.id.startsWith("demo-")
                          : !d.id.startsWith("demo-"),
                      )
                      .map((d) => (
                        <DatasetCard
                          key={d.id}
                          dataset={d}
                          onSelect={() => {
                            navigate(
                              d.kind === "eeg"
                                ? "EEG Laboratory"
                                : d.kind === "mri"
                                  ? "MRI Anatomy"
                                  : d.kind === "source"
                                    ? "Source Models"
                                    : d.kind === "fmri"
                                      ? "fMRI Laboratory"
                                      : "Experiments",
                            );
                            selectDataset(d.id);
                          }}
                        />
                      ))}
                  </div>
                </Panel>
              )}
              {kind && !id && (
                <div className="empty">
                  <Database size={32} />
                  <h2>No configured {kind} resources</h2>
                  <p>
                    Add an explicit local allowlist configuration on the server,
                    or select Synthetic demo.
                  </p>
                  <p>Unavailable data are not successful analyses.</p>
                </div>
              )}
              {id && state.page === "EEG Laboratory" && (
                <EEG key={id} {...viewerProps} />
              )}
              {id && state.page === "MRI Anatomy" && (
                <MRI key={id} {...viewerProps} />
              )}
              {id && state.page === "Source Models" && (
                <Suspense
                  fallback={<div className="loading">Loading 3D renderer…</div>}
                >
                  <Source key={id} {...viewerProps} />
                </Suspense>
              )}
              {id && state.page === "fMRI Laboratory" && (
                <FMRI key={id} {...viewerProps} />
              )}
              {state.page === "Experiments" && (
                <Workbench datasets={catalog.data?.datasets || []} />
              )}
              {state.page === "Validation" && (
                <>
                  <Warning>
                    Interpretation states describe the available evidence. No
                    Explorer view establishes clinical validity.
                  </Warning>
                  <Panel
                    title="Current scientific boundaries"
                    eyebrow="QC / EVIDENCE"
                  >
                    <Async loading={qc.loading} error={qc.error}>
                      <Json value={qc.data} />
                    </Async>
                  </Panel>
                  <Panel
                    title="Statistical calibration"
                    eyebrow="MILESTONE14.1 / RESTRICTIONS"
                  >
                    <p>
                      Default inference is descriptive. Feasible AR1/AR2 and
                      human confirmatory claims remain unsupported. BY or
                      Bonferroni correction cannot repair invalid marginal
                      probabilities.
                    </p>
                    <p className="muted">
                      Synthetic iid-OLS calibration does not generalize
                      automatically to human data, other designs, masks or
                      preprocessing definitions.
                    </p>
                  </Panel>
                </>
              )}
              {state.page === "Settings" && (
                <>
                  <Panel
                    title="Appearance & layout"
                    eyebrow="LOCAL PREFERENCES"
                  >
                    <div className="toolbar">
                      <button onClick={() => setTheme("dark")}>
                        Dark mode
                      </button>
                      <button onClick={() => setTheme("light")}>
                        Light mode
                      </button>
                      <button onClick={() => setInspector(!inspector)}>
                        Toggle inspector
                      </button>
                    </div>
                    <p className="muted">
                      Theme is stored in this browser. Dataset contents are
                      never stored in localStorage.
                    </p>
                  </Panel>
                  <Panel title="Data boundaries" eyebrow="PRIVACY / LOCAL ONLY">
                    <p>
                      Configure allowed roots and explicit opaque resource IDs
                      in an ignored server-side JSON file, selected with
                      SOMA_EXPLORER_CONFIG. No file upload, arbitrary path
                      endpoint, public hosting or shell execution is available.
                    </p>
                    <Warning>
                      No analytics or telemetry are configured. Patient images
                      and individual screenshots stay in ignored local output
                      directories.
                    </Warning>
                  </Panel>
                </>
              )}
            </Async>
            <footer className="workspace-footer">
              <span className="status-dot" />
              Soma scientific engine
              <span>
                Explicit units. Traceable provenance. Bounded computation.
              </span>
              <span className="spacer" />
              <span>LOCAL / OFFLINE CAPABLE</span>
            </footer>
          </main>
          {inspector && (
            <aside className="inspector" aria-label="Scientific inspector">
              <div className="inspector-head">
                <span className="eyebrow">CONTEXT INSPECTOR</span>
                <span className="status-dot" />
              </div>
              <h3>{dataset?.label || "Scientific context"}</h3>
              <span className="badge">
                {evidence
                  ? (evidence.synthetic ? "SYNTHETIC · " : "") +
                    evidence.state.replaceAll("_", " ")
                  : "NO RESULT SELECTED"}
              </span>
              <section>
                <h4>Identity</h4>
                <dl>
                  <dt>Resource</dt>
                  <dd>{evidence?.dataset_id || dataset?.id || "—"}</dd>
                  <dt>Subject</dt>
                  <dd>{dataset?.subjects.join(", ") || "—"}</dd>
                  <dt>Session</dt>
                  <dd>{dataset?.sessions.join(", ") || "—"}</dd>
                  <dt>Source</dt>
                  <dd>
                    {evidence?.synthetic
                      ? "Synthetic generator"
                      : state.mode === "local"
                        ? "Local allowlist"
                        : "Synthetic demonstration"}
                  </dd>
                </dl>
              </section>
              <section>
                <h4>Inference policy</h4>
                <p>Milestone 14.1</p>
                <span className="policy-line">
                  <ShieldCheck size={15} />
                  Confirmatory claims blocked
                </span>
                <p className="muted small">
                  Human and feasible AR results remain descriptive. No UI
                  override.
                </p>
              </section>
              <section>
                <h4>Scientific warnings</h4>
                {evidence?.warnings.map((w) => (
                  <Warning key={w}>{w}</Warning>
                )) || (
                  <p className="muted small">
                    Select a scientific result to inspect its limitations.
                  </p>
                )}
              </section>
              <section>
                <h4>Provenance</h4>
                {evidence ? (
                  <Json value={evidence.provenance} />
                ) : (
                  <p className="muted small">
                    Input checksums, generator and software version appear with
                    each loaded result.
                  </p>
                )}
              </section>
              <div className="inspector-note">
                <ShieldCheck size={17} />
                <span>
                  Numerical evidence
                  <br />
                  is not clinical validity.
                </span>
              </div>
            </aside>
          )}
        </div>
      </div>
    </div>
  );
}
function PanelIcon() {
  return (
    <svg
      width="17"
      height="17"
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
    >
      <rect x="2" y="3" width="16" height="14" rx="2" />
      <path d="M12 3v14" />
    </svg>
  );
}
function DatasetCard({
  dataset: d,
  onSelect,
}: {
  dataset: Dataset;
  onSelect: () => void;
}) {
  return (
    <button className="dataset-card" onClick={onSelect} disabled={!d.available}>
      <span className="eyebrow">
        {d.kind} / {d.synthetic ? "SYNTHETIC" : "LOCAL"}
      </span>
      <h3>{d.label}</h3>
      <p>
        {d.subjects.join(", ")} · {d.sessions.join(", ")}
      </p>
      <span className="badge">{d.state.replaceAll("_", " ")}</span>
      <ArrowUpRight size={18} />
    </button>
  );
}
