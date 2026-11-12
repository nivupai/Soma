import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import Nonspherical from "./Nonspherical";
const surface = {
  xyz_mm: [
    [0, 0, 0],
    [1, 0, 0],
    [0, 1, 0],
  ],
  faces: [[0, 1, 2]],
};
const head = {
  head: 0,
  family: "prolate",
  analysis_level: 2,
  display_level: 1,
  surfaces: [surface, surface, surface, surface],
  sensors_mm: [[0, 1, 0]],
  truth_mm: [0, 0, 0],
  grid_mm: [[1, 0, 0]],
  estimates: { MNE: [1], dSPM: [2], Tikhonov: [3] },
};
const report = {
  schema: "soma.nonspherical.explorer/1",
  synthetic_only: true,
  human_subjects: 0,
  heads: [head, { ...head, head: 1, family: "oblate" }],
  convergence: [
    { head: 0, status: "CONVERGED", errors: [0.6, 0.1, 0.02] },
    { head: 1, status: "NOT_CONVERGED", errors: [0.6, 0.2, 0.1] },
  ],
  failures: [{ head: 1, case: "mesh-2", reason: "solver divergence" }],
};
afterEach(() => vi.unstubAllGlobals());
it("keeps head selection, mesh graph, failure overlay and synthetic scope explicit", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, json: async () => report })),
  );
  render(<Nonspherical />);
  expect(
    await screen.findByRole("img", {
      name: "Synthetic conductor mesh and source distribution",
    }),
  ).toBeInTheDocument();
  expect(screen.getByText(/no human MRI accuracy/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Synthetic head"), {
    target: { value: "1" },
  });
  expect(screen.getByText("Head 1: NOT_CONVERGED")).toBeInTheDocument();
  expect(
    screen.getByText("1 failed configurations retained"),
  ).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Nonspherical method"), {
    target: { value: "dSPM" },
  });
  expect(
    screen.getByRole("img", { name: "Mesh convergence graph" }),
  ).toBeInTheDocument();
});
it("withholds an artifact relabeled as human or private", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      json: async () => ({ ...report, synthetic_only: false }),
    })),
  );
  render(<Nonspherical />);
  expect(
    await screen.findByText(/Unverified nonspherical artifact/),
  ).toBeInTheDocument();
  expect(screen.queryByLabelText("Synthetic head")).not.toBeInTheDocument();
});
