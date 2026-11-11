import { render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import ModelArchive from "./ModelArchive";
afterEach(() => vi.unstubAllGlobals());
it("keeps model archives distinct from human external accuracy", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => ({
      ok: true,
      json: async () =>
        url.endsWith("/model-archives")
          ? [{ id: "demo-model-archive", label: "Preview" }]
          : {
              schema: "soma.model-release-summary/1",
              status: "SYNTHETIC_INTERFACE_PREVIEW",
              release_id: null,
              protocol_fingerprint: null,
              training_cohort: "No human release selected",
              models: ["dummy"],
              fitted_state: "Select reviewed release",
              source_validation: null,
              external_acquisition: "EXTERNAL_DATA_ACQUISITION_BLOCKED",
              warnings: ["New state is not original M22"],
            },
    })),
  );
  render(<ModelArchive />);
  expect(
    await screen.findByText(/No human external accuracy is available/),
  ).toBeInTheDocument();
  expect(screen.getByText(/New state is not original M22/)).toBeInTheDocument();
  expect(
    screen.getByText(/EXTERNAL_DATA_ACQUISITION_BLOCKED/),
  ).toBeInTheDocument();
});
it("ignores unrelated legacy responses", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, json: async () => [] })),
  );
  render(<ModelArchive />);
  expect(
    await screen.findByText("Prospective EEG model archive"),
  ).toBeInTheDocument();
  expect(screen.queryByText(/Model archive:/)).not.toBeInTheDocument();
});
