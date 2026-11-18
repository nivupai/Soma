import { test, expect } from "@playwright/test";
test("independent FEM view preserves physical units and evidence scope", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: "Source Models", exact: true })
    .click();
  const heading = page.getByRole("heading", {
    name: "Independent four-layer FEM reference",
    exact: true,
  });
  await heading.scrollIntoViewIfNeeded();
  await expect(heading).toBeVisible();
  await expect(
    page.getByText(/Unscaled OpenMEEG \/ FEM difference/),
  ).toBeVisible();
  await page.getByLabel("FEM synthetic head").selectOption("5");
  await page.getByLabel("FEM mesh level").selectOption("2");
  await expect(
    page.getByRole("img", {
      name: "FEM source-wise physical field differences",
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.getByText(/M28 findings remain unchanged/)).toBeVisible();
});
