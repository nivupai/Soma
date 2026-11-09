import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { Async, Evidence, Trace, useResource } from "./Common";
import { api } from "../api/client";
afterEach(() => vi.unstubAllGlobals());
describe("scientific interpretation and loading", () => {
  it("keeps warnings adjacent to exploratory results", () => {
    render(
      <Evidence
        result={{
          dataset_id: "demo",
          synthetic: true,
          state: "EXPLORATORY",
          warnings: ["Not anatomical truth"],
          provenance: {},
          data: {},
        }}
      />,
    );
    expect(screen.getByText("SYNTHETIC · EXPLORATORY")).toBeVisible();
    expect(screen.getByText("Not anatomical truth")).toBeVisible();
  });
  it("never renders an error as a successful viewer", () => {
    render(
      <Async error="Missing derivatives">
        <div>successful map</div>
      </Async>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Missing derivatives");
    expect(screen.queryByText("successful map")).toBeNull();
  });
  it("exposes accessible loading state", () => {
    render(
      <Async loading>
        <div>data</div>
      </Async>,
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading scientific data",
    );
  });
  it("renders actual unit-bearing traces", () => {
    render(<Trace x={[0, 1, 2]} y={[1, 2, 1]} label="EEG voltage V" />);
    expect(screen.getByRole("img", { name: "EEG voltage V" })).toBeVisible();
  });
  it("surfaces rejected API requests", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 409,
        json: async () => ({ detail: "Incompatible frames" }),
      }),
    );
    await expect(api("/compare")).rejects.toThrow("Incompatible frames");
  });
  it("does not reuse a previous dataset while a new one loads", async () => {
    let resolve: (v: unknown) => void = () => {};
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ id: "first" }),
        })
        .mockImplementationOnce(
          () =>
            new Promise((r) => {
              resolve = r;
            }),
        ),
    );
    function View({ id }: { id: string }) {
      const r = useResource<{ id: string }>(`/data/${id}`);
      return <div>{r.loading ? "pending" : r.data?.id}</div>;
    }
    const view = render(<View id="first" />);
    await waitFor(() => expect(screen.getByText("first")).toBeVisible());
    view.rerender(<View id="second" />);
    expect(screen.queryByText("first")).toBeNull();
    expect(screen.getByText("pending")).toBeVisible();
    resolve({ ok: true, json: async () => ({ id: "second" }) });
    await waitFor(() => expect(screen.getByText("second")).toBeVisible());
  });
});
