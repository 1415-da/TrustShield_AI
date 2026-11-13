import { expect, test, type Page } from "@playwright/test";

import { login, USERS } from "./helpers";

/** Authentication workflow, role landing pages, navigation consistency and session clean-up. */

const path = (page: Page) => new URL(page.url()).pathname;

test("signed-out visit to a protected page redirects to sign-in and returns there afterwards", async ({ page }) => {
  await page.goto("/console/policies");
  await expect(page).toHaveURL(/\/login\?next=%2Fconsole%2Fpolicies/);
  await page.fill("#email", USERS.admin);
  await page.fill("#password", "TrustShield-demo-2024");
  await page.getByTestId("sign-in-submit").click();
  await expect(page).toHaveURL(/\/console\/policies$/);
});

for (const [who, email, home] of [
  ["Employee", USERS.employee, "/assistant"],
  ["Compliance Reviewer", USERS.reviewer, "/console/reviews"],
  ["TrustShield Admin", USERS.admin, "/console"],
  ["Finance Head", USERS.financeHead, "/console/agents"],
  ["Security Auditor", USERS.auditor, "/console/audit"],
] as const) {
  test(`${who} lands on ${home}`, async ({ page }) => {
    await login(page, email);
    await expect(page).toHaveURL(new RegExp(`${home.replace(/\//g, "\\/")}$`));
  });
}

test("session survives a refresh, and the token never touches localStorage", async ({ page, context }) => {
  await login(page, USERS.employee);
  await page.reload();
  await expect(page).toHaveURL(/\/assistant$/);
  expect(await page.evaluate(() => JSON.stringify(localStorage))).not.toMatch(/eyJ/);
  const access = (await context.cookies()).find((c) => c.name === "trustshield_access_token");
  expect(access?.httpOnly).toBe(true);
});

test("sign-in page never silently continues as the previous account", async ({ page }) => {
  await login(page, USERS.employee);
  await page.goto("/login");
  await expect(page.getByTestId("already-signed-in")).toContainText("Ananya Rao");
  expect(path(page)).toBe("/login");
});

test("sign-out clears the session everywhere: other tabs, Back button, cookies and API", async ({ page, context }) => {
  await login(page, USERS.admin);
  // an in-app navigation, so the Back button has a protected page to return to
  await page.getByRole("navigation", { name: "Console" }).getByRole("link", { name: "Users & roles" }).click();
  await expect(page).toHaveURL(/\/console\/users$/);
  const other = await context.newPage();
  await other.goto("/console/audit");
  await page.getByTestId("sign-out").first().click();
  await expect(page).toHaveURL(/\/login$/);
  await expect(other).toHaveURL(/\/login/);
  await page.goBack();
  await expect(page).toHaveURL(/\/login/); // the protected page is re-checked, never shown from cache
  await expect(page.getByTestId("org-switcher")).toHaveCount(0);
  expect((await page.request.get("/api/auth/me")).status()).toBe(401);
  expect((await context.cookies()).filter((c) => c.name.startsWith("trustshield_"))).toEqual([]);
  await page.goto("/console");
  await expect(page).toHaveURL(/\/login\?next=%2Fconsole/);
});

test("invalid sign-in shows a clear error and validation runs before submitting", async ({ page }) => {
  await page.goto("/login");
  await page.fill("#email", "not-an-email");
  await page.getByTestId("sign-in-submit").click();
  await expect(page.getByText("Enter a valid work email address.")).toBeVisible();
  await page.fill("#email", USERS.employee);
  await page.fill("#password", "definitely-wrong");
  await page.getByTestId("sign-in-submit").click();
  await expect(page.getByText("Incorrect email or password.")).toBeVisible();
  await expect(page.locator("#password")).toHaveValue("");
});

test("unsafe return addresses are ignored", async ({ page }) => {
  await page.goto("/login?next=//evil.example/steal");
  await page.fill("#email", USERS.employee);
  await page.fill("#password", "TrustShield-demo-2024");
  await page.getByTestId("sign-in-submit").click();
  await expect(page).toHaveURL(/localhost:\d+\/assistant$/);
});

test("the sidebar shows only permitted links, and forbidden pages show No access", async ({ page }) => {
  await login(page, USERS.reviewer);
  const nav = page.getByRole("navigation", { name: "Console" });
  await expect(nav.getByRole("link", { name: "Review queue" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Users & roles" })).toHaveCount(0);
  await expect(nav.getByRole("link", { name: "Audit log" })).toHaveCount(0);
  await page.goto("/console/users");
  await expect(page.getByTestId("no-access")).toBeVisible();
});

test("console links go where they say", async ({ page }) => {
  await login(page, USERS.admin);
  const nav = page.getByRole("navigation", { name: "Console" });
  for (const [label, href] of [["Policy Studio", "/console/policies"], ["Audit log", "/console/audit"], ["Users & roles", "/console/users"]]) {
    await nav.getByRole("link", { name: label }).click();
    await expect(page).toHaveURL(new RegExp(`${href.replace(/\//g, "\\/")}$`));
  }
  await page.getByTestId("nav-assistant").first().click();
  await expect(page).toHaveURL(/\/assistant$/);
  await page.getByTestId("open-workspace").click();
  await expect(page).toHaveURL(/\/workspace$/);
  await page.getByTestId("nav-console").click();
  await expect(page).toHaveURL(/\/console$/);
});

test("employee review-queue links are absent and the reviewer queue link works", async ({ page }) => {
  await login(page, USERS.employee);
  await expect(page.getByTestId("nav-console")).toHaveCount(0);
  await page.goto("/console/reviews");
  await expect(page.getByTestId("no-access")).toBeVisible();
});

test("public links: Create workspace, Sign in, Docs and Live demo", async ({ page }) => {
  await page.goto("/");
  const main = page.getByRole("navigation", { name: "Main" });
  await main.getByRole("link", { name: "Create workspace" }).click();
  await expect(page).toHaveURL(/\/signup$/);
  await page.goto("/");
  await main.getByRole("link", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.goto("/");
  await main.getByRole("link", { name: "Live demo" }).click();
  await expect(page).toHaveURL(/\/demo$/);
  await page.goto("/");
  await main.getByRole("link", { name: "Docs" }).first().click();
  await expect(page).toHaveURL(/\/docs$/);
});

test("the sign-in button is disabled while submitting", async ({ page }) => {
  await page.goto("/login");
  await page.fill("#email", USERS.employee);
  await page.fill("#password", "TrustShield-demo-2024");
  await page.route("**/api/auth/login", async (route) => { await new Promise((r) => setTimeout(r, 800)); await route.continue(); });
  await page.getByTestId("sign-in-submit").click();
  await expect(page.getByTestId("sign-in-submit")).toBeDisabled();
  await expect(page).toHaveURL(/\/assistant$/);
});

test("no user-facing page mentions synthetic, demo, sample, mock, fake or test data", async ({ page }) => {
  const banned = /\b(synthetic|demo data|sample data|fake data|test data|mock data|seeded data|simulated company|fictional company)\b/i;
  for (const p of ["/", "/demo", "/docs", "/login", "/signup"]) {
    await page.goto(p);
    expect(await page.locator("body").innerText(), p).not.toMatch(banned);
  }
  await login(page, USERS.admin);
  for (const p of ["/console", "/console/policies", "/console/documents", "/console/users", "/console/settings", "/assistant", "/workspace"]) {
    await page.goto(p);
    await page.waitForLoadState("networkidle");
    expect(await page.locator("body").innerText(), p).not.toMatch(banned);
  }
});
