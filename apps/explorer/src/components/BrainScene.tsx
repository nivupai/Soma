import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import type { Mesh } from "../api/client";
export default function BrainScene({
  data,
  selected,
  onSelect,
  opacity,
  layers,
}: {
  data: Mesh;
  selected: number;
  onSelect: (n: number) => void;
  opacity: number;
  layers: string[];
}) {
  const host = useRef<HTMLDivElement>(null);
  const marker = useRef<THREE.Mesh | null>(null);
  const render = useRef<() => void>(() => {});
  const sceneObjects = useRef<Record<string, THREE.Object3D>>({});
  const [error, setError] = useState("");
  useEffect(() => {
    const el = host.current;
    if (!el) return;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch {
      setError(
        "WebGL unavailable. Source coordinates and time courses remain available below.",
      );
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    el.appendChild(renderer.domElement);
    renderer.domElement.setAttribute(
      "aria-label",
      "Interactive anatomical geometry",
    );
    renderer.domElement.setAttribute("role", "img");
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 10000);
    camera.up.set(0, 0, 1);
    const coords = [...data.vertices_mm, ...data.points_mm];
    const box = new THREE.Box3().setFromPoints(
      coords.map((v) => new THREE.Vector3(...(v as [number, number, number]))),
    );
    const center = box.isEmpty()
      ? new THREE.Vector3()
      : box.getCenter(new THREE.Vector3());
    const span = Math.max(30, box.getSize(new THREE.Vector3()).length());
    camera.position.copy(
      center
        .clone()
        .add(new THREE.Vector3(span * 1.2, -span * 1.5, span * 0.9)),
    );
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.copy(center);
    controls.enableDamping = false;
    controls.update();
    scene.add(new THREE.AmbientLight(0xffffff, 1.6));
    const light = new THREE.DirectionalLight(0xbde9ed, 3);
    light.position.set(100, -80, 150);
    scene.add(light);
    const surfaceGeometry = new THREE.BufferGeometry();
    surfaceGeometry.setAttribute(
      "position",
      new THREE.Float32BufferAttribute(data.vertices_mm.flat(), 3),
    );
    surfaceGeometry.setIndex(data.faces.flat());
    surfaceGeometry.computeVertexNormals();
    const hasActivation =
      data.vertices_mm.length === data.values.length && data.values.length > 0;
    if (hasActivation) {
      const peak = Math.max(...data.values, 1e-30);
      surfaceGeometry.setAttribute(
        "color",
        new THREE.Float32BufferAttribute(
          data.values.flatMap((value) => {
            const q = value / peak;
            return [0.2 + 0.8 * q, 0.65 - 0.2 * q, 0.65 - 0.4 * q];
          }),
          3,
        ),
      );
    }
    const material = new THREE.MeshStandardMaterial({
      color: hasActivation ? 0xffffff : 0x82a8b2,
      vertexColors: hasActivation,
      roughness: 0.85,
      transparent: true,
      opacity: 0.5,
      side: THREE.DoubleSide,
      depthWrite: false,
    });
    const surface = new THREE.Mesh(surfaceGeometry, material);
    scene.add(surface);
    const pointGeometry = new THREE.BufferGeometry();
    pointGeometry.setAttribute(
      "position",
      new THREE.Float32BufferAttribute(data.points_mm.flat(), 3),
    );
    const max = Math.max(...data.values, 1e-30);
    pointGeometry.setAttribute(
      "color",
      new THREE.Float32BufferAttribute(
        data.points_mm.flatMap((_, i) => {
          const q = (data.values[i] || 0) / max;
          return [0.2 + 0.8 * q, 0.65 - 0.2 * q, 0.65 - 0.4 * q];
        }),
        3,
      ),
    );
    const points = new THREE.Points(
      pointGeometry,
      new THREE.PointsMaterial({
        size: Math.max(1, span / 160),
        vertexColors: true,
      }),
    );
    scene.add(points);
    const sensorGeometry = new THREE.BufferGeometry();
    sensorGeometry.setAttribute(
      "position",
      new THREE.Float32BufferAttribute(data.electrode_points_mm.flat(), 3),
    );
    const electrodes = new THREE.Points(
      sensorGeometry,
      new THREE.PointsMaterial({ size: span / 90, color: 0x81bbf5 }),
    );
    scene.add(electrodes);
    const highlight = new THREE.Mesh(
      new THREE.SphereGeometry(span / 100, 12, 12),
      new THREE.MeshBasicMaterial({ color: 0xffd288 }),
    );
    scene.add(highlight);
    marker.current = highlight;
    sceneObjects.current = { surface, sources: points, electrodes };
    const axes = new THREE.AxesHelper(span / 4);
    axes.position.copy(
      center.clone().add(new THREE.Vector3(-span / 3, 0, -span / 3)),
    );
    scene.add(axes);
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
    ray.params.Points = { threshold: span / 70 };
    let down = [0, 0];
    const pointerDown = (e: PointerEvent) => {
      down = [e.clientX, e.clientY];
    };
    const select = (e: PointerEvent) => {
      if (Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 5) return;
      const r = renderer.domElement.getBoundingClientRect();
      ray.setFromCamera(
        new THREE.Vector2(
          (2 * (e.clientX - r.left)) / r.width - 1,
          1 - (2 * (e.clientY - r.top)) / r.height,
        ),
        camera,
      );
      const hit = ray.intersectObject(points)[0];
      if (hit?.index !== undefined) onSelect(hit.index);
    };
    renderer.domElement.addEventListener("pointerdown", pointerDown);
    renderer.domElement.addEventListener("pointerup", select);
    draw();
    return () => {
      resize.disconnect();
      controls.dispose();
      renderer.domElement.removeEventListener("pointerdown", pointerDown);
      renderer.domElement.removeEventListener("pointerup", select);
      scene.traverse((object) => {
        if (
          object instanceof THREE.Mesh ||
          object instanceof THREE.Points ||
          object instanceof THREE.Line
        ) {
          object.geometry.dispose();
          const materials = Array.isArray(object.material)
            ? object.material
            : [object.material];
          materials.forEach((m) => m.dispose());
        }
      });
      renderer.dispose();
      renderer.forceContextLoss();
      renderer.domElement.remove();
      marker.current = null;
      render.current = () => {};
    };
  }, [data, onSelect]);
  useEffect(() => {
    if (marker.current && data.points_mm[selected]) {
      marker.current.position.fromArray(data.points_mm[selected]);
      render.current();
    }
  }, [selected, data]);
  useEffect(() => {
    Object.entries(sceneObjects.current).forEach(([key, object]) => {
      object.visible = layers.includes(key);
      if (object instanceof THREE.Mesh)
        (object.material as THREE.MeshStandardMaterial).opacity = opacity;
    });
    render.current();
  }, [layers, opacity, data]);
  return (
    <div className="brain-scene" ref={host}>
      {error && (
        <div className="empty" role="alert">
          {error}
        </div>
      )}
      <span className="scene-axis">X / Y / Z · {data.frame} · mm</span>
      <span className="scene-hint">
        Drag to orbit · scroll to zoom · right-drag to pan · click a source
      </span>
    </div>
  );
}
