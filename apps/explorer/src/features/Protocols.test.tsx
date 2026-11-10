import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import Protocols, { DriftPlot } from "./Protocols";
vi.mock("./Workflows", () => ({ Diagram: () => <div>Recorded lineage</div> }));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
describe("protocol evidence", () => {
  it("does not draw missing outcomes as zero drift", () => {
    render(<DriftPlot rows={[]} />);
    expect(
      screen.getByText(/Numerical equivalence is indeterminate/),
    ).toBeTruthy();
    expect(screen.queryByRole("img")).toBeNull();
  });
  it("labels plotted errors as selected summary evidence", () => {
    render(
      <DriftPlot
        rows={[
          {
            unit_id: "unit-1",
            maximum_absolute_error: 0.01,
            numerically_equivalent: false,
            equivalence_applicable: true,
            axes: ["effect"],
            units: ["1"],
            left_values: [0],
            right_values: [0.01],
            atol: 0.001,
            rtol: 0,
          },
        ]}
      />,
    );
    expect(
      screen.getByRole("img", { name: "Selected summary absolute drift" }),
    ).toBeTruthy();
    expect(screen.getByText(/not a significance test/)).toBeTruthy();
  });
  it("makes only read requests and reports absent history honestly", async () => {
    const fetcher = vi.fn(async (url: string, options?: RequestInit) => ({
      ok: options?.method === undefined,
      json: async () =>
        url.endsWith("/protocols")
          ? [{ id: "demo-protocol-eeg", label: "EEG", status: "LOCAL" }]
          : url.endsWith("/replays")
            ? []
            : {
                validation_receipt: {
                  external_preregistration_verified: false,
                },
              },
    }));
    vi.stubGlobal("fetch", fetcher);
    render(<Protocols />);
    expect(
      await screen.findByText(/No registered execution history/),
    ).toBeTruthy();
    expect(
      screen.getByText(/Local seals are not external preregistration/),
    ).toBeTruthy();
    expect(
      fetcher.mock.calls.every(
        ([, options]) => !(options as RequestInit | undefined)?.method,
      ),
    ).toBe(true);
  });
});
