import { render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import SourceUncertainty from "./SourceUncertainty";
afterEach(() => vi.unstubAllGlobals());
const report = {
  schema: "soma.source-uncertainty.explorer/1",
  synthetic_only: true,
  human_subjects: 0,
  protocol_fingerprint: "frozen-protocol",
  configurations: 49,
  failed_configurations: ["failed-geometry"],
  warning:
    "Simulated spherical geometry; not empirically verified human cortical activity.",
  examples: [
    {
      scenario: "conductivity-0.01",
      family: "conductivity",
      method: "MNE",
      grid_mm: [
        [0, 0, 0],
        [10, 0, 0],
      ],
      truth_mm: [5, 0, 0],
      baseline: [1, 0.5],
      perturbed: [0.5, 1],
      units: "A m",
      metrics: {
        localization_mm: 5,
        dispersion_mm: 7,
        nearest_grid_mm: 5,
        peak_amplitude_bias_ratio: -0.5,
      },
    },
  ],
};
it("shows actual synthetic truth, paired maps, 3D metrics and failures", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, json: async () => report })),
  );
  render(<SourceUncertainty />);
  expect(
    await screen.findByText(/Simulated spherical geometry/),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("img", { name: "Baseline source estimate" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("img", { name: "Perturbed source estimate" }),
  ).toBeInTheDocument();
  expect(
    screen.getByText("Numerical failures retained: 1 / 49"),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/Selected error source: conductivity/),
  ).toBeInTheDocument();
});
it("rejects a result relabeled as human validation", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      json: async () => ({ ...report, synthetic_only: false }),
    })),
  );
  render(<SourceUncertainty />);
  expect(
    await screen.findByText(/Unverified uncertainty artifact/),
  ).toBeInTheDocument();
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
});
