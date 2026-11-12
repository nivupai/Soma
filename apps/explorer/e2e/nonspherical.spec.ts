import { test, expect } from "@playwright/test";
test("nonspherical workbench exposes actual computed fields and limited validation", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: "Source Models", exact: true })
    .click();
  const heading = page.getByRole("heading", {
    name: "Nonspherical conductor validation",
    exact: true,
  });
  await heading.scrollIntoViewIfNeeded();
  await expect(heading).toBeVisible();
  await expect(
    page.getByText(/Six generated heads; no human MRI accuracy/),
  ).toBeVisible();
  await page.getByLabel("Synthetic head", { exact: true }).selectOption("3");
  await expect(
    page.getByText("Head 3: CONVERGED", { exact: true }),
  ).toBeVisible();
  await page.getByLabel("Conductor surface").selectOption("2");
  await page.getByLabel("Geometry projection").selectOption("xz");
  await page.getByLabel("Nonspherical method").selectOption("dSPM");
  await expect(
    page.getByRole("img", {
      name: "Synthetic conductor mesh and source distribution",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("img", { name: "Mesh convergence graph", exact: true }),
  ).toBeVisible();
  if (process.env.CAPTURE_NONSPHERICAL === "1")
    await page.screenshot({ path: "../../reports/milestone27/explorer.png" });
});
