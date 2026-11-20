import { test, expect } from "@playwright/test";
test("inverse calibration explorer reports actual synthetic priors and held-out errors", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: "Source Models", exact: true })
    .click();
  const heading = page.getByRole("heading", {
    name: "Inverse priors and source-density calibration",
    exact: true,
  });
  await heading.scrollIntoViewIfNeeded();
  await expect(heading).toBeVisible();
  await expect(page.getByText(/481 candidates · peak error/)).toBeVisible();
  await page
    .getByLabel("Source prior", { exact: true })
    .selectOption("total_variance");
  await page.getByLabel("Prior inverse method").selectOption("dSPM");
  await expect(
    page.getByRole("img", { name: "Computed inverse point-spread response" }),
  ).toBeVisible();
  await expect(
    page.getByText(/dSPM is dimensionless and cannot be interpreted/),
  ).toBeVisible();
  await page.getByLabel("Prior regularization").selectOption("prediction");
  await expect(
    page.getByText(/without synthesized spatial maps/),
  ).toBeVisible();
});
