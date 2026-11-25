import { useState } from "react";
import { Async, Panel, Warning, useResource } from "../components/Common";
import { type Result, type VolumeMeta, type Slice } from "../api/client";
import { SliceCanvas } from "./MRI";
import ReadinessBanner from "../components/ReadinessBanner";
import { readinessLabel } from "../components/headColor";
type View = { id: string; label: string; kind: string };
type Report = {
  schema: string;
  anatomy_status: string;
  readiness?: {
    status: string;
    anatomical_accuracy_established: boolean;
    checks: Record<string, boolean | null>;
    limitations: string[];
  };
  human_localization_accuracy: boolean;
  local_views: View[];
  comparisons: {
    comparison: string;
    relative: number;
    target: number;
    passed: boolean;
  }[];
  mesh_quality: {
    level: number;
    passed: boolean;
    minimum_interface_separation_mm: number;
    boundaries: { triangle_quality_min: number }[];
  }[];
  tissue_metrics: {
    dataset: string;
    name: string;
    Dice: number;
    HD95_mm: number;
  }[];
};
type Geometry = {
  status: string;
  frame: string;
  meshes: { vertices_m: number[][]; faces: number[][]; boundary: string }[];
  electrodes_m: number[][];
};
function LocalSlice({ id }: { id: string }) {
  const meta = useResource<Result<VolumeMeta>>(`/volumes/${id}`);
  const [index, setIndex] = useState(128);
  const shape = meta.data?.data.shape;
  const voxel = shape
    ? [
        Math.floor(shape[0] / 2),
        Math.floor(shape[1] / 2),
        Math.min(index, shape[2] - 1),
      ]
    : [0, 0, 0];
  const slice = useResource<Result<Slice>>(
    shape
      ? `/volumes/${id}/slice?plane=axial&x=${voxel[0]}&y=${voxel[1]}&z=${voxel[2]}`
      : null,
  );
  return (
    <Async
      loading={meta.loading || slice.loading}
      error={meta.error || slice.error}
    >
      {meta.data && slice.data && (
        <>
          <label>
            Local axial slice
            <input
              aria-label="Local axial slice"
              type="range"
              min="0"
              max={meta.data.data.shape[2] - 1}
              value={voxel[2]}
              onChange={(e) => setIndex(Number(e.target.value))}
            />
          </label>
          <SliceCanvas
            meta={meta.data.data}
            slice={slice.data.data}
            range={meta.data.data.intensity_range}
            opacity={0.4}
            label="all"
            voxel={voxel}
            onSelect={(v) => setIndex(v[2])}
          />
          <p>
            Frame: {meta.data.data.frame}. Overlay labels use the exact MRI
            grid. Provided FreeSurfer labels are automated; the separately named
            manual reference and prediction views are IBSR tissue evidence only.
          </p>
        </>
      )}
    </Async>
  );
}
function LocalMesh({ id }: { id: string }) {
  const g = useResource<Geometry>(`/mri-head-models/local/${id}`);
  const colors = ["var(--lavender)", "var(--amber)", "var(--teal)"];
  return (
    <Async loading={g.loading} error={g.error}>
      {g.data && (
        <>
          <ReadinessBanner
            subject="Local MRI-derived head"
            readiness={readinessLabel(g.data.status)}
            geometricallyValid={null}
            anatomicallyValidated={false}
            reasons={["topology and registration QC only"]}
          />
          <svg
            viewBox="-130 -130 260 260"
            role="img"
            aria-label="Local MRI-derived conductor and measured electrodes"
            style={{ width: "100%", maxHeight: 420 }}
          >
            {g.data.meshes.map((m, i) => (
              <g
                key={m.boundary}
                fill="none"
                stroke={colors[i]}
                strokeWidth=".25"
                opacity=".4"
              >
                {m.faces.map((f, j) => (
                  <polygon
                    key={j}
                    points={f
                      .map(
                        (k) =>
                          `${m.vertices_m[k][0] * 1000},${-m.vertices_m[k][1] * 1000}`,
                      )
                      .join(" ")}
                  />
                ))}
              </g>
            ))}
            {g.data.electrodes_m.map((p, i) => (
              <circle
                key={i}
                cx={p[0] * 1000}
                cy={-p[1] * 1000}
                r="1.2"
                fill="var(--text)"
              />
            ))}
          </svg>
          <p>
            Actual local FLASH-derived inner skull, outer skull and scalp;
            measured electrodes. Axial projection, MRI surface RAS, display mm.{" "}
            {g.data.status}: topology and registration QC establish no
            anatomical accuracy. No redistribution.
          </p>
        </>
      )}
    </Async>
  );
}
export default function HumanHeadModels() {
  const r = useResource<Report>("/mri-head-models");
  const [selected, setSelected] = useState("");
  const data = r.data;
  const valid =
    data?.schema === "soma.mri-head-model.aggregate/1" &&
    data.human_localization_accuracy === false;
  const view = data?.local_views.find((v) => v.id === selected);
  return (
    <Panel
      title="MRI-derived human head models"
      eyebrow="M32 · ANATOMICAL EVIDENCE"
    >
      <Async
        loading={r.loading}
        error={
          r.error ||
          (data && !valid ? "Unsupported human anatomical evidence" : "")
        }
      >
        {data && valid && (
          <>
            <ReadinessBanner
              subject="M32 MRI head model"
              readiness={readinessLabel(
                data.readiness?.status ?? data.anatomy_status,
              )}
              geometricallyValid={
                data.readiness
                  ? Object.values(data.readiness.checks).every(
                      (v) => v === true,
                    )
                  : null
              }
              anatomicallyValidated={
                data.readiness?.anatomical_accuracy_established === true
              }
              reasons={data.readiness?.limitations ?? []}
            />
            <Warning>
              0 validated conductor anatomies · 1 QC-only anatomy · 23
              tissue-reference cases not ready for a full conductor model. Human
              source-localization accuracy is not established. Native mesh
              portability remains unproven.
            </Warning>
            <p>
              Independent intensity segmentation reproduces the historical
              baseline on 18 IBSR and five MRBrainS training cases. All 23 fail
              the frozen tissue target. Brain-tissue references do not validate
              skull or scalp.
            </p>
            <table>
              <thead>
                <tr>
                  <th>Dataset / tissue</th>
                  <th>Mean Dice</th>
                  <th>Mean HD95 mm</th>
                </tr>
              </thead>
              <tbody>
                {data.tissue_metrics.map((t) => (
                  <tr key={t.dataset + t.name}>
                    <td>
                      {t.dataset} / {t.name}
                    </td>
                    <td>{t.Dice.toFixed(3)}</td>
                    <td>{t.HD95_mm.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <table>
              <thead>
                <tr>
                  <th>Numerical comparison</th>
                  <th>Relative difference</th>
                  <th>Frozen 10% target</th>
                </tr>
              </thead>
              <tbody>
                {data.comparisons.map((c) => (
                  <tr key={c.comparison}>
                    <td>{c.comparison}</td>
                    <td>{(100 * c.relative).toFixed(2)}%</td>
                    <td>{c.passed ? "PASS" : "FAIL"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <table>
              <thead>
                <tr>
                  <th>BEM level</th>
                  <th>Surface QC</th>
                  <th>Minimum triangle quality</th>
                  <th>Minimum interface gap mm</th>
                </tr>
              </thead>
              <tbody>
                {data.mesh_quality.map((q) => (
                  <tr key={q.level}>
                    <td>{q.level}</td>
                    <td>{q.passed ? "PASS" : "FAIL"}</td>
                    <td>
                      {Math.min(
                        ...q.boundaries.map((b) => b.triangle_quality_min),
                      ).toFixed(3)}
                    </td>
                    <td>{q.minimum_interface_separation_mm.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p>
              Three-compartment BEM; CSF is homogenized with brain. A
              four-material FEM comparison is not physically comparable.
              Synthetic neural sources occupy only 13.10% of provided GM voxels.
              This is a conditional numerical demonstration on real MRI anatomy.
            </p>
            {data.local_views.length ? (
              <>
                <label>
                  Authorized local anatomy
                  <select
                    aria-label="Authorized local anatomy"
                    value={selected}
                    onChange={(e) => setSelected(e.target.value)}
                  >
                    <option value="">Select local view</option>
                    {data.local_views.map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.label}
                      </option>
                    ))}
                  </select>
                </label>
                {view?.kind === "mri" && (
                  <LocalSlice key={view.id} id={view.id} />
                )}
                {view?.kind === "anatomical-model" && (
                  <LocalMesh key={view.id} id={view.id} />
                )}
              </>
            ) : (
              <p>
                No locally authorized MRI is enabled. Participant anatomy is not
                packaged in public assets. An operator can explicitly prepare a
                private viewer and enable direct loopback access; no synthetic
                brain is substituted.
              </p>
            )}
          </>
        )}
      </Async>
    </Panel>
  );
}
