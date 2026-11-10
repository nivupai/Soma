import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Workbench from "./Workbench";
import { api } from "../api/client";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
const base = {
  id: "fixture",
  title: "Schema fixture",
  state: "EXPLORATORY",
  metrics: { value: 1 },
  parameters: {},
  compatibility: {},
  checksums: {},
  figures: [],
  warnings: [],
};
function serve(value: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: async () => [value] }),
  );
}
describe("versioned artifact presentation", () => {
  it("keeps schema and migration status visible without changing values", async () => {
    const value = {
      ...base,
      schema_name: "soma.result",
      schema_version: "1.1.0",
      validation_status: "FORMAT_AND_INTEGRITY_VERIFIED",
      migration_status: "MIGRATED_READ_ONLY",
    };
    serve(value);
    render(<Workbench datasets={[]} />);
    expect(await screen.findByText("Schema 1.1.0")).toBeVisible();
    expect(screen.getByText(/FORMAT_AND_INTEGRITY_VERIFIED/)).toHaveTextContent(
      "MIGRATED_READ_ONLY",
    );
    expect(value.metrics).toEqual({ value: 1 });
  });
  it("surfaces unsupported versions without inventing a figure", async () => {
    serve({
      ...base,
      state: "INVALID",
      schema_version: "99.0.0",
      validation_status: "UNSUPPORTED_VERSION",
      warnings: ["Unsupported schema; no numerical view permitted"],
    });
    render(<Workbench datasets={[]} />);
    expect(
      await screen.findByText(
        "Unsupported schema; no numerical view permitted",
      ),
    ).toBeVisible();
    expect(screen.queryByRole("img")).toBeNull();
  });
  it("marks historical unversioned results explicitly", async () => {
    serve(base);
    render(<Workbench datasets={[]} />);
    expect(await screen.findByText("Legacy / unversioned")).toBeVisible();
    expect(screen.getByText(/LEGACY_UNVERSIONED/)).toBeVisible();
  });
});

it("retains structured scientific incompatibility explanations", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      json: async () => ({
        detail: {
          scientific_compatibility: [
            {
              issues: [
                { field: "subject_identity", reason: "Different subjects" },
              ],
              unknown: [],
            },
          ],
        },
      }),
    }),
  );
  await expect(api("/experiments/compare")).rejects.toThrow(
    "subject_identity: Different subjects",
  );
});
