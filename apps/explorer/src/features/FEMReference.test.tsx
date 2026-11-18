import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import FEMReference from "./FEMReference";
const report = {
  schema: "soma.fem-reference.explorer/1",
  synthetic_only: true,
  human_subjects: 0,
  threshold: 0.1,
  heads: [
    { head: 0, level: 3, relative: 0.03, alpha: 0.99, aligned: 0.02 },
    { head: 5, level: 3, relative: 0.04, alpha: 0.98, aligned: 0.03 },
  ],
  source_fields: [],
  inverse: [],
  receipt: {
    models_computed: 62,
    models_failed: 1,
    analytical_limit_pass: true,
    independent_four_layer_agreement_pass: true,
  },
};
afterEach(() => vi.unstubAllGlobals());
it("keeps synthetic physical acceptance and diagnostic scaling separate", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, json: async () => report })),
  );
  render(<FEMReference />);
  expect(await screen.findByText("3.00%")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("FEM synthetic head"), {
    target: { value: "5" },
  });
  expect(screen.getByText("4.00%")).toBeInTheDocument();
  expect(screen.getByText(/Alignment is never applied/)).toBeInTheDocument();
  expect(
    screen.getByText(/does not establish human or phantom accuracy/),
  ).toBeInTheDocument();
});
it("rejects a changed threshold", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      json: async () => ({ ...report, threshold: 0.2 }),
    })),
  );
  render(<FEMReference />);
  expect(
    await screen.findByText(/Unverified FEM identity/),
  ).toBeInTheDocument();
  expect(screen.queryByLabelText("FEM synthetic head")).not.toBeInTheDocument();
});
