export type Page =
  | "Overview"
  | "Datasets"
  | "EEG Laboratory"
  | "MRI Anatomy"
  | "Source Models"
  | "fMRI Laboratory"
  | "Experiments"
  | "Workflows"
  | "Protocols"
  | "Validation"
  | "Settings";
export interface Selection {
  page: Page;
  mode: "demo" | "local";
  dataset: string;
  start: number;
  duration: number;
  channels: string[];
  voxel: number[];
  source: number;
}
export const initial: Selection = {
  page: "Overview",
  mode: "demo",
  dataset: "",
  start: 0,
  duration: 10,
  channels: [],
  voxel: [0, 0, 0],
  source: 0,
};
export type Action =
  | { type: "page"; page: Page }
  | { type: "mode"; mode: "demo" | "local" }
  | { type: "dataset"; id: string }
  | { type: "window"; start: number; duration: number }
  | { type: "channels"; channels: string[] }
  | { type: "voxel"; voxel: number[] }
  | { type: "source"; index: number };
export function reducer(s: Selection, a: Action): Selection {
  switch (a.type) {
    case "page":
      return { ...initial, mode: s.mode, page: a.page };
    case "mode":
      return { ...initial, page: s.page, mode: a.mode };
    case "dataset":
      return { ...initial, page: s.page, mode: s.mode, dataset: a.id };
    case "window":
      return { ...s, start: a.start, duration: a.duration };
    case "channels":
      return { ...s, channels: a.channels };
    case "voxel":
      return { ...s, voxel: a.voxel };
    case "source":
      return { ...s, source: a.index };
  }
}
