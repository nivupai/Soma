import { expect, it } from "vitest";
import type { SourceUncertaintyOverlay } from "../api/client";
import {
  colorsFor,
  overlayValues,
  rampColor,
  readinessLabel,
  scalarRange,
  validateOverlay,
} from "./headColor";

const overlay: SourceUncertaintyOverlay = {
  contract: "soma.explorer.source-uncertainty-overlay/1",
  head_id: "demo-synthetic-head",
  quantity: "localisation_error",
  units: "mm",
  statistic: "mean",
  interval: "confidence_interval",
  confidence_level: 0.95,
  n_sources: 2,
  mean: [5, 10],
  lower: [3, 6],
  upper: [8, 16],
  origin: "MOCK_FIXTURE",
  fixture: true,
  warnings: [],
};

it("maps scalars monotonically onto the ramp and clamps out-of-range values", () => {
  expect(rampColor(-1)).toEqual(rampColor(0));
  expect(rampColor(2)).toEqual(rampColor(1));
  expect(rampColor(Number.NaN)).toEqual(rampColor(0));
  // The red channel rises along the ramp.
  expect(rampColor(1)[0]).toBeGreaterThan(rampColor(0)[0]);
  expect(colorsFor([0, 5, 10], [0, 10])).toHaveLength(9);
  expect(colorsFor([10], [0, 10])).toEqual(rampColor(1));
});

it("computes a finite non-degenerate range", () => {
  expect(scalarRange([3, Number.NaN, 1, 2])).toEqual([1, 3]);
  expect(scalarRange([4, 4])).toEqual([4, 5]);
  expect(scalarRange([])).toEqual([0, 1]);
});

it("never upgrades unknown readiness", () => {
  expect(readinessLabel("QC_ONLY_ANATOMY")).toBe("QC_ONLY");
  expect(readinessLabel("VALIDATED_ANATOMY")).toBe("VALIDATED");
  expect(readinessLabel("NOT_READY_FOR_FORWARD_MODEL")).toBe("NOT_READY");
  expect(readinessLabel("SOMETHING_NEW")).toBe("NOT_READY");
  expect(readinessLabel(undefined)).toBe("NOT_READY");
});

it("validates uncertainty overlays against the source space", () => {
  expect(validateOverlay(overlay, 2)).toBeNull();
  expect(validateOverlay(overlay, 3)).toMatch(/does not match/);
  expect(validateOverlay({ ...overlay, lower: [6, 6] }, 2)).toMatch(
    /Invalid interval at source 0/,
  );
  expect(validateOverlay({ ...overlay, origin: "M34_RESULT" }, 2)).toMatch(
    /Fixture flag/,
  );
  expect(overlayValues(overlay, "mean")).toEqual([5, 10]);
  expect(overlayValues(overlay, "width")).toEqual([5, 10]);
});
