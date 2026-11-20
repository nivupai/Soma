import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { HeadSceneData, SourceUncertaintyOverlay } from "../api/client";
import HeadExplorer, { DEMO_HEAD_ID } from "./HeadExplorer";
import ReadinessBanner from "../components/ReadinessBanner";

afterEach(() => vi.unstubAllGlobals());

const v = [
  [0, 0, 0],
  [10, 0, 0],
  [0, 10, 0],
  [0, 0, 10],
];
const f = [
  [0, 2, 1],
  [0, 1, 3],
  [0, 3, 2],
  [1, 2, 3],
];
const scene: HeadSceneData = {
  contract: "soma.explorer.head-scene/1",
  head_id: DEMO_HEAD_ID,
  label: "Synthetic concentric-shell head",
  synthetic: true,
  redistributable: true,
  private_mri_used: false,
  generator: "test",
  frame: "synthetic_head_RAS_mm",
  units: "mm",
  readiness: "NOT_READY",
  readiness_status: "NOT_READY_FOR_FORWARD_MODEL",
  readiness_reasons: ["missing MRI origin or local-use authorization"],
  geometrically_valid: true,
  anatomically_validated: false,
  geometry_checks: { closed_manifold: true },
  layers: (
    [
      ["scalp", "Scalp"],
      ["outer_skull", "Outer skull"],
      ["inner_skull", "Inner skull"],
      ["cortex", "Brain / cortex"],
    ] as const
  ).map(([name, label]) => ({ name, label, vertices_mm: v, faces: f })),
  sensors: [{ label: "Cz", position_mm: [0, 0, 12] }],
  sources: {
    kind: "cortical_surface",
    positions_mm: [
      [1, 1, 1],
      [2, 2, 2],
    ],
    normals: [
      [0, 0, 1],
      [0, 0, 1],
    ],
    scalar_name: "synthetic_activation",
    scalar_units: "a.u.",
    scalar: [0.1, 0.9],
  },
  warnings: ["Geometrically valid is not anatomically validated."],
};
const overlay: SourceUncertaintyOverlay = {
  contract: "soma.explorer.source-uncertainty-overlay/1",
  head_id: DEMO_HEAD_ID,
  quantity: "localisation_error",
  units: "mm",
  statistic: "mean",
  interval: "confidence_interval",
  confidence_level: 0.95,
  n_sources: 2,
  mean: [5, 12],
  lower: [3.25, 7.8],
  upper: [8, 19.2],
  origin: "MOCK_FIXTURE",
  fixture: true,
  warnings: ["MOCK FIXTURE: M34 localisation-error results do not exist yet."],
};

function stub(sceneValue: unknown = scene, overlayValue: unknown = overlay) {
  const fetch = vi.fn(async (url: string) => ({
    ok: true,
    json: async () =>
      url.endsWith("/uncertainty") ? overlayValue : sceneValue,
  }));
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

it("shows readiness prominently and keeps geometric and anatomical validity apart", async () => {
  stub();
  render(<HeadExplorer mode="demo" />);
  const banner = await screen.findByRole("region", {
    name: "Synthetic concentric-shell head readiness",
  });
  expect(banner).toHaveAttribute("data-readiness", "NOT_READY");
  expect(within(banner).getByText("NOT_READY")).toBeTruthy();
  const facts = within(banner).getAllByRole("definition");
  expect(facts.map((d) => d.textContent)).toEqual(["YES", "NO"]);
  expect(within(banner).getByText(/missing MRI origin/)).toBeTruthy();
  // jsdom has no WebGL: the scene degrades without hiding readiness.
  expect(await screen.findByText(/WebGL unavailable/)).toBeTruthy();
});

it("toggles layers and their opacity controls", async () => {
  stub();
  render(<HeadExplorer mode="demo" />);
  const scalp = await screen.findByLabelText("Show Scalp");
  expect(scalp).toBeChecked();
  expect(screen.getByLabelText("Show Inner skull")).not.toBeChecked();
  expect(screen.getByLabelText("Inner skull opacity")).toBeDisabled();
  fireEvent.click(scalp);
  expect(scalp).not.toBeChecked();
  expect(screen.getByLabelText("Scalp opacity")).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Brain / cortex opacity"), {
    target: { value: "0.9" },
  });
  expect(screen.getByLabelText("Brain / cortex opacity")).toHaveValue("0.9");
  expect(screen.getByText("EEG sensors (1)")).toBeTruthy();
  expect(screen.getByText("Cortical sources (2)")).toBeTruthy();
});

it("renders the uncertainty overlay legend and the selected interval", async () => {
  const fetch = stub();
  render(<HeadExplorer mode="demo" />);
  await screen.findByLabelText("Colour sources by");
  expect(screen.getByText("synthetic activation")).toBeTruthy();
  expect(fetch).toHaveBeenCalledTimes(1);
  fireEvent.change(screen.getByLabelText("Colour sources by"), {
    target: { value: "mean" },
  });
  const legend = await screen.findByRole("figure", {
    name: "Localisation error · mean legend",
  });
  expect(within(legend).getByText("MOCK FIXTURE")).toBeTruthy();
  expect(within(legend).getByText("5.00 mm")).toBeTruthy();
  expect(within(legend).getByText("12.00 mm")).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Selected head-model source"), {
    target: { value: "1" },
  });
  expect(screen.getByText(/12\.0 mm \[7\.8, 19\.2\] · 95% CI/)).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Colour sources by"), {
    target: { value: "width" },
  });
  expect(
    await screen.findByRole("figure", {
      name: "Localisation error · 95% CI width legend",
    }),
  ).toBeTruthy();
});

it("rejects a misaligned overlay instead of colouring sources with it", async () => {
  stub(scene, { ...overlay, n_sources: 3, mean: [1, 2, 3] });
  render(<HeadExplorer mode="demo" />);
  fireEvent.change(await screen.findByLabelText("Colour sources by"), {
    target: { value: "mean" },
  });
  expect(
    await screen.findByText(/does not match the source space/),
  ).toBeTruthy();
});

it("rejects a head scene claiming anatomical validation or private MRI", async () => {
  stub({ ...scene, anatomically_validated: true, readiness: "VALIDATED" });
  render(<HeadExplorer mode="demo" />);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Unsupported head scene contract",
  );
});

it("does not request any head geometry in local mode", () => {
  const fetch = stub();
  render(<HeadExplorer mode="local" />);
  expect(fetch).not.toHaveBeenCalled();
  expect(screen.getByText(/opt-in, loopback-only M32/)).toBeTruthy();
  expect(screen.getByText("NOT ASSESSED")).toBeTruthy();
});

it("never displays an anatomical-validation claim without VALIDATED readiness", () => {
  render(
    <ReadinessBanner
      readiness="QC_ONLY"
      geometricallyValid
      anatomicallyValidated
    />,
  );
  const banner = screen.getByRole("region", { name: "Head model readiness" });
  expect(within(banner).getByText("QC_ONLY")).toBeTruthy();
  expect(
    within(banner)
      .getAllByRole("definition")
      .map((d) => d.textContent),
  ).toEqual(["YES", "NO"]);
});
