import { test, expect } from "@playwright/test";
test("M32 distinguishes failed tissue evidence from numerical QC", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: "Source Models", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "MRI-derived human head models" }),
  ).toBeVisible();
  await expect(page.getByText("14.56%")).toBeVisible();
  await expect(page.getByText(/0 validated conductor anatomies/)).toBeVisible();
});
test("explicit local operator can inspect actual private MRI and conductor", async ({
  page,
}) => {
  test.skip(
    process.env.SOMA_LOCAL_ANATOMY_VIEWER !== "1",
    "Requires operator authorized local MRI; never downloaded in public CI",
  );
  await page.goto("/");
  await page
    .getByRole("button", { name: "Source Models", exact: true })
    .click();
  await page
    .getByLabel("Authorized local anatomy")
    .selectOption("m32-authorized-mri");
  await expect(page.getByLabel("Local axial slice")).toBeVisible();
  await expect(page.locator("canvas").last()).toBeVisible();
  await page
    .getByLabel("Authorized local anatomy")
    .selectOption("m32-authorized-conductor");
  await expect(
    page.getByRole("img", {
      name: "Local MRI-derived conductor and measured electrodes",
    }),
  ).toBeVisible();
  await expect(
    page.getByText(/Actual local FLASH-derived inner skull/),
  ).toBeVisible();
});
