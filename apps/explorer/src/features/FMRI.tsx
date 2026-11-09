import { useEffect } from "react";
import type { FMRI as FMRIData, Result } from "../api/client";
import type { Selection, Action } from "../state";
import {
  Async,
  Evidence,
  Json,
  Panel,
  useResource,
  Warning,
} from "../components/Common";
import { Heatmap } from "../components/Heatmap";
import MRI from "./MRI";
export default function FMRI({
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
  const response = useResource<Result<FMRIData>>(`/fmri/${id}`);
  useEffect(() => {
    onResult(response.data);
  }, [response.data, onResult]);
  const data = response.data?.data;
  return (
    <>
      <Warning>
        <strong>Descriptive inference only.</strong> Milestone14.1 policy is
        enforced by the service. There is no confirmatory override. Human
        fMRIPrep derivatives and test–retest results remain unavailable.
      </Warning>
      <Async loading={response.loading} error={response.error}>
        {data && (
          <>
            <Panel
              title="Task model & contrast"
              eyebrow="fMRI / SCIENTIFIC POLICY"
              actions={<span className="badge">DESCRIPTIVE ONLY</span>}
            >
              <div className="toolbar">
                <label>
                  Contrast
                  <select aria-label="fMRI contrast">
                    <option>task · effect size</option>
                  </select>
                </label>
                <span>
                  Preprocessing:{" "}
                  {String(data.metadata.preprocessing || "See provenance")}
                </span>
                <span>
                  Noise: {String(data.metadata.noise_model || "Unknown")}
                </span>
              </div>
              <div className="two-col inset">
                <div>
                  {data.design.length ? (
                    <>
                      <Heatmap
                        values={data.design}
                        label="GLM design matrix"
                        mode="signed"
                      />
                      <p className="plot-caption">
                        {data.columns.join(" · ")} · signed linear colors ·{" "}
                        {data.design.length} scans · TR {data.tr_s} s
                      </p>
                    </>
                  ) : (
                    <p className="empty">
                      Design matrix unavailable for this imported artifact.
                    </p>
                  )}
                </div>
                <div>
                  <h3>ROI summary</h3>
                  <Json value={data.roi} />
                  <details>
                    <summary>Residual and motion/confound diagnostics</summary>
                    <Json value={data.residual} />
                  </details>
                  <p className="muted">
                    Events:{" "}
                    {data.events
                      .map((e) => `${e.onset}s ${e.trial_type}`)
                      .join(" · ") || "Unavailable"}
                  </p>
                </div>
              </div>
            </Panel>
            {response.data?.state !== "NOT_AVAILABLE" ? (
              <MRI
                key={id}
                id={id}
                state={state}
                dispatch={dispatch}
                onResult={() => {}}
              />
            ) : (
              <Warning>
                NOT AVAILABLE: raw BOLD metadata is available, but validated
                derivatives and contrast maps are missing.
              </Warning>
            )}
            <Evidence result={response.data} />
          </>
        )}
      </Async>
    </>
  );
}
