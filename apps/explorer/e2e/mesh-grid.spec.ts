import { test, expect } from "@playwright/test";
test("external mesh workbench separates geometry and inverse-grid effects", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: "Source Models", exact: true })
    .click();
  const h = page.getByRole("heading", {
    name: "Independent mesh and source-grid convergence",
    exact: true,
  });
  await h.scrollIntoViewIfNeeded();
  await expect(h).toBeVisible();
  await page.getByLabel("Mesh grid head").selectOption("5");
  await page.getByLabel("Inverse grid spacing").selectOption("20");
  await expect(
    page.getByRole("img", {
      name: "Source grid localization and nearest-distance curves",
    }),
  ).toBeVisible();
  await expect(
    page.getByText(/The latter includes geometry effects/),
  ).toBeVisible();
  await expect(page.getByText(/Dense grids are not assumed/)).toBeVisible();
});
