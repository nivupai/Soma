import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { Diagram, reachable, type WorkflowGraph } from "./Workflows";
vi.mock("@xyflow/react", () => ({
  ReactFlow: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  Background: () => null,
  Controls: () => <button>Fit workflow to view</button>,
  MiniMap: () => null,
  MarkerType: { ArrowClosed: "arrow" },
  Position: { Right: "right", Left: "left" },
}));
afterEach(cleanup);
const graph: WorkflowGraph = {
  id: "g",
  status: "FAILED",
  environment: { python: "3.12" },
  limitations: ["Numerical lineage only"],
  nodes: [
    {
      id: "input",
      node_type: "artifact",
      position: { x: 0, y: 0 },
      data: {
        label: "input",
        status: "NOT_RUN",
        cache: "NOT_ASSESSED",
        validation: "DECLARATIONS_ONLY",
        runtime_s: null,
        reason: null,
        metadata: { kind: "mri.intensity" },
      },
    },
    {
      id: "stage",
      node_type: "stage",
      position: { x: 200, y: 0 },
      data: {
        label: "stage",
        status: "FAILED",
        cache: "RECORDED_MISS",
        validation: "NOT_RUN",
        runtime_s: 0.25,
        reason: "Corrupt cache",
        metadata: {
          implementation: "registered",
          parameters: { threshold: 1 },
        },
      },
    },
    {
      id: "output",
      node_type: "artifact",
      position: { x: 400, y: 0 },
      data: {
        label: "output",
        status: "NOT_RUN",
        cache: "NOT_ASSESSED",
        validation: "DECLARATIONS_ONLY",
        runtime_s: null,
        reason: null,
        metadata: {},
      },
    },
  ],
  edges: [
    { id: "a", source: "input", target: "stage" },
    { id: "b", source: "stage", target: "output" },
  ],
};
describe("workflow inspection", () => {
  it("traverses both lineage directions without unrelated nodes", () => {
    expect([...reachable(graph, "stage", false)].sort()).toEqual([
      "input",
      "stage",
    ]);
    expect([...reachable(graph, "stage", true)].sort()).toEqual([
      "output",
      "stage",
    ]);
  });
  it("selects stage metadata with accessible buttons and explains failures", () => {
    render(<Diagram graph={graph} />);
    fireEvent.click(screen.getByRole("button", { name: "stage · stage" }));
    expect(
      screen.getByRole("region", { name: "Selected workflow node" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Corrupt cache")).toBeInTheDocument();
    expect(screen.getByText(/0.2500 s/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Lineage direction"), {
      target: { value: "downstream" },
    });
    expect(screen.getByText(/downstream: stage → output/)).toBeInTheDocument();
  });
  it("filters keyboard navigator without executing science", () => {
    render(<Diagram graph={graph} />);
    fireEvent.change(screen.getByLabelText("Find workflow node"), {
      target: { value: "stage" },
    });
    expect(
      screen.queryByRole("button", { name: "artifact · input" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "stage · stage" }),
    ).toBeInTheDocument();
  });
});
