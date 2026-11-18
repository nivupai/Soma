import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import MeshGrid from "./MeshGrid";
const report = {
  schema: "soma.mesh-grid.explorer/1",
  synthetic_only: true,
  human_subjects: 0,
  threshold: 0.1,
  mesher: "Gmsh4.15.2",
  receipt: { computed_fields: 85, failed_fields: 1, matched_finest_pass: true },
  comparisons: [],
  geometry: [],
  peaks: [],
  grid_summary: [
    {
      spacing_mm: 15,
      candidates: 341,
      method: "Tikhonov",
      solver: "fem",
      noise_std_V: 5e-8,
      localization_mm: 20,
      nearest_grid_mm: 7,
      excess_localization_mm: 13,
      localization_mm_lower: 15,
      localization_mm_upper: 25,
    },
  ],
};
afterEach(() => vi.unstubAllGlobals());
it("distinguishes actual error from the grid lower bound", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, json: async () => report })),
  );
  render(<MeshGrid />);
  expect(await screen.findByText("20.00")).toBeInTheDocument();
  expect(screen.getByText("7.00")).toBeInTheDocument();
  expect(screen.getByText(/Dense grids are not assumed/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Mesh grid head"), {
    target: { value: "5" },
  });
  expect(
    screen.getByRole("img", {
      name: "Source grid localization and nearest-distance curves",
    }),
  ).toBeInTheDocument();
});
it("withholds a false independence claim", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      json: async () => ({ ...report, mesher: "radial extrusion" }),
    })),
  );
  render(<MeshGrid />);
  expect(
    await screen.findByText(/Unverified mesh\/grid identity/),
  ).toBeInTheDocument();
});
