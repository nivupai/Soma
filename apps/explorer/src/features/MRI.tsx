import { useEffect, useRef, useState } from "react";
import { type Result, type VolumeMeta, type Slice, query } from "../api/client";
import type { Action, Selection } from "../state";
import {
  Async,
  Evidence,
  Panel,
  useResource,
  Warning,
} from "../components/Common";
function SliceCanvas({
  slice,
  meta,
  range,
  opacity,
  label,
  voxel,
  onSelect,
}: {
  slice: Slice;
  meta: VolumeMeta;
  range: number[];
  opacity: number;
  label: string;
  voxel: number[];
  onSelect: (v: number[]) => void;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState([0, 0]);
  const drag = useRef<number[] | null>(null);
  const axes =
    slice.plane === "axial"
      ? [0, 1, 2]
      : slice.plane === "coronal"
        ? [0, 2, 1]
        : [1, 2, 0];
  const [u, v] = axes;
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    canvas.width = slice.width;
    canvas.height = slice.height;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const image = ctx.createImageData(slice.width, slice.height);
    for (let y = 0; y < slice.height; y++)
      for (let x = 0; x < slice.width; x++) {
        const i = (y * slice.width + x) * 4;
        const value = Math.max(
          0,
          Math.min(
            255,
            (255 * (slice.values[y][x] - range[0])) /
              (range[1] - range[0] || 1),
          ),
        );
        const seg = slice.labels?.[y][x] || 0;
        const color = seg % 2 ? [67, 196, 183] : [232, 171, 80];
        const alpha =
          seg && (label === "all" || String(seg) === label) ? opacity : 0;
        image.data.set(
          [
            value * (1 - alpha) + color[0] * alpha,
            value * (1 - alpha) + color[1] * alpha,
            value * (1 - alpha) + color[2] * alpha,
            255,
          ],
          i,
        );
      }
    ctx.putImageData(image, 0, 0);
    ctx.strokeStyle = "#5ad4c1";
    ctx.lineWidth = 0.4;
    const cx = voxel[u] / slice.stride + 0.5,
      cy =
        Math.floor((meta.shape[v] - 1) / slice.stride) -
        voxel[v] / slice.stride +
        0.5;
    ctx.beginPath();
    ctx.moveTo(cx, 0);
    ctx.lineTo(cx, slice.height);
    ctx.moveTo(0, cy);
    ctx.lineTo(slice.width, cy);
    ctx.stroke();
  }, [slice, meta, range, opacity, label, voxel, u, v]);
  function pick(event: React.MouseEvent<HTMLCanvasElement>) {
    if (event.shiftKey) return;
    const r = event.currentTarget.getBoundingClientRect();
    const x = Math.max(
      0,
      Math.min(
        slice.width - 1,
        Math.floor(((event.clientX - r.left) / r.width) * slice.width),
      ),
    );
    const y = Math.max(
      0,
      Math.min(
        slice.height - 1,
        Math.floor(((event.clientY - r.top) / r.height) * slice.height),
      ),
    );
    const next = [...voxel];
    next[u] = x * slice.stride;
    next[v] =
      (Math.floor((meta.shape[v] - 1) / slice.stride) - y) * slice.stride;
    onSelect(next);
  }
  return (
    <div className="slice-pane">
      <div className="slice-title">
        <strong>{slice.plane}</strong>
        <span className="mono">{slice.index.toString().padStart(3, "0")}</span>
      </div>
      <div className="slice-image">
        <span className="orient top">{slice.vertical_labels[0]}</span>
        <span className="orient bottom">{slice.vertical_labels[1]}</span>
        <span className="orient left">{slice.horizontal_labels[0]}</span>
        <span className="orient right">{slice.horizontal_labels[1]}</span>
        <canvas
          ref={ref}
          role="img"
          aria-label={`${slice.plane} MRI slice`}
          onClick={pick}
          onPointerDown={(e) => {
            if (e.shiftKey) {
              drag.current = [e.clientX, e.clientY, ...pan];
              e.currentTarget.setPointerCapture(e.pointerId);
            }
          }}
          onPointerMove={(e) => {
            if (drag.current)
              setPan([
                drag.current[2] + e.clientX - drag.current[0],
                drag.current[3] + e.clientY - drag.current[1],
              ]);
          }}
          onPointerUp={() => {
            drag.current = null;
          }}
          style={{
            width: `min(80cqw, ${(80 * meta.spacing_mm[u] * slice.width) / (meta.spacing_mm[v] * slice.height)}cqh)`,
            height: `min(${(80 * meta.spacing_mm[v] * slice.height) / (meta.spacing_mm[u] * slice.width)}cqw, 80cqh)`,
            transform: `translate(${pan[0]}px,${pan[1]}px) scale(${zoom})`,
          }}
        />
      </div>
      <div className="slice-tools">
        <label>
          Zoom
          <input
            aria-label={`${slice.plane} zoom`}
            type="range"
            min="1"
            max="4"
            step=".1"
            value={zoom}
            onChange={(e) => setZoom(Number(e.target.value))}
          />
        </label>
        <button
          onClick={() => {
            setPan([0, 0]);
            setZoom(1);
          }}
        >
          Reset
        </button>
      </div>
    </div>
  );
}
export default function MRI({
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
  const m = useResource<Result<VolumeMeta>>(`/volumes/${id}`);
  const [range, setRange] = useState<number[] | null>(null);
  const [opacity, setOpacity] = useState(0.25);
  const [label, setLabel] = useState("all");
  const meta = m.data?.data;
  useEffect(() => {
    onResult(m.data);
  }, [m.data, onResult]);
  // This keyed component resets its local controls on dataset switches.
  const initialized = useRef(false);
  useEffect(() => {
    if (meta && !initialized.current) {
      initialized.current = true;
      dispatch({
        type: "voxel",
        voxel: meta.shape.map((v) => Math.floor(v / 2)),
      });
    }
  }, [meta, dispatch]);
  const path = meta
    ? query({ x: state.voxel[0], y: state.voxel[1], z: state.voxel[2] })
    : null;
  const axial = useResource<Result<Slice>>(
      path ? `/volumes/${id}/slice?plane=axial&${path}` : null,
    ),
    coronal = useResource<Result<Slice>>(
      path ? `/volumes/${id}/slice?plane=coronal&${path}` : null,
    ),
    sagittal = useResource<Result<Slice>>(
      path ? `/volumes/${id}/slice?plane=sagittal&${path}` : null,
    );
  const actualRange = range || meta?.intensity_range || [0, 1];
  return (
    <Async loading={m.loading} error={m.error}>
      {meta && (
        <>
          <div className="metrics">
            <div>
              <span>Voxel grid</span>
              <strong>{meta.shape.join(" × ")}</strong>
            </div>
            <div>
              <span>Spacing</span>
              <strong>
                {meta.spacing_mm.map((v) => v.toFixed(1)).join(" / ")}
                <small> mm</small>
              </strong>
            </div>
            <div>
              <span>Coordinate frame</span>
              <strong>{meta.frame}</strong>
            </div>
            <div>
              <span>Orientation</span>
              <strong>
                {meta.orientation.join("")}
                <small> neurological</small>
              </strong>
            </div>
          </div>
          <Panel
            title={
              meta.units.includes("effect")
                ? "Descriptive effect map"
                : "Multiplanar anatomy"
            }
            eyebrow="SPATIAL WORKSPACE / AFFINE-AWARE"
            actions={
              <span className="unit">
                Click to position · Shift-drag to pan
              </span>
            }
          >
            <div className="slices">
              {[axial, coronal, sagittal].map((s, i) => (
                <Async key={i} loading={s.loading} error={s.error}>
                  {s.data && (
                    <SliceCanvas
                      slice={s.data.data}
                      meta={meta}
                      range={actualRange}
                      opacity={opacity}
                      label={label}
                      voxel={state.voxel}
                      onSelect={(voxel) => dispatch({ type: "voxel", voxel })}
                    />
                  )}
                </Async>
              ))}
            </div>
            <div className="coordinate-bar">
              <span className="eyebrow">CROSSHAIR</span>
              <span className="mono" data-testid="voxel-coordinates">
                Voxel [{state.voxel.join(", ")}]
              </span>
              <span className="mono" data-testid="world-coordinates">
                World [
                {axial.data?.data.world_mm.map((v) => v.toFixed(2)).join(", ")}]
                mm
              </span>
              <span>Label {axial.data?.data.label ?? "unavailable"}</span>
            </div>
          </Panel>
          <div className="two-col">
            <Panel
              title="Position & intensity"
              eyebrow="VOXEL / WORLD COORDINATES"
            >
              <div className="controls">
                {meta.shape.map((n, i) => (
                  <label key={i}>
                    {["I", "J", "K"][i]}
                    <input
                      aria-label={`Voxel ${["I", "J", "K"][i]}`}
                      type="range"
                      min="0"
                      max={n - 1}
                      value={state.voxel[i]}
                      onChange={(e) => {
                        const voxel = [...state.voxel];
                        voxel[i] = Number(e.target.value);
                        dispatch({ type: "voxel", voxel });
                      }}
                    />
                    <span className="mono">{state.voxel[i]}</span>
                  </label>
                ))}
                <label>
                  Window low
                  <input
                    aria-label="Intensity window low"
                    type="number"
                    value={Number(actualRange[0].toPrecision(5))}
                    step=".01"
                    onChange={(e) =>
                      setRange([Number(e.target.value), actualRange[1]])
                    }
                  />
                </label>
                <label>
                  Window high
                  <input
                    aria-label="Intensity window high"
                    type="number"
                    value={Number(actualRange[1].toPrecision(5))}
                    step=".01"
                    onChange={(e) =>
                      setRange([actualRange[0], Number(e.target.value)])
                    }
                  />
                </label>
              </div>
              <p className="muted">
                Intensity: {meta.units}. Actual affine maps every displayed
                pixel; anisotropic voxel aspect is preserved.
              </p>
            </Panel>
            <Panel title="Anatomical overlays" eyebrow="CATEGORICAL LABELS">
              <div className="controls">
                <label>
                  Label
                  <select
                    aria-label="Segmentation label"
                    value={label}
                    onChange={(e) => setLabel(e.target.value)}
                  >
                    <option value="all">All available labels</option>
                    {Object.entries(meta.labels).map(([id, name]) => (
                      <option key={id} value={id}>
                        {name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Opacity
                  <input
                    aria-label="Segmentation opacity"
                    type="range"
                    min="0"
                    max=".8"
                    step=".05"
                    value={opacity}
                    onChange={(e) => setOpacity(Number(e.target.value))}
                  />
                  <span>{Math.round(opacity * 100)}%</span>
                </label>
              </div>
              <Warning>
                {Object.keys(meta.labels).length
                  ? "Aligned labels on the exact image grid. Synthetic labels are analytic regions, not validated human tissues."
                  : "No aligned segmentation supplied. No labels are fabricated."}
              </Warning>
              {meta.oblique && (
                <Warning>
                  Oblique acquisition: these are voxel-aligned planes, not
                  resampled world-orthogonal sections.
                </Warning>
              )}
              <p className="muted">
                Tissue validation does not establish skull/scalp conductor
                accuracy.
              </p>
            </Panel>
          </div>
          <Evidence result={m.data} />
        </>
      )}
    </Async>
  );
}
