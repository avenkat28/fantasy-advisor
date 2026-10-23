/** Live integration suite. Both local services and real artifacts are required. */
import { expect, test } from "@playwright/test";

test("research, projections, comparisons and evaluation use the live backend", async ({
  page,
  request,
}) => {
  const base =
    process.env.API_TEST_BASE_URL ||
    process.env.FRONTEND_TEST_URL ||
    "http://localhost:3000";
  const health = await (await request.get(`${base}/api/health`)).json();
  const season = health.snapshot.season;
  const week = Math.max(...health.snapshot.roster_weeks[String(season)]);
  const weekly = await (
    await request.get(
      `${base}/api/projections?season=${season}&week=${week}&limit=2`,
    )
  ).json();
  const [first, second] = weekly.projections;
  expect(first).toBeTruthy();
  expect(second).toBeTruthy();
  const pageErrors: string[] = [];
  const apiOrigins = new Set<string>();
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith("/api/")) apiOrigins.add(url.origin);
  });
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Your edge starts here." }),
  ).toBeVisible();
  await expect(page.getByLabel("NFL week")).toHaveValue(String(week));
  await expect(page.locator(".table-player").first()).toBeVisible({
    timeout: 30000,
  });
  await expect(page.locator("body")).toHaveJSProperty(
    "scrollWidth",
    await page.locator("body").evaluate((body) => body.clientWidth),
  );
  await page
    .getByRole("link", { name: "Weekly Projections", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Weekly projections" }),
  ).toBeVisible();
  await page.getByLabel("Search projected players").fill(first.player_name);
  await expect(
    page
      .getByRole("table")
      .getByRole("link")
      .filter({ hasText: first.player_name })
      .first(),
  ).toBeVisible();
  await page
    .getByRole("table")
    .getByRole("link")
    .filter({ hasText: first.player_name })
    .first()
    .click();
  await expect(
    page.getByRole("heading", { name: first.player_name, level: 1 }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Recent game log" }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "Start/Sit Comparison", exact: true })
    .click();
  await page.getByLabel("Player A", { exact: true }).fill(first.player_name);
  await page
    .getByRole("list", { name: "Player A results" })
    .getByRole("button")
    .filter({ hasText: first.player_name })
    .first()
    .click();
  await page.getByLabel("Player B", { exact: true }).fill(second.player_name);
  await page
    .getByRole("list", { name: "Player B results" })
    .getByRole("button")
    .filter({ hasText: second.player_name })
    .first()
    .click();
  await page
    .getByRole("button", { name: "Compare players", exact: true })
    .click();
  await expect(page.locator(".recommendation")).toBeVisible();
  await page
    .getByRole("link", { name: "Model Performance", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Every model. Every metric." }),
  ).toBeVisible();
  await expect(page.getByRole("table")).toContainText("xgboost");
  await expect(page.locator(".recharts-surface").first()).toBeVisible();
  expect(pageErrors).toEqual([]);
  expect([...apiOrigins]).toEqual([new URL(page.url()).origin]);
});

test("unpublished week gives an actionable error, not fabricated projections", async ({
  page,
  request,
}) => {
  const base =
    process.env.API_TEST_BASE_URL ||
    process.env.FRONTEND_TEST_URL ||
    "http://localhost:3000";
  const health = await (await request.get(`${base}/api/health`)).json();
  const missingWeek = Array.from({ length: 18 }, (_, i) => i + 1).find(
    (w) =>
      !health.snapshot.roster_weeks[String(health.snapshot.season)].includes(w),
  );
  test.skip(!missingWeek, "All weeks have roster coverage.");
  await page.goto("/projections");
  await expect(page.getByLabel("NFL week")).toBeEnabled();
  await page.getByLabel("NFL week").selectOption(String(missingWeek));
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "No fresh weekly roster",
  );
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
  await expect(page.getByRole("table")).toHaveCount(0);
});

test("one domain serves the UI, API, and API documentation", async ({
  request,
}) => {
  const health = await request.get("/api/health");
  expect(health.ok()).toBeTruthy();
  expect((await health.json()).application).toBe("FantasyAdvisor");
  const docs = await request.get("/docs");
  expect(docs.ok()).toBeTruthy();
  expect(await docs.text()).toContain("SwaggerUIBundle");
  const schema = await request.get("/openapi.json");
  expect((await schema.json()).paths).toHaveProperty("/api/projections");
  const missing = await request.get("/api/route-that-does-not-exist");
  expect(missing.status()).toBe(404);
  expect(missing.headers()["content-type"]).toContain("application/json");
  const ui = await request.get("/players");
  expect(ui.ok()).toBeTruthy();
  expect(ui.headers()["content-type"]).toContain("text/html");
});
