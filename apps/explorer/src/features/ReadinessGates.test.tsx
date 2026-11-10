import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import ReadinessGates from "./ReadinessGates";
afterEach(cleanup);
it("keeps blocked evidence visible and distinct from scientific validity", () => {
  render(
    <ReadinessGates
      value={{
        status: "BLOCKED",
        bundle_integrity: "READY",
        interpretation: "Historical receipt; revalidate before use",
        gates: [
          {
            name: "content integrity",
            status: "READY",
            reasons: ["hashes match"],
            evidence: [],
          },
          {
            name: "preprocessing",
            status: "BLOCKED",
            reasons: ["Missing directed transforms"],
            evidence: [],
          },
          {
            name: "chronology",
            status: "INDETERMINATE",
            reasons: ["No source timing"],
            evidence: [],
          },
        ],
      }}
    />,
  );
  expect(
    screen.getByRole("table", { name: "Scientific readiness requirements" }),
  ).toHaveTextContent("BLOCKED");
  expect(screen.getByText("Missing directed transforms")).toBeVisible();
  expect(screen.getByText(/does not establish consent/)).toBeVisible();
});
it("does not render controls that run a pipeline or override a gate", () => {
  render(
    <ReadinessGates
      value={{
        status: "INDETERMINATE",
        bundle_integrity: "NOT_AVAILABLE",
        interpretation: "Synthetic fixture",
        gates: [],
      }}
    />,
  );
  expect(screen.queryByRole("button")).toBeNull();
  expect(screen.getByText(/NOT_AVAILABLE/)).toBeVisible();
});

it("shows repeated runs without inventing sessions", async () => {
  const { UnitTable } = await import("./DataAudit");
  render(
    <UnitTable
      units={[
        {
          participant_key: "fiction:one",
          session: null,
          run: "4",
          acquisition: null,
          task: "imagery",
          modality: "EEG",
          status: "NOT_EXECUTED",
          permission: "UNKNOWN",
          eligibility: "BLOCKED",
          missing_preprocessing: "unknown",
          deviations: [],
        },
      ]}
    />,
  );
  expect(
    screen.getByRole("table", { name: "Subject and session integrity" }),
  ).toHaveTextContent("4 / NOT PROVIDED");
  expect(screen.queryByText("visit 1")).toBeNull();
});

it("renders exactly one readiness panel inside Data Audit", async () => {
  const DataAudit = (await import("./DataAudit")).default;
  vi.stubGlobal("fetch", async (url: string) => ({
    ok: true,
    json: async () =>
      url.endsWith("/human-audits")
        ? [{ id: "demo-human-audit", label: "Fiction", synthetic: true }]
        : {
            dataset: "fixture",
            status: "NOT_RUN",
            synthetic: true,
            units: [],
            warnings: [],
            registration: { status: "NOT_AVAILABLE" },
            readiness: {
              status: "BLOCKED",
              bundle_integrity: "NOT_AVAILABLE",
              interpretation: "fixture",
              gates: [],
            },
          },
  }));
  try {
    render(<DataAudit />);
    await screen.findByRole("heading", {
      name: "Scientific readiness gates",
    });
    expect(
      screen.getAllByRole("heading", {
        name: "Scientific readiness gates",
      }),
    ).toHaveLength(1);
  } finally {
    vi.unstubAllGlobals();
  }
});
