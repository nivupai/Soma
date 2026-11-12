import { test, expect } from "@playwright/test";
test("source uncertainty keeps synthetic truth, physical displacement and failed cases explicit", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: "Source Models", exact: true })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "Anatomical uncertainty experiment",
      exact: true,
    }),
  ).toBeVisible();
  await page
    .getByRole("heading", {
      name: "Anatomical uncertainty experiment",
      exact: true,
    })
    .scrollIntoViewIfNeeded();
  await expect(
    page.getByText(/Simulated spherical geometry; not empirically/),
  ).toBeVisible();
  await expect(
    page.getByRole("img", { name: "Baseline source estimate", exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Source uncertainty scenario")
    .selectOption("translation-5");
  await expect(
    page.getByText(/Selected error source: translation/),
  ).toBeVisible();
  await page.getByLabel("Uncertainty inverse method").selectOption("dSPM");
  await expect(
    page.getByText("Not physical (dSPM)", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Numerical failures retained: 9 / 49", { exact: true }),
  ).toBeVisible();
  if (process.env.CAPTURE_UNCERTAINTY === "1")
    await page.screenshot({
      path: "../../reports/milestone26/explorer.png",
      fullPage: false,
    });
});
