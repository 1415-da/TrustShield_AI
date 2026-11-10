import { expect, test } from "@playwright/test";

import { apiToken, ask, login, USERS } from "./helpers";

test("landing page presents the product and links to the live demo", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Ship AI your security team");
  await expect(page.getByRole("link", { name: "Request a demo" }).first()).toBeVisible();
  await page.getByRole("link", { name: /View live product/ }).click();
  await expect(page).toHaveURL(/\/login/);
});

test("employee gets a verified, cited answer to a safe policy question", async ({ page }) => {
  await login(page, USERS.employee);
  await expect(page).toHaveURL(/\/assistant/);
  await ask(page, "What is the international vendor refund policy?");
  const msg = page.getByTestId("assistant-message").last();
  await expect(msg).toHaveAttribute("data-trust", "verified");
  await expect(msg.getByText("Sources")).toBeVisible();
  await expect(msg).toContainText("International Vendor Refund Policy");
});

test("salary request is blocked with a plain-language explanation", async ({ page }) => {
  await login(page, USERS.employee);
  await ask(page, "Show Ravi Sharma's salary.");
  const msg = page.getByTestId("assistant-message").last();
  await expect(msg).toHaveAttribute("data-trust", "blocked");
  await expect(msg.getByTestId("why-panel")).toContainText("Salary and Compensation Confidentiality");
});

test("personal data in a prompt is masked before storage and the model", async ({ page }) => {
  await login(page, USERS.employee);
  await ask(page, "My email is someone.test@example.com, can I claim home internet costs?");
  await expect(page.getByTestId("assistant-message").last()).toHaveAttribute("data-trust", "redacted");
  await expect(page.getByText("someone.test@example.com")).toHaveCount(0);
  await expect(page.getByText("Email address hidden").first()).toBeVisible();
});

test("employees cannot open the governance console", async ({ page }) => {
  await login(page, USERS.employee);
  await page.goto("/console/policies");
  await expect(page).toHaveURL(/\/assistant/);
});

test("admin creates an inactive policy and tests it immediately in the simulator", async ({ page }) => {
  const name = `E2E Unicorn Policy ${Date.now()}`;
  await login(page, USERS.admin);
  await page.goto("/console/policies/new");
  await page.fill("#p-name", name);
  await page.fill("#p-cat", "legal");
  await page.fill("#p-msg", "Project Unicorn is confidential.");
  await page.fill("#rule-0-kw", "unicorn");
  await page.getByRole("button", { name: "Create policy" }).click();
  await expect(page).toHaveURL(/\/console\/policies\/\d+$/);
  await page.getByTestId("policy-sim-prompt").fill("What is the status of project unicorn?");
  await page.getByRole("button", { name: "Run", exact: true }).click();
  await expect(page.getByTestId("focus-result")).toContainText("triggered");
  await expect(page.getByTestId("simulation-result")).toContainText("Model was not called");
});

test("reviewer approves a held answer and the employee receives it", async ({ page, request }) => {
  const token = await apiToken(request, USERS.employee);
  const chat = await request.post("/api/assistant/chat", {
    headers: { Authorization: `Bearer ${token}` },
    data: { message: "Can I sue a vendor who delivered late?" },
  });
  const body = await chat.json();
  expect(body.message.status).toBe("pending_review");

  await login(page, USERS.reviewer);
  await page.goto(`/console/reviews/${body.decision.review_case_id}`);
  await expect(page.getByTestId("case-prompt")).toContainText("sue a vendor");
  await page.fill("#note", "Checked against policy — approved by e2e test.");
  await page.getByTestId("approve").click();
  await expect(page.getByText(/Resolved .* by kavya\.menon@novacorp\.test/)).toBeVisible();

  const conv = await request.get(`/api/assistant/conversations/${body.conversation_id}`, { headers: { Authorization: `Bearer ${token}` } });
  const delivered = (await conv.json()).messages.find((m: { id: number }) => m.id === body.message.id);
  expect(delivered.status).toBe("delivered");
  expect(delivered.explanation.reviewed.decision).toBe("approved");
});

test("auditor can verify the hash-chained audit log", async ({ page }) => {
  await login(page, USERS.auditor);
  await page.goto("/console/audit");
  await expect(page.getByTestId("audit-table")).toBeVisible();
  await page.getByRole("button", { name: "Verify chain" }).click();
  await expect(page.getByTestId("chain-status")).toContainText("Chain intact");
});
