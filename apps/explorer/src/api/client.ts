export type Interpretation =
  | "VALIDATED_NUMERICAL"
  | "DESCRIPTIVE_ONLY"
  | "EXPLORATORY"
  | "INDETERMINATE"
  | "INVALID"
  | "NOT_AVAILABLE";
export interface Result<T> {
  dataset_id: string;
  state: Interpretation;
  synthetic: boolean;
  warnings: string[];
  provenance: Record<string, unknown>;
  data: T;
}
export interface Dataset {
  id: string;
  label: string;
  kind: string;
  synthetic: boolean;
  state: Interpretation;
  available: boolean;
  subjects: string[];
  sessions: string[];
  runs: string[];
}
export interface Catalog {
  datasets: Dataset[];
  version: string;
  inference_policy: string;
}
export interface Event {
  onset: number;
  duration: number;
  code?: string;
  label?: string;
  trial_type?: string;
}
export interface EEGMeta {
  channels: string[];
  fs_hz: number;
  duration_s: number;
  units: string;
  reference: string;
  events: Event[];
  quality: string[];
}
export interface EEGWindow {
  times_s: number[];
  channels: string[];
  values_V: number[][];
  lower_V: number[][];
  upper_V: number[][];
  fs_hz: number;
  display_only: boolean;
  start_sample: number;
  stop_sample: number;
}
export interface EEGAnalysis {
  channel: string;
  frequencies_hz: number[];
  density_V2_Hz: number[];
  band_power_V2: Record<string, number>;
  tf_times_s: number[];
  tf_frequencies_hz: number[];
  tf_power_V2: number[][];
  bursts_s: number[][];
  n_analysis_samples: number;
  edge_guard_s: number;
}
export interface VolumeMeta {
  shape: number[];
  affine_mm: number[][];
  spacing_mm: number[];
  orientation: string[];
  frame: string;
  units: string;
  intensity_range: number[];
  oblique: boolean;
  labels: Record<string, string>;
}
export interface Slice {
  plane: string;
  index: number;
  width: number;
  height: number;
  values: number[][];
  labels: number[][] | null;
  voxel: number[];
  world_mm: number[];
  label: number | null;
  pixel_to_world_mm: number[][];
  horizontal_labels: string[];
  vertical_labels: string[];
  stride: number;
  overlay_units: string | null;
}
export interface Mesh {
  vertices_mm: number[][];
  faces: number[][];
  values: number[];
  points_mm: number[][];
  electrode_points_mm: number[][];
  frame: string;
  units: string;
  layers: string[];
  qc: string[];
  render_geometry: string;
  diagnostics: Record<string, unknown>;
}
export interface SourceSeries {
  source_index: number;
  times_s: number[];
  values: number[];
  units: string;
  point_mm: number[] | null;
  point_spread: number[] | null;
  diagnostics: Record<string, unknown>;
}
export interface Artifact {
  schema_name?: string | null;
  schema_version?: string | null;
  validation_status?: string;
  migration_status?: string;
  result_envelope?: Record<string, unknown> | null;
  state: Interpretation;
  id: string;
  title: string;
  metrics: Record<string, unknown>;
  parameters: Record<string, unknown>;
  compatibility: Record<string, string>;
  checksums: Record<string, string>;
  figures: string[];
  warnings: string[];
}
export interface FMRI {
  design: number[][];
  columns: string[];
  events: Event[];
  metadata: Record<string, unknown>;
  residual: Record<string, unknown>;
  roi: Record<string, unknown>;
  tr_s?: number;
  n_scans?: number;
  limitations?: string[];
}
export interface Job {
  id: string;
  status: string;
  progress: number;
  error: string | null;
  result: Result<EEGAnalysis> | null;
  manifest: Record<string, unknown> | null;
}
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  if (!response.ok) {
    const body = await response
      .json()
      .catch(() => ({ detail: "Service unavailable" }));
    if (
      body.detail &&
      typeof body.detail === "object" &&
      Array.isArray(body.detail.scientific_compatibility)
    ) {
      const reasons: string[] = [];
      for (const judgment of body.detail.scientific_compatibility) {
        for (const issue of [
          ...(judgment.issues ?? []),
          ...(judgment.unknown ?? []),
        ]) {
          if (
            typeof issue.field === "string" &&
            typeof issue.reason === "string"
          )
            reasons.push(`${issue.field}: ${issue.reason}`);
        }
      }
      throw new Error(`Scientific incompatibility: ${reasons.join("; ")}`);
    }
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : `Request rejected (${response.status})`,
    );
  }
  return response.json() as Promise<T>;
}
export const query = (values: Record<string, string | number>) =>
  new URLSearchParams(
    Object.entries(values).map(([k, v]) => [k, String(v)]),
  ).toString();
export type Readiness = "VALIDATED" | "QC_ONLY" | "NOT_READY";
export type HeadLayerName = "scalp" | "outer_skull" | "inner_skull" | "cortex";
export interface HeadLayer {
  name: HeadLayerName;
  label: string;
  vertices_mm: number[][];
  faces: number[][];
}
export interface HeadSceneData {
  contract: "soma.explorer.head-scene/1";
  head_id: string;
  label: string;
  synthetic: boolean;
  redistributable: boolean;
  private_mri_used: false;
  generator: string;
  frame: string;
  units: "mm";
  readiness: Readiness;
  readiness_status: string;
  readiness_reasons: string[];
  geometrically_valid: boolean;
  anatomically_validated: boolean;
  geometry_checks: Record<string, boolean | number | string>;
  layers: HeadLayer[];
  sensors: { label: string; position_mm: number[] }[];
  sources: {
    kind: "cortical_surface";
    positions_mm: number[][];
    normals: number[][];
    scalar_name: string;
    scalar_units: string;
    scalar: number[];
  };
  warnings: string[];
}
/** Per-source scalar + interval overlay (M34 localisation error; mock today). */
export interface SourceUncertaintyOverlay {
  contract: "soma.explorer.source-uncertainty-overlay/1";
  head_id: string;
  quantity: "localisation_error";
  units: "mm";
  statistic: "mean";
  interval: "confidence_interval";
  confidence_level: number;
  n_sources: number;
  mean: number[];
  lower: number[];
  upper: number[];
  origin: "MOCK_FIXTURE" | "M34_RESULT";
  fixture: boolean;
  warnings: string[];
}
