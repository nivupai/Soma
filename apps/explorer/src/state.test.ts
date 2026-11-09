import { describe, it, expect } from "vitest";
import { initial, reducer } from "./state";
describe("scientific selection isolation", () => {
  it("resets trial, channels, voxel and source on dataset switches", () => {
    const state = {
      ...initial,
      dataset: "first",
      start: 22,
      channels: ["C3"],
      voxel: [3, 4, 5],
      source: 12,
    };
    const next = reducer(state, { type: "dataset", id: "second" });
    expect(next).toEqual({ ...initial, dataset: "second" });
  });
  it("resets related panels when a trial window changes", () => {
    expect(
      reducer(initial, { type: "window", start: 8, duration: 10 }),
    ).toMatchObject({ start: 8, duration: 10 });
  });
  it("never carries local selections into demo mode", () => {
    expect(
      reducer(
        { ...initial, dataset: "private", mode: "local", source: 5 },
        { type: "mode", mode: "demo" },
      ),
    ).toEqual(initial);
  });
  it("updates one shared voxel for all MRI planes", () => {
    expect(reducer(initial, { type: "voxel", voxel: [2, 5, 8] }).voxel).toEqual(
      [2, 5, 8],
    );
  });
  it("clears subjects and source state on laboratory navigation", () => {
    expect(
      reducer(
        { ...initial, dataset: "local", source: 9 },
        { type: "page", page: "MRI Anatomy" },
      ),
    ).toEqual({ ...initial, page: "MRI Anatomy" });
  });
});
