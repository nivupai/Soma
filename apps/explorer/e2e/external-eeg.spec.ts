import { test, expect } from "@playwright/test";
test("external EEG audit preserves blocked human evaluation and frozen-model distinctions", async ({
  page,
}) => {
  const writes: string[] = [];
  page.on("request", (r) => {
    if (r.method() !== "GET") writes.push(r.url());
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Experiments", exact: true }).click();
  await expect(
    page.getByRole("heading", {
      name: "External EEG replication",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByText(
      "No human external decoding outcomes. A blocked audit is not a completed replication.",
    ),
  ).toBeVisible();
  await page
    .getByText("Model and feature compatibility", { exact: true })
    .click();
  await expect(
    page.getByText(/"original_m22_model_available": false/),
  ).toBeVisible();
  await expect(
    page.getByText(/Observed human coverage: 0 subjects/),
  ).toBeVisible();
  expect(writes).toEqual([]);
  if (process.env.CAPTURE_EXTERNAL_EEG === "1")
    await page.screenshot({
      path: "../../reports/milestone23/external-explorer.png",
      fullPage: true,
    });
});
