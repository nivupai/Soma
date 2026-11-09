import { useEffect } from "react";
import { Activity, ChevronLeft, ChevronRight } from "lucide-react";
import {
  query,
  type EEGMeta,
  type EEGWindow,
  type EEGAnalysis,
  type Result,
} from "../api/client";
import type { Selection, Action } from "../state";
import {
  useResource,
  Panel,
  Async,
  Evidence,
  Trace,
  Warning,
} from "../components/Common";
import { Heatmap } from "../components/Heatmap";
export default function EEG({
  id,
  state,
  dispatch,
  onResult,
}: {
  id: string;
  state: Selection;
  dispatch: (a: Action) => void;
  onResult: (r: Result<unknown> | null) => void;
}) {
  const meta = useResource<Result<EEGMeta>>(`/eeg/${id}/metadata`);
  const channels = state.channels.length
    ? state.channels
    : meta.data?.data.channels.slice(0, 3) || [];
  const window = useResource<Result<EEGWindow>>(
    channels.length
      ? `/eeg/${id}/window?${query({ channels: channels.join(","), start_s: state.start, duration_s: state.duration })}`
      : null,
  );
  const analysis = useResource<Result<EEGAnalysis>>(
    channels.length
      ? `/eeg/${id}/analysis?${query({ channel: channels[0], start_s: state.start, duration_s: state.duration })}`
      : null,
  );
  useEffect(() => {
    onResult(analysis.data || meta.data);
  }, [analysis.data, meta.data, onResult]);
  const m = meta.data?.data,
    a = analysis.data?.data,
    w = window.data?.data;
  function navigate(start: number, duration = state.duration) {
    dispatch({
      type: "window",
      start: Math.max(0, Math.min((m?.duration_s || 60) - duration, start)),
      duration,
    });
  }
  return (
    <>
      <Async loading={meta.loading} error={meta.error}>
        {m && (
          <div className="metrics">
            <div>
              <span>Sampling rate</span>
              <strong>
                {m.fs_hz}
                <small> Hz</small>
              </strong>
            </div>
            <div>
              <span>Recording length</span>
              <strong>
                {m.duration_s.toFixed(1)}
                <small> s</small>
              </strong>
            </div>
            <div>
              <span>Channels</span>
              <strong>
                {m.channels.length}
                <small> recorded</small>
              </strong>
            </div>
            <div>
              <span>Signal scale</span>
              <strong>
                µV<small> display · V analysis</small>
              </strong>
            </div>
          </div>
        )}
      </Async>
      <Panel
        title="Continuous recording"
        eyebrow="EEG / TIME DOMAIN"
        actions={
          <span className="muted inline">
            <Activity size={14} /> Live local data
          </span>
        }
      >
        <div className="toolbar">
          <button
            aria-label="Previous window"
            onClick={() => navigate(state.start - state.duration)}
          >
            <ChevronLeft size={15} />
          </button>
          <span className="mono">
            {state.start.toFixed(1)}—{(state.start + state.duration).toFixed(1)}{" "}
            s
          </span>
          <button
            aria-label="Next window"
            onClick={() => navigate(state.start + state.duration)}
          >
            <ChevronRight size={15} />
          </button>
          <label>
            Window
            <select
              aria-label="EEG window duration"
              value={state.duration}
              onChange={(e) => navigate(state.start, Number(e.target.value))}
            >
              {[2, 5, 10, 20, 30].map((v) => (
                <option key={v} value={v}>
                  {v} s
                </option>
              ))}
            </select>
          </label>
          <span className="spacer" />
          <span className="muted">Min/max envelope · display only</span>
        </div>
        <Async loading={window.loading} error={window.error}>
          {w && (
            <div className="eeg-traces">
              {w.channels.map((ch, i) => (
                <div className="channel" key={ch}>
                  <span className="channel-label">
                    {ch}
                    <small>µV</small>
                  </span>
                  <svg
                    aria-label={`${ch} EEG trace`}
                    role="img"
                    viewBox="0 0 900 100"
                  >
                    <defs>
                      <pattern
                        id={`eeg-${i}`}
                        width="90"
                        height="25"
                        patternUnits="userSpaceOnUse"
                      >
                        <path
                          d="M90 0H0V25"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth=".5"
                        />
                      </pattern>
                    </defs>
                    <rect
                      width="900"
                      height="100"
                      fill={`url(#eeg-${i})`}
                      opacity=".22"
                    />
                    {m?.events
                      .filter(
                        (e) =>
                          e.onset < state.start + state.duration &&
                          e.onset + e.duration > state.start,
                      )
                      .map((e) => (
                        <rect
                          key={e.onset}
                          x={(900 * (e.onset - state.start)) / state.duration}
                          y="0"
                          width={(900 * e.duration) / state.duration}
                          height="100"
                          fill="var(--amber)"
                          opacity=".08"
                        />
                      ))}
                    <path
                      d={
                        w.upper_V[i]
                          .map(
                            (v, j) =>
                              `${j ? "L" : "M"}${(900 * j) / Math.max(1, w.times_s.length - 1)},${50 - v * 1e6 * 1.3}`,
                          )
                          .join(" ") +
                        w.lower_V[i]
                          .map((_, k) => {
                            const j = w.times_s.length - 1 - k;
                            return `L${(900 * j) / Math.max(1, w.times_s.length - 1)},${50 - w.lower_V[i][j] * 1e6 * 1.3}`;
                          })
                          .join(" ") +
                        "Z"
                      }
                      fill="var(--cyan)"
                      opacity=".18"
                    />
                    <path
                      d={w.values_V[i]
                        .map(
                          (v, j) =>
                            `${j ? "L" : "M"}${(900 * j) / Math.max(1, w.times_s.length - 1)},${50 - v * 1e6 * 1.3}`,
                        )
                        .join(" ")}
                      fill="none"
                      stroke={
                        ["var(--cyan)", "var(--blue)", "var(--lavender)"][i % 3]
                      }
                      strokeWidth="1"
                      vectorEffect="non-scaling-stroke"
                    />
                    <text x="5" y="17.5">
                      +25 µV
                    </text>
                    <text x="5" y="82.5">
                      −25 µV
                    </text>
                  </svg>
                </div>
              ))}
            </div>
          )}
        </Async>
        <div className="timeline">
          <span>{state.start.toFixed(1)} s</span>
          <input
            aria-label="Recording position"
            type="range"
            min="0"
            max={Math.max(0, (m?.duration_s || 60) - state.duration)}
            step=".25"
            value={state.start}
            onChange={(e) => navigate(Number(e.target.value))}
          />
          <span>{m?.duration_s.toFixed(0)} s</span>
        </div>
        <details className="channel-picker">
          <summary>Channels · {channels.join(", ")}</summary>
          <div className="chips">
            {m?.channels.map((ch) => (
              <button
                key={ch}
                aria-pressed={channels.includes(ch)}
                onClick={() => {
                  const next = channels.includes(ch)
                    ? channels.filter((c) => c !== ch)
                    : [...channels, ch];
                  if (next.length && next.length <= 8)
                    dispatch({ type: "channels", channels: next });
                }}
              >
                {ch}
              </button>
            ))}
          </div>
        </details>
      </Panel>
      <div className="two-col">
        <Panel
          title="Spectral fingerprint"
          eyebrow={`${channels[0] || "CHANNEL"} / NEURODSP WELCH`}
          actions={<span className="unit">V²/Hz · log₁₀</span>}
        >
          <Async loading={analysis.loading} error={analysis.error}>
            {a && (
              <>
                <Trace
                  x={a.frequencies_hz}
                  y={a.density_V2_Hz}
                  label="Power spectral density"
                  log
                />
                <div className="band-stats">
                  {Object.entries(a.band_power_V2).map(([k, v]) => (
                    <div key={k}>
                      <span>{k === "mu" ? "μ · 8–13 Hz" : "β · 13–30 Hz"}</span>
                      <strong>
                        {v.toExponential(2)} <small>V²</small>
                      </strong>
                    </div>
                  ))}
                </div>
              </>
            )}
          </Async>
        </Panel>
        <Panel
          title="Time–frequency power"
          eyebrow="MORLET / 3 CYCLES"
          actions={<span className="unit">V² · log color</span>}
        >
          <Async loading={analysis.loading} error={analysis.error}>
            {a && (
              <>
                <div className="tf-labels">
                  <span>30 Hz</span>
                  <Heatmap
                    values={a.tf_power_V2}
                    label="Morlet time frequency power"
                  />
                  <span>8 Hz</span>
                </div>
                <div className="plot-caption">
                  {state.start}–{state.start + state.duration} s · edge guard{" "}
                  {a.edge_guard_s} s
                </div>
              </>
            )}
          </Async>
        </Panel>
      </div>
      <div className="two-col">
        <Panel title="Trial annotations" eyebrow="EVENTS / SELECT TO INSPECT">
          <div className="events">
            {m?.events.map((event, i) => (
              <button
                key={`${event.onset}-${i}`}
                onClick={() => navigate(event.onset - 2)}
                className={
                  event.onset >= state.start &&
                  event.onset < state.start + state.duration
                    ? "selected"
                    : ""
                }
              >
                <span className="mono">{event.onset.toFixed(1)} s</span>
                <span>{event.label || event.code}</span>
                <small>{event.duration.toFixed(1)} s</small>
              </button>
            ))}
          </div>
        </Panel>
        <Panel
          title="Mu burst intervals"
          eyebrow="FIXED AMPLITUDE / EXPLORATORY"
        >
          <div className="burst-track">
            {a?.bursts_s.map(([s, e]) => (
              <span
                key={s}
                style={{
                  left: `${(100 * (s - state.start)) / state.duration}%`,
                  width: `${(100 * (e - s)) / state.duration}%`,
                }}
                title={`${s.toFixed(2)}–${e.toFixed(2)} s`}
              />
            ))}
          </div>
          <p className="muted">
            {a?.bursts_s.length || 0} intervals · 3/5 µV dual thresholds · ≥3
            cycles
          </p>
          <Warning>
            Window-local fixed thresholds; not rest-calibrated. Burst estimates
            and TFR edge regions are exploratory.
          </Warning>
          <p className="muted small">
            Reference: {m?.reference}. {m?.quality.join(" · ")}
          </p>
        </Panel>
      </div>
      <Evidence result={analysis.data} />
    </>
  );
}
