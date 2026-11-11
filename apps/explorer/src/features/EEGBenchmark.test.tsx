import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import EEGBenchmark from "./EEGBenchmark";
vi.mock("../components/Common", async (original) => {
  const actual = await original<typeof import("../components/Common")>();
  return {
    ...actual,
    useResource: (path: string) => ({
      loading: false,
      error: null,
      data:
        path === "/eeg-benchmarks"
          ? [{ id: "demo-eeg-benchmark", label: "Preview", synthetic: true }]
          : {
              status: "NOT_RUN",
              warnings: ["Historical reuse; no external replication"],
              variants: [],
            },
    }),
  };
});
afterEach(cleanup);
it("shows explicit missing evidence without invented model performance", () => {
  render(<EEGBenchmark />);
  expect(screen.getByText("NOT_RUN")).toBeVisible();
  expect(
    screen.getByText(/no performance or human inference is invented/),
  ).toBeVisible();
  expect(screen.queryByRole("table")).toBeNull();
  expect(screen.getByText(/Historical reuse/)).toBeVisible();
});
it("offers only receipt and prespecified analysis selection", () => {
  render(<EEGBenchmark />);
  expect(screen.getByLabelText("Select EEG benchmark")).toBeVisible();
  expect(screen.getByLabelText("EEG sensitivity")).toBeVisible();
  expect(screen.queryByRole("button")).toBeNull();
});
