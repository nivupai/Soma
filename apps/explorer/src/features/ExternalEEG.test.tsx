import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import ExternalEEG from "./ExternalEEG";
vi.mock("../components/Common", async (original) => {
  const a = await original<typeof import("../components/Common")>();
  return {
    ...a,
    useResource: (p: string) => ({
      loading: false,
      error: null,
      data:
        p === "/external-eeg"
          ? [{ id: "demo-external-eeg", label: "Audit" }]
          : {
              schema: "soma.external-eeg.audit/1",
              status: "BLOCKED",
              source_dataset: "eegmmidb",
              target_dataset: "bnci2014-001",
              license: "CC-BY-ND-4.0",
              permission_status: "AGGREGATE_EXPORT_UNRESOLVED",
              performance: [],
              model_compatibility: { original_m22_model_available: false },
              domain_shift: { status: "METADATA_ONLY" },
              warnings: [],
            },
    }),
  };
});
afterEach(cleanup);
it("keeps blocked execution and zero observed human coverage explicit", () => {
  render(<ExternalEEG />);
  expect(screen.getByText(/External audit: BLOCKED/)).toBeVisible();
  expect(screen.getByText(/0 subjects · 0 sessions · 0 trials/)).toBeVisible();
  expect(screen.getByText(/No human external decoding outcomes/)).toBeVisible();
  expect(screen.queryByRole("table")).toBeNull();
});
it("exposes evidence without download or permission override controls", () => {
  render(<ExternalEEG />);
  expect(screen.getByText(/AGGREGATE_EXPORT_UNRESOLVED/)).toBeVisible();
  expect(screen.getByText("Model and feature compatibility")).toBeVisible();
  expect(screen.queryByRole("button")).toBeNull();
});
