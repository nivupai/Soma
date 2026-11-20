import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import InverseCalibration from "./InverseCalibration";
const row = {
  grid: "nested2",
  candidates: 481,
  prior: "cell_volume",
  method: "MNE",
  policy: "spectral",
  noise_std_V: 5e-8,
  localization_mm: 24.95,
  localization_mm_lower: 21.1,
  localization_mm_upper: 29.1,
  excess_mm: 17.9,
  dispersion_mm: 40,
};
const report = {
  schema: "soma.inverse-calibration.explorer/1",
  synthetic_only: true,
  human_subjects: 0,
  design_sha256: "frozen",
  warning: "Synthetic study only; native portability is NOT established",
  summary: [row],
  source_metrics: [],
  examples: [],
  failures: [],
  receipt: {
    heads: 6,
    original_sources: 72,
    new_heldout_sources: 24,
    failed_configurations: 0,
  },
};
afterEach(() => vi.unstubAllGlobals());
it("uses frozen results and exposes prior controls and limitations", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, json: async () => report })),
  );
  render(<InverseCalibration />);
  expect(
    await screen.findByText(/481 candidates · peak error 24.95 mm/),
  ).toBeTruthy();
  expect(
    screen.getByText(/native portability is NOT established/),
  ).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Source prior"), {
    target: { value: "unweighted" },
  });
  expect(screen.getByText(/Computed held-out FEM results/)).toBeTruthy();
  expect(screen.getByLabelText("Source radial coordinate")).toBeTruthy();
});
it("rejects a human or unsupported result identity", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      json: async () => ({ ...report, human_subjects: 1 }),
    })),
  );
  render(<InverseCalibration />);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Unsupported synthetic inverse result",
  );
});
