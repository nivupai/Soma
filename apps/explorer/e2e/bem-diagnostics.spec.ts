import { test, expect } from "@playwright/test";
test("independent BEM diagnostics retain failed gates and physical reference scope", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: "Source Models", exact: true })
    .click();
  const heading = page.getByRole("heading", {
    name: "Independent BEM diagnostics",
    exact: true,
  });
  await heading.scrollIntoViewIfNeeded();
  await expect(heading).toBeVisible();
  await expect(
    page.getByText(/The finest nonspherical fields still fail/),
  ).toBeVisible();
  await page
    .getByLabel("BEM synthetic head", { exact: true })
    .selectOption("5");
  await expect(
    page.getByRole("img", {
      name: "BEM off-grid source error plot",
      exact: true,
    }),
  ).toBeVisible();
  await page.getByLabel("BEM physical reference").selectOption("A");
  await page.getByLabel("BEM solver comparison").selectOption("MNE");
  await expect(page.getByText("0.47%", { exact: true })).toBeVisible();
  await expect(
    page.getByText(
      /passing control does not validate nonspherical or human anatomy/,
    ),
  ).toBeVisible();
  if (process.env.CAPTURE_BEM === "1")
    await heading
      .locator("xpath=ancestor::section[1]")
      .screenshot({ path: "../../reports/milestone28/explorer.png" });
});
