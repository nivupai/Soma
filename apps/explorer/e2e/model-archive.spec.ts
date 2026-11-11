import { test, expect } from "@playwright/test";
test("model archive distinguishes verified state from external human replication", async ({
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
      name: "Prospective EEG model archive",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByText(
      "No human external accuracy is available. Archived state integrity is not independent scientific validation.",
    ),
  ).toBeVisible();
  await expect(
    page.getByText("Newly archived state is not original M22 weights", {
      exact: true,
    }),
  ).toBeVisible();
  await page
    .getByText("Feature and transfer compatibility", { exact: true })
    .click();
  await expect(
    page.getByText(/BNCI004 lacks six required channels/),
  ).toBeVisible();
  expect(writes).toEqual([]);
  if (process.env.CAPTURE_MODEL_ARCHIVE === "1")
    await page.screenshot({
      path: "../../reports/milestone24/model-explorer.png",
      fullPage: true,
    });
});
