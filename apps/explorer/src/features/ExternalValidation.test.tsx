import { render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import ExternalValidation from "./ExternalValidation";
afterEach(() => vi.unstubAllGlobals());
it("keeps unapproved acquisition and incompatible frozen inference blocked", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => ({
      ok: true,
      json: async () =>
        url.endsWith("/external-validations")
          ? [{ id: "demo-external-validation", label: "Audit" }]
          : {
              schema: "soma.external-validation/1",
              status: "BLOCKED",
              dataset: "bnci2014-001",
              release_id: "authentic-v24",
              synthetic_only: false,
              mode: "HARMONIZED_FROZEN",
              scientific_compatibility: "NOT_COMPARABLE",
              acquisition_status: "BLOCKED",
              human_external_subjects: 0,
              human_external_sessions: 0,
              human_external_trials: 0,
              performance: [],
              domain_shift: { status: "METADATA_ONLY" },
              blockers: ["Explicit approval required"],
              refitted_components: 0,
            },
    })),
  );
  render(<ExternalValidation />);
  expect(
    await screen.findByText(/No external human accuracy is available/),
  ).toBeInTheDocument();
  expect(screen.getByText("Explicit approval required")).toBeInTheDocument();
  expect(
    screen.getByText(/Scientific feature compatibility: NOT_COMPARABLE/),
  ).toBeInTheDocument();
});
it("labels fictional outcomes explicitly", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => ({
      ok: true,
      json: async () =>
        url.endsWith("/external-validations")
          ? []
          : {
              schema: "soma.external-validation/1",
              status: "SYNTHETIC_COMPLETE",
              dataset: "synthetic-target-v25",
              release_id: "fictional",
              synthetic_only: true,
              mode: "EXACT_FROZEN",
              scientific_compatibility: "COMPATIBLE_SYNTHETIC_ONLY",
              acquisition_status: "SYNTHETIC_NO_DOWNLOAD",
              human_external_subjects: 0,
              human_external_sessions: 0,
              human_external_trials: 0,
              performance: [{ model: "dummy" }],
              domain_shift: { status: "SYNTHETIC_ONLY" },
              blockers: [],
              refitted_components: 0,
            },
    })),
  );
  render(<ExternalValidation />);
  expect(await screen.findByText(/SYNTHETIC TEST ONLY/)).toBeInTheDocument();
  expect(screen.getByText("Fictional numerical outcomes")).toBeInTheDocument();
});
