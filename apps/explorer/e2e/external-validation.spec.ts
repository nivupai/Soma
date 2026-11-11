import { test, expect } from "@playwright/test";
test("external validation separates acquisition approval, compatibility and human outcomes", async ({
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
      name: "Frozen external EEG validation",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByText("External validation: BLOCKED", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText(/Human external coverage: 0 subjects/),
  ).toBeVisible();
  await expect(
    page.getByText(/No external human accuracy is available while acquisition/),
  ).toBeVisible();
  expect(writes).toEqual([]);
  if (process.env.CAPTURE_VALIDATION === "1")
    await page.screenshot({
      path: "../../reports/milestone25/external-validation.png",
      fullPage: false,
    });
});
