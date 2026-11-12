import { useCallback, useEffect, useState } from "react";
import type { Mesh, Result, SourceSeries } from "../api/client";
import type { Selection, Action } from "../state";
import {
  Async,
  Evidence,
  Json,
  Panel,
  Trace,
  useResource,
  Warning,
} from "../components/Common";
import BrainScene from "../components/BrainScene";
import SourceUncertainty from "./SourceUncertainty";
export default function Source({
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
  const mesh = useResource<Result<Mesh>>(`/sources/${id}/mesh`);
  const series = useResource<Result<SourceSeries>>(
    `/sources/${id}/series?index=${state.source}`,
  );
  const [opacity, setOpacity] = useState(0.45);
  const [layers, setLayers] = useState(["surface", "sources", "electrodes"]);
  const select = useCallback(
    (index: number) => dispatch({ type: "source", index }),
    [dispatch],
  );
  useEffect(() => {
    onResult(mesh.data);
  }, [mesh.data, onResult]);
  const data = mesh.data?.data;
  const leadfield = data?.diagnostics.leadfield as
    { singular_values?: number[] } | undefined;
  return (
    <>
      <Async loading={mesh.loading} error={mesh.error}>
        {data && (
          <>
            <div className="metrics">
              <div>
                <span>Source points</span>
                <strong>{data.points_mm.length}</strong>
              </div>
              <div>
                <span>Surface triangles</span>
                <strong>{data.faces.length.toLocaleString()}</strong>
              </div>
              <div>
                <span>Electrodes</span>
                <strong>
                  {data.electrode_points_mm.length || "Unavailable"}
                </strong>
              </div>
              <div>
                <span>Frame</span>
                <strong>{data.frame}</strong>
              </div>
            </div>
            <Panel
              title="Anatomical geometry & sources"
              eyebrow="3D WORKSPACE / PHYSICAL COORDINATES"
              actions={<span className="unit">Three.js · millimetres</span>}
            >
              <div className="toolbar">
                {data.layers.map((l) => (
                  <label key={l}>
                    <input
                      type="checkbox"
                      checked={layers.includes(l)}
                      onChange={() =>
                        setLayers(
                          layers.includes(l)
                            ? layers.filter((x) => x !== l)
                            : [...layers, l],
                        )
                      }
                    />
                    {l}
                  </label>
                ))}
                <label className="push">
                  Surface opacity
                  <input
                    aria-label="Surface opacity"
                    type="range"
                    min="0"
                    max="1"
                    step=".05"
                    value={opacity}
                    onChange={(e) => setOpacity(Number(e.target.value))}
                  />
                </label>
              </div>
              <BrainScene
                data={data}
                selected={state.source}
                onSelect={select}
                opacity={opacity}
                layers={layers}
              />
              <div className="coordinate-bar">
                <span className="mono">Source {state.source}</span>
                <span>
                  {series.data?.data.point_mm
                    ?.map((v) => v.toFixed(2))
                    .join(" / ") || "Spatial geometry unavailable"}{" "}
                  mm
                </span>
                <span>Rendering ≠ forward-model geometry</span>
              </div>
            </Panel>
          </>
        )}
      </Async>
      <div className="two-col">
        <Panel
          title="Selected source time course"
          eyebrow="SOURCE / TEMPORAL INSPECTION"
        >
          <label className="source-selector">
            Source index
            <input
              aria-label="Source index"
              type="number"
              min="0"
              max={Math.max(0, (data?.values.length || 1) - 1)}
              value={state.source}
              onChange={(e) =>
                select(
                  Math.max(
                    0,
                    Math.min(
                      (data?.values.length || 1) - 1,
                      Number(e.target.value),
                    ),
                  ),
                )
              }
            />
          </label>
          <Async loading={series.loading} error={series.error}>
            {series.data && (
              <>
                <Trace
                  x={series.data.data.times_s}
                  y={series.data.data.values}
                  label="Source time course"
                  color="var(--amber)"
                />
                <p className="plot-caption">
                  Time s · {series.data.data.units}
                </p>
              </>
            )}
          </Async>
        </Panel>
        <Panel
          title="Model evidence"
          eyebrow="NUMERICAL / ANATOMICAL READINESS"
        >
          {leadfield?.singular_values && (
            <Trace
              x={leadfield.singular_values.map((_, i) => i + 1)}
              y={leadfield.singular_values}
              label="Lead-field singular-value spectrum"
              log
            />
          )}
          <Json value={data?.diagnostics || {}} />
          {series.data?.data.point_spread && (
            <>
              <h3>Selected point-spread function</h3>
              <Trace
                x={series.data.data.point_spread.map((_, i) => i)}
                y={series.data.data.point_spread}
                label="Selected source point spread"
                color="var(--lavender)"
              />
              <Json value={series.data.data.diagnostics} />
            </>
          )}
          <Warning>
            Inverse reconstruction is not anatomical truth. No BEM computation
            is launched. Point-spread, leakage and regularization diagnostics
            appear only when supplied by a verified artifact.
          </Warning>
          <p className="muted">{data?.render_geometry}</p>
        </Panel>
      </div>
      <SourceUncertainty />
      <Evidence result={mesh.data} />
    </>
  );
}
