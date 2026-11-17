import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import BEMDiagnostics from "./BEMDiagnostics";
const levels = [1, 2, 3].map((level) => ({
  level,
  relative: 0.36 / level,
  alignment_scalar: 0.9,
  aligned_residual: 0.05,
  source_relative: [0.1, 0.2],
  geometry_match: true,
  sensor_reference_match: true,
  openmeeg_error: 0.03 / level,
  mne_error: 0.02 / level,
}));
const report = {
  schema: "soma.bem-diagnostic.explorer/1",
  synthetic_only: true,
  human_subjects: 0,
  threshold: 0.1,
  solver_pair: "OpenMEEG / MNE",
  heads: [
    { head: 0, levels },
    { head: 5, levels },
  ],
  controls: [
    { reference: "A", levels },
    { reference: "B", levels },
  ],
};
afterEach(() => vi.unstubAllGlobals());
it("keeps physical discrepancy and diagnostics separate across reference controls", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, json: async () => report })),
  );
  render(<BEMDiagnostics />);
  expect(await screen.findByText("12.00%")).toBeInTheDocument();
  expect(screen.getByText(/AGREEMENT NOT ESTABLISHED/)).toBeInTheDocument();
  expect(
    screen.getByRole("img", { name: "BEM off-grid source error plot" }),
  ).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("BEM synthetic head"), {
    target: { value: "5" },
  });
  fireEvent.change(screen.getByLabelText("BEM physical reference"), {
    target: { value: "A" },
  });
  fireEvent.change(screen.getByLabelText("BEM solver comparison"), {
    target: { value: "MNE" },
  });
  expect(screen.getByText("0.67%")).toBeInTheDocument();
  expect(
    screen.getByText(/Analytical acceptance is a separate 2%/),
  ).toBeInTheDocument();
});
it("withholds a modified target or private data claim", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      json: async () => ({ ...report, threshold: 0.2 }),
    })),
  );
  render(<BEMDiagnostics />);
  expect(
    await screen.findByText(/Unverified BEM identity or modified threshold/),
  ).toBeInTheDocument();
  expect(
    screen.queryByLabelText("BEM physical reference"),
  ).not.toBeInTheDocument();
});
