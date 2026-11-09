import { test, expect } from "@playwright/test";
import { writeFileSync } from "node:fs";
test("measure representative synthetic browser interactions", async ({
  page,
  browserName,
}) => {
  const metrics: Record<string, number | string | null> = {
    browser: browserName,
  };
  const start = Date.now();
  await page.goto("/");
  await expect(
    page.getByRole("img", { name: "Synthetic C3 EEG overview" }),
  ).toBeVisible();
  metrics.overview_ready_ms = Date.now() - start;
  for (const [name, target] of [
    ["EEG Laboratory", "Power spectral density"],
    ["MRI Anatomy", "axial MRI slice"],
    ["Source Models", "Interactive anatomical geometry"],
  ] as const) {
    const t = Date.now();
    await page.getByRole("button", { name, exact: true }).click();
    await expect(page.getByRole("img", { name: target })).toBeVisible();
    metrics[`${name}_ready_ms`] = Date.now() - t;
    if (name === "MRI Anatomy") {
      const t = Date.now();
      const before = await page.getByTestId("world-coordinates").textContent();
      await page.getByLabel("Voxel I", { exact: true }).fill("7");
      await expect(page.getByTestId("world-coordinates")).not.toHaveText(
        before!,
      );
      metrics.MRI_navigation_ms = Date.now() - t;
    }
    if (name === "Source Models") {
      const t = Date.now();
      await page.getByLabel("Source index").fill("5");
      await expect(page.locator(".coordinate-bar")).toContainText("Source 5");
      await expect(
        page.getByRole("img", { name: "Source time course" }),
      ).toBeVisible();
      metrics.source_selection_ms = Date.now() - t;
      const canvas = page.getByRole("img", {
        name: "Interactive anatomical geometry",
      });
      const box = await canvas.boundingBox();
      if (box) {
        const t = Date.now();
        await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
        await page.mouse.down();
        await page.mouse.move(
          box.x + box.width * 0.65,
          box.y + box.height * 0.55,
          { steps: 12 },
        );
        await page.mouse.up();
        metrics.orbit_12_steps_ms = Date.now() - t;
      }
    }
  }
  metrics.JS_heap_used_bytes = await page.evaluate(
    () =>
      (performance as Performance & { memory?: { usedJSHeapSize: number } })
        .memory?.usedJSHeapSize ?? null,
  );
  metrics.animation_frame_median_ms = await page.evaluate(async () => {
    const xs: number[] = [];
    let last = performance.now();
    for (let i = 0; i < 20; i++) {
      await new Promise<void>((r) => requestAnimationFrame(() => r()));
      const now = performance.now();
      xs.push(now - last);
      last = now;
    }
    return xs.sort((a, b) => a - b)[10];
  });
  metrics.scope =
    "Headless Chromium synthetic views; wall-clock UI readiness, not scientific numerical runtime; heap is renderer process estimate";
  if (process.env.BENCHMARK_EXPLORER === "1")
    writeFileSync(
      "../../experiments/milestone15/browser-performance.json",
      JSON.stringify(metrics, null, 2) + "\n",
    );
  expect(metrics.MRI_navigation_ms).toBeGreaterThanOrEqual(0);
});
