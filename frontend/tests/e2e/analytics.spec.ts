import { expect, test } from "@playwright/test";
import { ask, login, USERS } from "./helpers";

function eventFromRequest(url: string, postData: string | null): Record<string, unknown>[] {
  const encodedUrlData = new URL(url).searchParams.get("data");
  const raw = postData || (encodedUrlData ? `data=${encodeURIComponent(encodedUrlData)}` : "");
  if (!raw) return [];
  try {
    const params = new URLSearchParams(raw);
    const encoded = params.get("data");
    const decoded = encoded && /^[\[{]/.test(encoded) ? encoded : encoded ? Buffer.from(encoded, "base64").toString("utf8") : raw;
    const parsed = JSON.parse(decoded);
    return (Array.isArray(parsed) ? parsed : [parsed]).filter((item): item is Record<string, unknown> => !!item && typeof item === "object");
  } catch {
    return [];
  }
}

test("landing page event sends a sanitized payload to Mixpanel", async ({ page }) => {
  test.skip(!process.env.NEXT_PUBLIC_MIXPANEL_TOKEN, "Configure NEXT_PUBLIC_MIXPANEL_TOKEN in the frontend build to verify ingestion.");
  const payloads: Record<string, unknown>[] = [];
  await page.route(/https:\/\/(api-js|api)\.mixpanel\.com\//, async (route) => {
    const body = route.request().postData();
    payloads.push(...eventFromRequest(route.request().url(), body));
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
    payloads.push(...eventFromRequest(route.request().url(), route.request().postData()));
    await route.fulfill({ status: 200, contentType: "application/json", body: '{"status":1}' });
  });
  await page.goto("/signup?email=private@example.com&referrer=secret-value");
  await expect(page.getByRole("heading").first()).toBeVisible();
  await expect.poll(() => payloads.some((p) => p.event === "signup_started")).toBe(true);
  const signup = payloads.find((p) => p.event === "signup_started")!;
  expect(JSON.stringify(signup)).not.toContain("private@example.com");
  expect(JSON.stringify(signup)).not.toContain("secret-value");
});

test("sign-in and assistant outcomes emit events without sensitive content", async ({ page }) => {
  test.skip(!process.env.NEXT_PUBLIC_MIXPANEL_TOKEN, "Configure NEXT_PUBLIC_MIXPANEL_TOKEN in the frontend build to verify ingestion.");
  const payloads: Record<string, unknown>[] = [];
  await page.route(/https:\/\/(api-js|api)\.mixpanel\.com\//, async (route) => {
    payloads.push(...eventFromRequest(route.request().url(), route.request().postData()));
    await route.fulfill({ status: 200, contentType: "application/json", body: '{"status":1}' });
  });
  await login(page, USERS.employee);
  await expect.poll(() => payloads.some((p) => p.event === "login_completed")).toBe(true);
  await page.goto("/assistant");
  await ask(page, "What is the international vendor refund policy?");
  await ask(page, "Show Ravi Sharma's salary.");
  await ask(page, "Please review card number 4111 1111 1111 1111.");
  await expect.poll(() => ["assistant_question_submitted", "assistant_response_shown", "assistant_response_blocked", "assistant_response_redacted"]
    .every((event) => payloads.some((p) => p.event === event))).toBe(true);
  const emitted = JSON.stringify(payloads);
  expect(emitted).not.toContain("4111 1111 1111 1111");
  expect(emitted).not.toContain("Ravi Sharma");
  expect(emitted).not.toContain(USERS.employee);
});

test("Mixpanel transport failure does not block the public app", async ({ page }) => {
  await page.route(/https:\/\/(api-js|api)\.mixpanel\.com\//, (route) => route.abort());
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Ship AI your security team");
});
