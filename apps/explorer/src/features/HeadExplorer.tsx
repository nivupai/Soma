import { useCallback, useMemo, useState } from "react";
import type { HeadLayerName, HeadSceneData } from "../api/client";
import { Async, Panel, Warning, useResource } from "../components/Common";
import ReadinessBanner from "../components/ReadinessBanner";
import ScalarLegend from "../components/ScalarLegend";
import HeadScene, {
  DEFAULT_LAYERS,
  type LayerSettings,
} from "../components/HeadScene";
import {
  overlayValues,
  readinessLabel,
  scalarRange,
} from "../components/headColor";
import { useUncertaintyOverlay } from "../components/useUncertaintyOverlay";

export const DEMO_HEAD_ID = "demo-synthetic-head";
type ColourBy = "scalar" | "mean" | "width";

function validScene(s: HeadSceneData | null): s is HeadSceneData {
  return (
    !!s &&
    s.contract === "soma.explorer.head-scene/1" &&
    s.synthetic === true &&
    s.private_mri_used === false &&
    s.redistributable === true &&
    // A synthetic head can never carry an anatomical-validation claim.
    s.anatomically_validated === false
  );
}

export default function HeadExplorer({ mode }: { mode: "demo" | "local" }) {
  const r = useResource<HeadSceneData>(
    mode === "demo" ? `/head-scenes/${DEMO_HEAD_ID}` : null,
  );
  const [layers, setLayers] = useState<LayerSettings>(DEFAULT_LAYERS);
  const [showSensors, setShowSensors] = useState(true);
  const [showSources, setShowSources] = useState(true);
  const [colourBy, setColourBy] = useState<ColourBy>("scalar");
  const [selected, setSelected] = useState(0);
  const select = useCallback((i: number) => setSelected(i), []);
  const scene = validScene(r.data) ? r.data : null;
  const nSources = scene?.sources.positions_mm.length ?? 0;
  const u = useUncertaintyOverlay(
    scene?.head_id ?? null,
    nSources,
    colourBy !== "scalar",
  );
  const values = useMemo(
    () =>
      !scene
        ? []
        : colourBy !== "scalar" && u.overlay
          ? overlayValues(u.overlay, colourBy)
          : scene.sources.scalar,
    [scene, colourBy, u.overlay],
  );
  const range = useMemo(() => scalarRange(values), [values]);
  if (mode === "local")
    return (
      <Panel title="3D head layers" eyebrow="M35 · PUBLIC SYNTHETIC HEAD">
        <ReadinessBanner
          readiness="NOT_READY"
          geometricallyValid={null}
          anatomicallyValidated={false}
          reasons={["no public head scene is served for local data"]}
        />
        <p>
          The public 3D head view only serves synthetic, redistributable
          geometry. Private MRI anatomy stays in the opt-in, loopback-only M32
          viewer below; it is never sent to this view.
        </p>
      </Panel>
    );
  const overlayActive = colourBy !== "scalar" && !!u.overlay;
  const units = overlayActive ? "mm" : (scene?.sources.scalar_units ?? "");
  const legendTitle = !overlayActive
    ? (scene?.sources.scalar_name.replaceAll("_", " ") ?? "")
    : colourBy === "mean"
      ? "Localisation error · mean"
      : `Localisation error · ${Math.round(100 * (u.overlay?.confidence_level ?? 0))}% CI width`;
  const setLayer = (
    name: HeadLayerName,
    patch: Partial<LayerSettings[HeadLayerName]>,
  ) => setLayers((l) => ({ ...l, [name]: { ...l[name], ...patch } }));
  return (
    <Panel
      title="Synthetic 3D head"
      eyebrow="M35 · NESTED TISSUE LAYERS / SENSORS / SOURCES"
      actions={<span className="unit">Three.js · millimetres</span>}
    >
      <Async
        loading={r.loading}
        error={
          r.error || (r.data && !scene ? "Unsupported head scene contract" : "")
        }
      >
        {scene && (
          <>
            <ReadinessBanner
              readiness={readinessLabel(scene.readiness)}
              geometricallyValid={scene.geometrically_valid}
              anatomicallyValidated={scene.anatomically_validated}
              reasons={scene.readiness_reasons}
              subject={scene.label}
            />
            <div className="head-controls" aria-label="Head layer controls">
              {scene.layers.map((l) => (
                <div className="head-layer" key={l.name}>
                  <label>
                    <input
                      type="checkbox"
                      aria-label={`Show ${l.label}`}
                      checked={layers[l.name].visible}
                      onChange={(e) =>
                        setLayer(l.name, { visible: e.target.checked })
                      }
                    />
                    {l.label}
                  </label>
                  <input
                    type="range"
                    aria-label={`${l.label} opacity`}
                    min="0"
                    max="1"
                    step=".05"
                    value={layers[l.name].opacity}
                    disabled={!layers[l.name].visible}
                    onChange={(e) =>
                      setLayer(l.name, { opacity: Number(e.target.value) })
                    }
                  />
                </div>
              ))}
              <label>
                <input
                  type="checkbox"
                  checked={showSensors}
                  onChange={(e) => setShowSensors(e.target.checked)}
                />
                EEG sensors ({scene.sensors.length})
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={showSources}
                  onChange={(e) => setShowSources(e.target.checked)}
                />
                Cortical sources ({nSources})
              </label>
              <label>
                Colour sources by
                <select
                  aria-label="Colour sources by"
                  value={colourBy}
                  onChange={(e) => setColourBy(e.target.value as ColourBy)}
                >
                  <option value="scalar">{scene.sources.scalar_name}</option>
                  <option value="mean">Localisation error (mean)</option>
                  <option value="width">Localisation error (CI width)</option>
                </select>
              </label>
            </div>
            <HeadScene
              scene={scene}
              layers={layers}
              showSensors={showSensors}
              showSources={showSources}
              sourceValues={values}
              range={range}
              selected={selected}
              onSelect={select}
            />
            <div className="two-col">
              <div>
                <Async
                  loading={colourBy !== "scalar" && u.loading}
                  error={colourBy !== "scalar" ? u.error : ""}
                >
                  <ScalarLegend
                    title={legendTitle}
                    range={range}
                    units={units}
                    badge={
                      overlayActive && u.overlay?.fixture
                        ? "MOCK FIXTURE"
                        : undefined
                    }
                    note={
                      overlayActive
                        ? u.overlay?.warnings.join(" ")
                        : "Synthetic demonstration scalar; not a reconstruction."
                    }
                  />
                </Async>
              </div>
              <SelectedSource
                scene={scene}
                index={selected}
                onSelect={select}
                overlay={overlayActive ? u.overlay : null}
              />
            </div>
            {scene.warnings.map((w) => (
              <Warning key={w}>{w}</Warning>
            ))}
          </>
        )}
      </Async>
    </Panel>
  );
}

