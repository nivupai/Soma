import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import type { HeadLayerName, HeadSceneData } from "../api/client";
import { colorsFor } from "./headColor";

export type LayerSettings = Record<
  HeadLayerName,
  { visible: boolean; opacity: number }
>;

export const LAYER_COLORS: Record<HeadLayerName, number> = {
  scalp: 0xd8b49a,
  outer_skull: 0xece5d3,
  inner_skull: 0xbfb6a0,
  cortex: 0xd98f95,
};

export const DEFAULT_LAYERS: LayerSettings = {
  scalp: { visible: true, opacity: 0.18 },
  outer_skull: { visible: true, opacity: 0.22 },
  inner_skull: { visible: false, opacity: 0.3 },
  cortex: { visible: true, opacity: 0.55 },
};

// Inner layers are drawn first so translucent outer shells blend over them.
const RENDER_ORDER: Record<HeadLayerName, number> = {
  cortex: 0,
  inner_skull: 1,
  outer_skull: 2,
  scalp: 3,
};

/** Nested head layers, EEG sensors and scalar-coloured sources in three.js. */
export default function HeadScene({
  scene: data,
  layers,
  showSensors,
  showSources,
  sourceValues,
  range,
  selected,
  onSelect,
}: {
  scene: HeadSceneData;
  layers: LayerSettings;
  showSensors: boolean;
  showSources: boolean;
  sourceValues: number[];
  range: [number, number];
  selected: number;
  onSelect: (index: number) => void;
}) {
  const host = useRef<HTMLDivElement>(null);
  const render = useRef<() => void>(() => {});
  const objects = useRef<{
    layers: Partial<Record<HeadLayerName, THREE.Mesh>>;
    sensors?: THREE.Points;
    sources?: THREE.Points;
    marker?: THREE.Mesh;
  }>({ layers: {} });
  const [error, setError] = useState("");
  useEffect(() => {
    const el = host.current;
    if (!el) return;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch {
      setError(
        "WebGL unavailable. Readiness, layer metadata and source values remain available below.",
      );
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    el.appendChild(renderer.domElement);
    renderer.domElement.setAttribute("aria-label", "Interactive 3D head");
    renderer.domElement.setAttribute("role", "img");
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(36, 1, 1, 5000);
    camera.up.set(0, 0, 1);
    const span =
      2.2 * Math.max(...data.layers[0].vertices_mm.flat().map(Math.abs), 50);
    camera.position.set(span * 0.8, -span * 0.95, span * 0.55);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0, 0, 0);
    controls.enableDamping = false;
    controls.update();
    scene.add(new THREE.AmbientLight(0xffffff, 1.4));
    const light = new THREE.DirectionalLight(0xffffff, 2.4);
    light.position.set(150, -120, 220);
    scene.add(light);
    const layerObjects: Partial<Record<HeadLayerName, THREE.Mesh>> = {};
    for (const layer of data.layers) {
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute(
        "position",
        new THREE.Float32BufferAttribute(layer.vertices_mm.flat(), 3),
      );
      geometry.setIndex(layer.faces.flat());
      geometry.computeVertexNormals();
      const mesh = new THREE.Mesh(
        geometry,
        new THREE.MeshStandardMaterial({
          color: LAYER_COLORS[layer.name],
          roughness: 0.8,
          transparent: true,
          side: THREE.DoubleSide,
          depthWrite: false,
        }),
      );
      mesh.renderOrder = RENDER_ORDER[layer.name];
      mesh.name = layer.name;
      scene.add(mesh);
      layerObjects[layer.name] = mesh;
    }
    const sensorGeometry = new THREE.BufferGeometry();
    sensorGeometry.setAttribute(
      "position",
      new THREE.Float32BufferAttribute(
        data.sensors.flatMap((s) => s.position_mm),
        3,
      ),
    );
    // Markers join the transparent pass so renderOrder draws them after the
    // translucent shells instead of being washed out underneath them.
    const sensors = new THREE.Points(
      sensorGeometry,
      new THREE.PointsMaterial({
        size: 9,
        color: 0x85b8ec,
        transparent: true,
      }),
    );
    sensors.renderOrder = 10;
    scene.add(sensors);
    const sourceGeometry = new THREE.BufferGeometry();
    sourceGeometry.setAttribute(
      "position",
      new THREE.Float32BufferAttribute(data.sources.positions_mm.flat(), 3),
    );
    sourceGeometry.setAttribute(
      "color",
      new THREE.Float32BufferAttribute(
        new Array(data.sources.positions_mm.length * 3).fill(0.5),
        3,
      ),
    );
    const sources = new THREE.Points(
      sourceGeometry,
      new THREE.PointsMaterial({
        size: 8,
        vertexColors: true,
        transparent: true,
      }),
    );
    sources.renderOrder = 11;
    scene.add(sources);
    const marker = new THREE.Mesh(
      new THREE.SphereGeometry(3, 12, 12),
      new THREE.MeshBasicMaterial({ color: 0xffd288, transparent: true }),
    );
    marker.renderOrder = 12;
    scene.add(marker);
    objects.current = { layers: layerObjects, sensors, sources, marker };
    const draw = () => renderer.render(scene, camera);
    render.current = draw;
    controls.addEventListener("change", draw);
    const resize = new ResizeObserver(() => {
      const w = el.clientWidth,
        h = el.clientHeight;
      renderer.setSize(w, h);
      camera.aspect = w / Math.max(1, h);
      camera.updateProjectionMatrix();
      draw();
    });
    resize.observe(el);
    const ray = new THREE.Raycaster();
    ray.params.Points = { threshold: 4 };
    let down = [0, 0];
    const pointerDown = (e: PointerEvent) => {
      down = [e.clientX, e.clientY];
    };
    const pick = (e: PointerEvent) => {
      if (!sources.visible) return;
      if (Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 5) return;
      const r = renderer.domElement.getBoundingClientRect();
      ray.setFromCamera(
        new THREE.Vector2(
          (2 * (e.clientX - r.left)) / r.width - 1,
          1 - (2 * (e.clientY - r.top)) / r.height,
        ),
        camera,
      );
      const hit = ray.intersectObject(sources)[0];
      if (hit?.index !== undefined) onSelect(hit.index);
    };
    renderer.domElement.addEventListener("pointerdown", pointerDown);
    renderer.domElement.addEventListener("pointerup", pick);
    draw();
    return () => {
      resize.disconnect();
      controls.dispose();
      renderer.domElement.removeEventListener("pointerdown", pointerDown);
      renderer.domElement.removeEventListener("pointerup", pick);
      scene.traverse((object) => {
        if (object instanceof THREE.Mesh || object instanceof THREE.Points) {
          object.geometry.dispose();
          (Array.isArray(object.material)
            ? object.material
            : [object.material]
          ).forEach((m) => m.dispose());
        }
      });
      renderer.dispose();
      renderer.forceContextLoss();
      renderer.domElement.remove();
      objects.current = { layers: {} };
      render.current = () => {};
    };
  }, [data, onSelect]);
  useEffect(() => {
    for (const [name, mesh] of Object.entries(objects.current.layers)) {
      const s = layers[name as HeadLayerName];
      mesh.visible = s.visible && s.opacity > 0;
      const material = mesh.material as THREE.MeshStandardMaterial;
      material.opacity = s.opacity;
      material.depthWrite = s.opacity >= 0.99;
    }
    if (objects.current.sensors) objects.current.sensors.visible = showSensors;
    if (objects.current.sources) objects.current.sources.visible = showSources;
    render.current();
  }, [layers, showSensors, showSources, data]);
  useEffect(() => {
    const sources = objects.current.sources;
    if (!sources || sourceValues.length !== data.sources.positions_mm.length)
      return;
    const color = sources.geometry.getAttribute(
      "color",
    ) as THREE.BufferAttribute;
    color.set(colorsFor(sourceValues, range));
    color.needsUpdate = true;
    render.current();
  }, [sourceValues, range, data]);
  useEffect(() => {
    const marker = objects.current.marker;
    const p = data.sources.positions_mm[selected];
    if (marker && p) {
      marker.position.fromArray(p);
      marker.visible = showSources;
      render.current();
    }
  }, [selected, data, showSources]);
  return (
    <div className="brain-scene head-scene" ref={host}>
      {error && (
        <div className="empty" role="alert">
          {error}
        </div>
      )}
      <span className="scene-axis">R / A / S · {data.frame} · mm</span>
      <span className="scene-hint">
        Drag to orbit · scroll to zoom · right-drag to pan · click a source
      </span>
    </div>
  );
}
