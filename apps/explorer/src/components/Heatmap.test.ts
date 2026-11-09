import { describe, it, expect } from "vitest";
import { heatColor } from "./Heatmap";
describe("scientific color semantics", () => {
  it("retains positive/negative design-regressor sign", () => {
    const positive = heatColor(1, -1, 1, "signed"),
      negative = heatColor(-1, -1, 1, "signed");
    expect(positive[0]).toBeGreaterThan(positive[1]);
    expect(negative[1]).toBeGreaterThan(negative[0]);
    expect(positive).not.toEqual(negative);
  });
  it("keeps zero neutral on a signed shared scale", () => {
    expect(heatColor(0, -2, 2, "signed")).toEqual([18, 28, 38, 255]);
    expect(heatColor(0.5, -2, 2, "signed")[0]).toBeLessThan(
      heatColor(1, -2, 2, "signed")[0],
    );
  });
  it("power color is ordered by positive logarithmic magnitude", () => {
    expect(heatColor(1e-12, -12, -9, "power")[0]).toBeLessThan(
      heatColor(1e-9, -12, -9, "power")[0],
    );
  });
});
