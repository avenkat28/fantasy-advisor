import { expect, test } from "@playwright/test";
import { health, weekly, performance } from "../src/test/fixtures";

test("logo, browser icon and persisted themes work at every viewport", async ({ page, request }, testInfo) => {
  await page.route("**/api/**", async route => {
    const path = new URL(route.request().url()).pathname;
    const body = path.endsWith("/health") ? health : path.endsWith("/projections") ? weekly : path.endsWith("/performance") ? performance : { records: [], metrics: [] };
    await route.fulfill({ json: body });
  });
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  const logo = page.getByRole("img", { name: "Fantasy Advisor", exact: true });
  await expect(logo).toBeVisible();
  await expect.poll(() => logo.evaluate((el: HTMLImageElement) => el.naturalWidth)).toBeGreaterThan(0);
  const icon = await request.get("/favicon.ico");
  expect(icon.ok()).toBeTruthy();
  await page.screenshot({ path: `/tmp/fantasy-${testInfo.project.name}-dark.png`, fullPage: true });
  await page.getByRole("button", { name: "Switch to light mode" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await expect(page.getByRole("button", { name: "Switch to dark mode" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.screenshot({ path: `/tmp/fantasy-${testInfo.project.name}-light.png`, fullPage: true });
  await page.goto("/projections");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
});
