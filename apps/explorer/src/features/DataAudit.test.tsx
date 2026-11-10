import { afterEach, it, expect, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import DataAudit, { UnitTable } from "./DataAudit";
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
it("preserves absent sessions rather than inventing visit 1", () => {
  render(
    <UnitTable
      units={[
        {
          participant_key: "fiction:opaque",
          session: null,
          task: "structural",
          modality: "MRI",
          status: "BLOCKED",
          permission: "UNKNOWN",
          eligibility: "BLOCKED",
          missing_preprocessing: "unknown",
          deviations: [],
        },
      ]}
    />,
  );
  expect(screen.getByText("NOT PROVIDED")).toBeTruthy();
  expect(screen.queryByText("visit 1")).toBeNull();
});
it("keeps a research-data audit read-only", async () => {
  const get = vi.fn(async (url: string, options?: RequestInit) => ({
    ok: !options?.method,
    json: async () =>
      url.endsWith("/human-audits")
        ? [{ id: "demo-human-audit", label: "Fiction", synthetic: true }]
        : {
            dataset: "fixture",
            synthetic: true,
            status: "NOT_RUN",
            units: [],
            registration: { status: "NOT_PROVIDED" },
            warnings: ["No human evidence"],
          },
  }));
  vi.stubGlobal("fetch", get);
  render(<DataAudit />);
  expect(await screen.findByText("fixture")).toBeTruthy();
  expect(screen.getByText(/never executes an analysis/)).toBeTruthy();
  expect(get.mock.calls.every(([, o]) => !o?.method)).toBe(true);
});
