import { test, expect } from "@playwright/test";
test("synthetic demo head shows readiness, nested layers and a mock uncertainty overlay", async ({
  page,
}) => {
  const requests: string[] = [];
  page.on("request", (r) => requests.push(new URL(r.url()).pathname));
  await page.goto("/");
  await page
    .getByRole("button", { name: "Source Models", exact: true })
    .click();
  const heading = page.getByRole("heading", {
    name: "Synthetic 3D head",
    exact: true,
  });
  await heading.scrollIntoViewIfNeeded();
  const banner = page.getByRole("region", {
    name: "Synthetic concentric-shell head readiness",
  });
  await expect(banner).toHaveAttribute("data-readiness", "NOT_READY");
  await expect(banner.getByText("NOT_READY", { exact: true })).toBeVisible();
  await expect(banner.getByText(/does not establish anatomical/)).toBeVisible();
  await expect(
    page.getByRole("img", { name: "Interactive 3D head", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Show Scalp").uncheck();
  await expect(page.getByLabel("Scalp opacity")).toBeDisabled();
  await page.getByLabel("Show Inner skull").check();
  await page.getByLabel("Inner skull opacity").fill("0.6");
  await page.getByLabel("Colour sources by").selectOption("mean");
  const legend = page.getByRole("figure", {
    name: "Localisation error · mean legend",
  });
  await expect(legend.getByText("MOCK FIXTURE", { exact: true })).toBeVisible();
  await expect(page.getByText(/95% CI/).first()).toBeVisible();
  // Demo mode only reaches the synthetic head routes; no private anatomy.
  expect(requests.some((p) => p.includes("/api/mri-head-models/local/"))).toBe(
    false,
  );
  expect(
    [
      ...new Set(requests.filter((p) => p.startsWith("/api/head-scenes/"))),
    ].sort(),
  ).toEqual([
    "/api/head-scenes/demo-synthetic-head",
    "/api/head-scenes/demo-synthetic-head/uncertainty",
  ]);
  if (process.env.CAPTURE_HEAD_SCENE === "1")
    await page.screenshot({ path: "../../reports/milestone35/explorer.png" });
});
