import { expect, type APIRequestContext, type Page } from "@playwright/test";

export const PASSWORD = process.env.DEMO_USER_PASSWORD ?? "TrustShield-demo-2024";
export const USERS = {
  employee: "ananya.rao@novacorp.test",
  hr: "neha.kapoor@novacorp.test",
  reviewer: "kavya.menon@novacorp.test",
  admin: "rohan.das@novacorp.test",
  auditor: "sanjay.gupta@novacorp.test",
  finance: "rahul.verma@novacorp.test",
  financeHead: "vivek.raman@novacorp.test",
};

export async function login(page: Page, email: string): Promise<void> {
  await page.goto("/login");
  await page.fill("#email", email);
  await page.fill("#password", PASSWORD);
  await page.click("button[type=submit]");
  await expect(page).not.toHaveURL(/\/login/);
}

export async function ask(page: Page, prompt: string): Promise<void> {
  const before = await page.getByTestId("assistant-message").count();
  await page.getByTestId("composer").fill(prompt);
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("assistant-message")).toHaveCount(before + 1);
}

export async function apiToken(request: APIRequestContext, email: string): Promise<string> {
  const res = await request.post("/api/auth/login", { data: { email, password: PASSWORD } });
  expect(res.ok()).toBeTruthy();
  return (await res.json()).access_token as string;
}
