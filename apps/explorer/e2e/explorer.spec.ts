import { test, expect } from "@playwright/test";
import { mkdirSync } from "node:fs";
const capture = process.env.CAPTURE_EXPLORER === "1";
async function screenshot(page: import("@playwright/test").Page, name: string) {
  if (capture) {
    mkdirSync("../../docs/assets/explorer", { recursive: true });
    await expect(page.locator(".loading")).toHaveCount(0);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.evaluate(
      () =>
        new Promise<void>((resolve) =>
          requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
        ),
    );
    await page.screenshot({
      path: `../../docs/assets/explorer/${name}.png`,
      fullPage: true,
    });
  }
}
test("overview, real demo signals and coordinated trial selection", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Follow the signal." }),
  ).toBeVisible();
  await expect(
    page.getByRole("img", { name: "Synthetic C3 EEG overview" }),
  ).toBeVisible();
  await screenshot(page, "overview-dark");
  await page
    .getByRole("button", { name: "EEG Laboratory", exact: true })
    .click();
  await expect(page.getByRole("img", { name: "C3 EEG trace" })).toBeVisible();
  await expect(
    page.getByRole("img", { name: "Power spectral density" }),
  ).toBeVisible();
  await expect(
    page.getByRole("img", { name: "Morlet time frequency power" }),
  ).toBeVisible();
  await page.getByRole("button", { name: /20.0 s synthetic right/ }).click();
  await expect(page.getByLabel("Recording position")).toHaveValue("18");
  await screenshot(page, "eeg-dark");
  expect(errors).toEqual([]);
});
test("MRI crosshairs, orientation and label controls use shared voxel state", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "MRI Anatomy", exact: true }).click();
  await expect(
    page.getByRole("img", { name: "axial MRI slice" }),
  ).toBeVisible();
  await expect(page.getByTestId("world-coordinates")).not.toHaveText(
    "World [] mm",
  );
  const box = await page
    .getByRole("img", { name: "axial MRI slice" })
    .boundingBox();
  expect(Math.abs(box!.width / box!.height - (49 * 2) / (33 * 3))).toBeLessThan(
    0.02,
  );
  const before = await page.getByTestId("world-coordinates").textContent();
  await page.getByLabel("Voxel I", { exact: true }).fill("8");
  await expect(page.getByTestId("voxel-coordinates")).toContainText("8,");
  await expect(page.getByTestId("world-coordinates")).not.toHaveText(before!);
  await expect(
    page.locator(".slice-pane").first().locator(".orient.left"),
  ).toHaveText("L");
  await expect(
    page.locator(".slice-pane").first().locator(".orient.right"),
  ).toHaveText("R");
  await page.getByLabel("Segmentation opacity").fill(".5");
  await screenshot(page, "mri-dark");
  await page.getByLabel("axial zoom", { exact: true }).fill("2");
  const zoomed = page.getByRole("img", { name: "axial MRI slice" });
  const bounds = await zoomed.boundingBox();
  await zoomed.click({
    position: { x: bounds!.width * 0.75, y: bounds!.height * 0.25 },
  });
  await expect(page.getByTestId("voxel-coordinates")).toContainText(
    "36, 24, 12",
  );
  await expect(page.getByTestId("world-coordinates")).toContainText(
    "24.00, 24.00, 0.00",
  );
});
test("3D source rendering, source selection and provenance", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: "Source Models", exact: true })
    .click();
  await expect(
    page.getByRole("img", { name: "Interactive anatomical geometry" }),
  ).toBeVisible();
  await page.getByLabel("Source index").fill("4");
  await expect(
    page.getByRole("img", { name: "Source time course" }),
  ).toBeVisible();
  await expect(
    page.getByText(/not a cortical inverse reconstruction/).first(),
  ).toBeVisible();
  await screenshot(page, "source-dark");
});
test("fMRI remains descriptive and unavailable human results are explicit", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: "fMRI Laboratory", exact: true })
    .click();
  await expect(
    page.getByRole("img", { name: "GLM design matrix" }),
  ).toBeVisible();
  await expect(
    page.getByRole("img", { name: "axial MRI slice" }),
  ).toBeVisible();
  await expect(page.getByText("Descriptive inference only.")).toBeVisible();
  expect(
    (
      await request.get(
        "http://127.0.0.1:8000/api/fmri/demo-fmri?inference=confirmatory",
      )
    ).status(),
  ).toBe(422);
  await screenshot(page, "fmri-dark");
});
test("workbench export and bounded explicit job submission", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Experiments", exact: true }).click();
  await expect(
    page.getByText("Independent iid OLS calibration · Milestone14.1"),
  ).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "CSV", exact: true }).first().click();
  expect((await download).suggestedFilename()).toBe("soma-result.csv");
  await page.getByRole("button", { name: "Submit EEG analysis" }).click();
  await expect(page.locator(".job-status")).toContainText("completed");
});
test("light theme and narrow-screen keyboard navigation", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Toggle theme").click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await screenshot(page, "overview-light");
  await page.setViewportSize({ width: 650, height: 900 });
  await page
    .getByRole("button", { name: "MRI Anatomy", exact: true })
    .press("Enter");
  await expect(
    page.getByRole("img", { name: "axial MRI slice" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBe(true);
});
test("configured local EEG, MRI, source and descriptive fMRI artifacts load", async ({
  page,
  request,
}) => {
  const catalog = await (
    await request.get("http://127.0.0.1:8000/api/catalog")
  ).json();
  test.skip(
    !catalog.datasets.some((d: { id: string }) => d.id === "local-eeg"),
    "Explicit local allowlist not configured; demo-only offline CI",
  );
  await page.goto("/");
  await page.getByRole("button", { name: "Local data", exact: true }).click();
  await page
    .getByRole("button", { name: "EEG Laboratory", exact: true })
    .click();
  await expect(
    page.getByRole("img", { name: /EEG trace/ }).first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "MRI Anatomy", exact: true }).click();
  await expect(
    page.getByRole("img", { name: "axial MRI slice" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Source Models", exact: true })
    .click();
  await expect(
    page.getByRole("img", { name: "Source time course" }),
  ).toBeVisible();
  await expect(page.getByText(/fsaverage template/).first()).toBeVisible();
  await page
    .getByRole("button", { name: "fMRI Laboratory", exact: true })
    .click();
  await expect(
    page.getByRole("img", { name: "axial MRI slice" }),
  ).toBeVisible();
  await expect(
    page.getByText(/Explicit configured spatial-unit override/).first(),
  ).toBeVisible();
});
