import { render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import HumanHeadModels from "./HumanHeadModels";
import report from "../../../../src/soma/resources/mri-head-models-example-v32.json";
afterEach(() => vi.unstubAllGlobals());
it("shows actual frozen failures without publishing local anatomical assets", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      json: async () => ({ ...report, local_views: [] }),
    })),
  );
  render(<HumanHeadModels />);
  expect(
    await screen.findByText(/0 validated conductor anatomies/),
  ).toBeTruthy();
  expect(screen.getByText("FAIL")).toBeTruthy();
  expect(screen.getByText("14.56%")).toBeTruthy();
  expect(screen.getByText(/No locally authorized MRI is enabled/)).toBeTruthy();
  expect(screen.queryByLabelText("Authorized local anatomy")).toBeNull();
});
it("rejects an unsupported human accuracy claim", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      json: async () => ({
        ...report,
        local_views: [],
        human_localization_accuracy: true,
      }),
    })),
  );
  render(<HumanHeadModels />);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Unsupported human anatomical evidence",
  );
});