function SelectedSource({
  scene,
  index,
  onSelect,
  overlay,
}: {
  scene: HeadSceneData;
  index: number;
  onSelect: (i: number) => void;
  overlay: ReturnType<typeof useUncertaintyOverlay>["overlay"];
}) {
  const n = scene.sources.positions_mm.length;
  const p = scene.sources.positions_mm[index];
  return (
    <div className="selected-source" aria-label="Selected head source">
      <label className="source-selector">
        Head source
        <input
          aria-label="Selected head-model source"
          type="number"
          min="0"
          max={n - 1}
          value={index}
          onChange={(e) =>
            onSelect(Math.max(0, Math.min(n - 1, Number(e.target.value) || 0)))
          }
        />
      </label>
      <dl>
        <dt>Position</dt>
        <dd>{p?.map((v) => v.toFixed(1)).join(" / ")} mm</dd>
        <dt>{scene.sources.scalar_name}</dt>
        <dd>
          {scene.sources.scalar[index]?.toFixed(3)} {scene.sources.scalar_units}
        </dd>
        {overlay && (
          <>
            <dt>Localisation error</dt>
            <dd>
              {overlay.mean[index].toFixed(1)} mm [
              {overlay.lower[index].toFixed(1)},{" "}
              {overlay.upper[index].toFixed(1)}] ·{" "}
              {Math.round(100 * overlay.confidence_level)}% CI
            </dd>
          </>
        )}
      </dl>
    </div>
  );
}
