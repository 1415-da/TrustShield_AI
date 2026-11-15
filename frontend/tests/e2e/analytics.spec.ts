import { expect, test } from "@playwright/test";

function eventFromRequest(postData: string | null): Record<string, unknown> | null {
  if (!postData) return null;
  try {
    const params = new URLSearchParams(postData);
    const encoded = params.get("data");
    if (encoded) return JSON.parse(Buffer.from(encoded, "base64").toString("utf8"));
    return JSON.parse(postData);
  } catch {
    return null;
  }
}

test("landing page event sends a sanitized payload to Mixpanel", async ({ page }) => {
  test.skip(!process.env.NEXT_PUBLIC_MIXPANEL_TOKEN, "Configure NEXT_PUBLIC_MIXPANEL_TOKEN in the frontend build to verify ingestion.");
  const payloads: Record<string, unknown>[] = [];
  await page.route(/https:\/\/(api-js|api)\.mixpanel\.com\//, async (route) => {
    const payload = eventFromRequest(route.request().postData());
    if (payload) payloads.push(payload);
    await route.fulfill({ status: 200, contentType: "application/json", body: '{"status":1}' });
  });
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Ship AI your security team");
  await expect.poll(() => payloads.some((p) => p.event === "landing_page_viewed")).toBe(true);
  const landing = payloads.find((p) => p.event === "landing_page_viewed")!;
  const properties = (landing.properties ?? {}) as Record<string, unknown>;
  expect(JSON.stringify(properties)).not.toMatch(/email|prompt|answer|salary|\?.*=/i);
});

test("signup route event is tracked without putting query values in Mixpanel", async ({ page }) => {
  test.skip(!process.env.NEXT_PUBLIC_MIXPANEL_TOKEN, "Configure NEXT_PUBLIC_MIXPANEL_TOKEN in the frontend build to verify ingestion.");
  const payloads: Record<string, unknown>[] = [];
  await page.route(/https:\/\/(api-js|api)\.mixpanel\.com\//, async (route) => {
    const payload = eventFromRequest(route.request().postData());
    if (payload) payloads.push(payload);
    await route.fulfill({ status: 200, contentType: "application/json", body: '{"status":1}' });
  });
  await page.goto("/signup?email=private@example.com&referrer=secret-value");
  await expect(page.getByRole("heading").first()).toBeVisible();
  await expect.poll(() => payloads.some((p) => p.event === "signup_started")).toBe(true);
  const signup = payloads.find((p) => p.event === "signup_started")!;
  expect(JSON.stringify(signup)).not.toContain("private@example.com");
  expect(JSON.stringify(signup)).not.toContain("secret-value");
});

test("Mixpanel transport failure does not block the public app", async ({ page }) => {
  await page.route(/https:\/\/(api-js|api)\.mixpanel\.com\//, (route) => route.abort());
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Ship AI your security team");
});
