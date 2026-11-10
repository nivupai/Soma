import { useCallback, useMemo, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  MarkerType,
  Position,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Panel, Async, Json, Warning, useResource } from "../components/Common";

type Item = { id: string; label: string; status: string };
export type WorkflowGraph = {
  id: string;
  status: string;
  nodes: {
    id: string;
    node_type: "artifact" | "stage";
    position: { x: number; y: number };
    data: {
      label: string;
      status: string;
      cache: string;
      validation: string;
      runtime_s: number | null;
      reason: string | null;
      metadata: Record<string, unknown>;
    };
  }[];
  edges: { id: string; source: string; target: string }[];
  invalidation?: Record<string, unknown> | null;
  environment: Record<string, unknown>;
  limitations: string[];
};
export function reachable(
  graph: WorkflowGraph,
  node: string,
  downstream: boolean,
) {
  const found = new Set([node]);
  const todo = [node];
  const adjacency = new Map<string, string[]>();
  for (const edge of graph.edges) {
    const a = downstream ? edge.source : edge.target;
    const b = downstream ? edge.target : edge.source;
    adjacency.set(a, [...(adjacency.get(a) || []), b]);
  }
  while (todo.length)
    for (const other of adjacency.get(todo.pop()!) || []) {
      if (!found.has(other)) {
        found.add(other);
        todo.push(other);
      }
    }
  return found;
}
export function Diagram({ graph }: { graph: WorkflowGraph }) {
  const [selected, setSelected] = useState("");
  const onSelectionChange = useCallback(({ nodes }: { nodes: Node[] }) => {
    if (nodes[0]) setSelected(nodes[0].id);
  }, []);
  const [direction, setDirection] = useState<"upstream" | "downstream">(
    "upstream",
  );
  const [filter, setFilter] = useState("");
  const active = useMemo(
    () =>
      selected ? reachable(graph, selected, direction === "downstream") : null,
    [graph, selected, direction],
  );
  const nodes = useMemo<Node[]>(
    () =>
      graph.nodes.map((n) => ({
        id: n.id,
        position: n.position,
        type: "default",
        data: {
          label: `${n.node_type === "artifact" ? "ARTIFACT" : "STAGE"} · ${n.id}\n${n.data.status} · ${n.data.cache}`,
        },
        ariaLabel: `${n.node_type} ${n.id}, ${n.data.status}`,
        selected: n.id === selected,
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
        style: {
          width: 205,
          color: "#e3edf2",
          background: "#132028",
          fontSize: 12,
          lineHeight: 1.5,
          whiteSpace: "pre-line",
          borderRadius: n.node_type === "artifact" ? 24 : 6,
          border: `2px solid ${n.data.status === "FAILED" ? "#c2414b" : n.data.cache === "RECORDED_HIT" ? "#16865c" : n.node_type === "artifact" ? "#7364b2" : "#397c9a"}`,
          opacity: active && !active.has(n.id) ? 0.3 : 1,
        },
      })),
    [graph, active, selected],
  );
  const edges = useMemo(
    () =>
      graph.edges.map((e) => ({
        ...e,
        markerEnd: { type: MarkerType.ArrowClosed },
        style: {
          stroke:
            active && active.has(e.source) && active.has(e.target)
              ? "#16865c"
              : "#8796a5",
          strokeWidth: 2,
        },
      })),
    [graph, active],
  );
  const node = graph.nodes.find((n) => n.id === selected);
  return (
    <>
      <div className="toolbar">
        <label>
          Lineage direction{" "}
          <select
            aria-label="Lineage direction"
            value={direction}
            onChange={(e) =>
              setDirection(e.target.value as "upstream" | "downstream")
            }
          >
            <option value="upstream">Upstream ancestry</option>
            <option value="downstream">Downstream impact</option>
          </select>
        </label>
        <label>
          Find node{" "}
          <input
            aria-label="Find workflow node"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </label>
        <button onClick={() => setSelected("")}>Clear selection</button>
      </div>
      <p className="muted">
        Rounded artifacts · rectangular stages · green recorded cache hits · red
        failures. Cache observations require CLI verification before reuse.
      </p>
      <div
        style={{ height: 480, width: "100%", minWidth: 0 }}
        aria-label="Scientific provenance graph"
      >
        <ReactFlow
          nodes={nodes}
          edges={edges}
          fitView
          minZoom={0.001}
          maxZoom={2.5}
          nodesDraggable={false}
          nodesConnectable={false}
          deleteKeyCode={null}
          onNodeClick={(_, n) => setSelected(n.id)}
          onSelectionChange={onSelectionChange}
          onlyRenderVisibleElements
          ariaLabelConfig={{
            "controls.fitView.ariaLabel": "Fit workflow to view",
          }}
        >
          <Background />
          <Controls showInteractive={false} />
          <MiniMap
            pannable
            zoomable
            nodeColor="#397c9a"
            maskColor="rgba(10,18,25,0.65)"
            style={{ background: "#132028" }}
          />
        </ReactFlow>
      </div>
      <details>
        <summary>Keyboard node navigator ({graph.nodes.length} nodes)</summary>
        <div className="workflow-node-list">
          {graph.nodes
            .filter((n) => n.id.includes(filter))
            .map((n) => (
              <button
                key={n.id}
                aria-pressed={n.id === selected}
                onClick={() => setSelected(n.id)}
              >
                {n.node_type} · {n.id}
              </button>
            ))}
        </div>
      </details>
      {node && (
        <section aria-live="polite" aria-label="Selected workflow node">
          <h3>
            {node.node_type} · {node.id}
          </h3>
          <p>
            {node.data.validation} · {node.data.cache}
            {node.data.runtime_s != null
              ? ` · ${node.data.runtime_s.toFixed(4)} s`
              : ""}
          </p>
          {node.data.reason && <Warning>{node.data.reason}</Warning>}
          <p>
            {direction}: {[...(active || [])].join(" → ")}
          </p>
          <Json value={node.data.metadata} />
        </section>
      )}
      {graph.invalidation && (
        <details>
          <summary>Invalidation explanations</summary>
          <Json value={graph.invalidation} />
        </details>
      )}
      <details>
        <summary>Software provenance</summary>
        <Json value={graph.environment} />
      </details>
      {graph.limitations.map((s) => (
        <Warning key={s}>{s}</Warning>
      ))}
    </>
  );
}
export default function Workflows() {
  const list = useResource<Item[]>("/workflows");
  const [identity, setIdentity] = useState("demo-workflow-eeg");
  const graph = useResource<WorkflowGraph>(`/workflows/${identity}`);
  return (
    <Panel title="Scientific workflow lineage" eyebrow="PROVENANCE / READ ONLY">
      <label>
        Workflow{" "}
        <select
          aria-label="Select workflow"
          value={identity}
          onChange={(e) => setIdentity(e.target.value)}
        >
          {(list.data || []).map((item) => (
            <option key={item.id} value={item.id}>
              {item.label}
            </option>
          ))}
        </select>
      </label>
      <Async
        loading={list.loading || graph.loading}
        error={list.error || graph.error}
      >
        {graph.data && <Diagram key={identity} graph={graph.data} />}
      </Async>
    </Panel>
  );
}
