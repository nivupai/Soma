import { useEffect, useRef } from "react";
export function heatColor(
  value: number,
  min: number,
  max: number,
  mode: "power" | "signed",
): number[] {
  if (mode === "signed") {
    const q = Math.max(
      -1,
      Math.min(1, value / (Math.max(Math.abs(min), Math.abs(max)) || 1)),
    );
    const color = q < 0 ? [70, 195, 190] : [235, 180, 100];
    return [
      18 + Math.abs(q) * (color[0] - 18),
      28 + Math.abs(q) * (color[1] - 28),
      38 + Math.abs(q) * (color[2] - 38),
      255,
    ];
  }
  const q = (Math.log10(Math.max(1e-30, value)) - min) / (max - min || 1);
  return [15 + 220 * q, 30 + 150 * q, 50 + 50 * q, 255];
}
export function Heatmap({
  values,
  label,
  mode = "power",
}: {
  values: number[][];
  label: string;
  mode?: "power" | "signed";
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = canvas.current;
    if (!c || !values.length || !values[0].length) return;
    const h = values.length,
      w = values[0].length;
    c.width = w;
    c.height = h;
    const ctx = c.getContext("2d");
    if (!ctx) return;
    const a = values
      .flat()
      .map((v) => (mode === "power" ? Math.log10(Math.max(1e-30, v)) : v));
    const min = Math.min(...a),
      max = Math.max(...a);
    const img = ctx.createImageData(w, h);
    for (let y = 0; y < h; y++)
      for (let x = 0; x < w; x++) {
        const row = mode === "signed" ? y : h - 1 - y;
        img.data.set(
          heatColor(values[y][x], min, max, mode),
          (row * w + x) * 4,
        );
      }
    ctx.putImageData(img, 0, 0);
  }, [values, mode]);
  return (
    <canvas className="heatmap" ref={canvas} aria-label={label} role="img" />
  );
}
