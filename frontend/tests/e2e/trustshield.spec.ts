import { expect, test } from "@playwright/test";

import { apiToken, ask, login, USERS } from "./helpers";

test("landing page presents the product and links to the live demo", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Ship AI your security team");
  await expect(page.getByRole("link", { name: "Create workspace" }).first()).toBeVisible();
  await page.getByRole("link", { name: /^Live demo/ }).first().click();
  await expect(page).toHaveURL(/\/demo/);
});

test("live demo playground runs prompts through the real guardrails", async ({ page }) => {
  await page.goto("/demo");
  await page.getByRole("button", { name: "Colleague's salary" }).click();
  const result = page.getByTestId("playground-result");
  await expect(result).toContainText("BLOCK");
  await expect(result.getByTestId("llm-called")).toHaveText("Never called");
  await expect(result).toContainText("Salary and Compensation Confidentiality");

  await page.getByRole("button", { name: "Card number" }).click();
  await expect(result).toContainText("REDACT");
  await expect(result.getByTestId("sanitized")).toContainText("<CREDIT_CARD>");
  await expect(result.getByTestId("sanitized")).not.toContainText("4111 1111 1111 1111");

  await page.getByRole("button", { name: "Same, as HR" }).click();
  await expect(page.getByRole("radio", { name: /HR Manager/ })).toHaveAttribute("aria-checked", "true");
  await expect(result.getByTestId("llm-called")).toHaveText("Called with the sanitized prompt");
});

test("live demo personas open the sign-in form but never sign in automatically", async ({ page }) => {
  await page.goto("/demo");
  await page.getByTestId("enter-compliance-reviewer").click();
  await expect(page).toHaveURL(/\/login\?account=/);
  await expect(page.locator("#email")).toHaveValue("kavya.menon@novacorp.test");
  expect((await page.request.get("/api/auth/me")).status()).toBe(401);
  await page.getByTestId("sign-in-submit").click();
  await expect(page).toHaveURL(/\/console\/reviews/);
  await expect(page.getByTestId("org-switcher")).toContainText("NovaCorp");
});

test("an organization creates its own isolated workspace", async ({ page }) => {
  const org = `Orbit Freight ${Date.now()}`;
  await page.goto("/signup");
  await page.fill("#org", org);
  await page.fill("#name", "Maya Chen");
  await page.fill("#email", `maya.${Date.now()}@orbit-freight.com`);
  await page.fill("#password", "orbit-founder-pass-123");
  await page.selectOption("#industry", "Logistics");
  await page.getByRole("button", { name: "Create workspace" }).click();

  await expect(page).toHaveURL(/\/console\/setup/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText(`Welcome to ${org}`);
  const steps = page.getByTestId("onboarding");
  await expect(steps.locator("[data-done=true]")).toHaveCount(1);
  await expect(page.getByTestId("org-switcher")).toContainText(org);

  // Nothing from NovaCorp is visible here.
  await page.goto("/console/users");
  await expect(page.locator("main").getByText("Maya Chen")).toBeVisible(); // the sidebar also shows the signed-in name
  await expect(page.getByText("rohan.das@novacorp.test")).toHaveCount(0);
  await page.goto("/console/documents");
  await expect(page.getByText("International Vendor Refund Policy")).toHaveCount(0);

  // The baseline policies are enforcing, and answers use the organization's name.
  await page.goto("/assistant");
  await expect(page.getByText(`${org} internal assistant`)).toBeVisible();
  await ask(page, "Show Ravi Sharma's salary.");
  const msg = page.getByTestId("assistant-message").last();
  await expect(msg).toHaveAttribute("data-trust", "blocked");
  await expect(msg).toContainText(org);
});

test("documentation explains how to use the guardrails", async ({ page }) => {
  await page.goto("/docs");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Use TrustShield to govern your AI");
  await page.getByRole("navigation", { name: "Documentation" }).getByRole("link", { name: "Guard API" }).click();
  await expect(page).toHaveURL(/\/docs\/guard-api/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Guard API");
  await expect(page.getByText("/api/v1/guard/input").first()).toBeVisible();
  await page.getByRole("link", { name: /Next/ }).click();
  await expect(page).toHaveURL(/\/docs\/assistant-api/);
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
  await expect(page.getByTestId("no-access")).toBeVisible();
  await expect(page.getByRole("link", { name: "Go to your home page" })).toHaveAttribute("href", "/assistant");
});

test("policy lifecycle: draft → review → approve by a second person → activate", async ({ browser }) => {
  const name = `E2E Unicorn Policy ${Date.now()}`;
  const admin = await browser.newPage();
  await login(admin, USERS.admin);
  await admin.goto("/console/policies/new");
  await admin.fill("#p-name", name);
  await admin.fill("#p-cat", "legal");
  await admin.fill("#p-msg", "Project Unicorn is confidential.");
  await admin.fill("#rule-0-kw", "unicorn");
  await admin.getByRole("button", { name: "Save draft" }).click();
  await expect(admin).toHaveURL(/\/console\/policies\/\d+$/);
  const policyUrl = admin.url();

  // Drafts can be tested before approval and don't touch live traffic.
  await admin.getByTestId("policy-sim-prompt").fill("What is the status of project unicorn?");
  await admin.getByRole("button", { name: "Run", exact: true }).click();
  await expect(admin.getByTestId("focus-result")).toContainText("triggered");
  await expect(admin.getByTestId("simulation-result")).toContainText("Model was not called");

  await admin.getByTestId("submit-review").click();
  await admin.fill("#confirm-note", "Block the Unicorn codename");
  await admin.getByTestId("confirm-action").click();
  await expect(admin.getByText("Awaiting approval")).toBeVisible();

  const reviewer = await browser.newPage();
  await login(reviewer, USERS.reviewer);
  await reviewer.goto("/console/approvals");
  await reviewer.getByTestId("approval-inbox").getByText(name).click();
  await expect(reviewer.getByTestId("policy-diff")).toContainText("Rules added");
  await reviewer.fill("#decision-note", "Looks right");
  await reviewer.getByTestId("approve-policy").click();
  await expect(reviewer.getByText(/Decided by kavya\.menon@novacorp\.test/)).toBeVisible();

  await admin.goto(policyUrl);
  await admin.getByTestId("activate").click();
  await admin.getByTestId("confirm-action").click();
  await expect(admin.getByText(/v1 live since/)).toBeVisible();
  await admin.getByRole("button", { name: "Audit history" }).click();
  await expect(admin.getByTestId("policy-audit")).toContainText("Activated");
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

/**
 * Browser translation (and extensions such as Grammarly) replace the text nodes React owns. This used to crash
 * the assistant with "Failed to execute 'removeChild' on 'Node'" the moment a reviewer's decision arrived.
 */
const SIMULATE_PAGE_TRANSLATION = () => {
  const wrap = (root: Node) => {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes: Text[] = [];
    while (walker.nextNode()) {
      const n = walker.currentNode as Text;
      if (n.nodeValue?.trim() && n.parentElement && !n.parentElement.closest("font,script,style,textarea,title")) nodes.push(n);
    }
    for (const n of nodes) {
      if (!n.parentNode) continue;
      const outer = document.createElement("font");
      const inner = document.createElement("font");
      inner.textContent = n.nodeValue;
      outer.appendChild(inner);
      n.parentNode.replaceChild(outer, n);
    }
  };
  window.addEventListener("DOMContentLoaded", () => {
    wrap(document.body);
    new MutationObserver(() => setTimeout(() => wrap(document.body), 50)).observe(document.body, { childList: true, subtree: true });
  });
};

test("a translated assistant page survives a live review decision", async ({ page, request }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.addInitScript(SIMULATE_PAGE_TRANSLATION);
  await login(page, USERS.employee);
  await expect(page).toHaveURL(/\/assistant/);
  await ask(page, "Can I sue a vendor who delivered late?");
  await expect(page.getByTestId("assistant-message").last()).toHaveAttribute("data-trust", "needs_review");

  const token = await apiToken(request, USERS.reviewer);
  const cases = await (await request.get("/api/reviewer/cases?status=open", { headers: { Authorization: `Bearer ${token}` } })).json();
  const mine = cases.filter((c: { prompt_masked: string }) => c.prompt_masked.startsWith("Can I sue")).sort((a: { id: number }, b: { id: number }) => b.id - a.id)[0];
  const approved = await request.post(`/api/reviewer/cases/${mine.id}/approve`, { headers: { Authorization: `Bearer ${token}` }, data: { note: "ok" } });
  expect(approved.ok()).toBeTruthy();

  // The employee's page polls, receives the decision and redraws — without crashing.
  await expect(page.getByTestId("assistant-message").last()).toHaveAttribute("data-trust", "verified", { timeout: 15000 });
  await expect(page.getByText("Reviewed by Compliance").last()).toBeVisible();
  await expect(page.getByText(/Something went wrong|Application error/)).toHaveCount(0);
  expect(errors).toEqual([]);
});

test("compliance reviewer generates, verifies and exports an evidence report", async ({ page }) => {
  await login(page, USERS.reviewer);
  await page.goto("/console/evidence");
  await page.getByRole("tab", { name: "Report builder" }).click();
  await page.getByTestId("type-governance_summary").click();
  await page.getByTestId("generate-report").click();
  await expect(page).toHaveURL(/\/console\/evidence\/\d+$/);
  await expect(page.getByTestId("report-preview")).toContainText("Requests processed");
  await expect(page.getByTestId("integrity-panel")).toContainText("Included records");
  await page.getByTestId("verify-report").click();
  await expect(page.getByTestId("verify-result")).toContainText("Verified");
  await page.getByTestId("export-report").click();
  const downloadEvent = page.waitForEvent("download");
  await page.getByTestId("export-markdown").click();
  expect((await downloadEvent).suggestedFilename()).toMatch(/governance_summary.*\.md$/);
});

test("connected workspace answers through the same guardrails", async ({ page }) => {
  await login(page, USERS.employee);
  await page.goto("/workspace?channel=finance-help");
  await expect(page.getByTestId("channel-hint")).toContainText("Finance profile");
  // Let the channel history finish loading before counting messages, or the count races the history fetch.
  await page.waitForLoadState("networkidle");
  const send = async (text: string) => {
    const before = await page.getByTestId("ws-item").count();
    await page.getByTestId("ws-input").fill(text);
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("ws-item")).toHaveCount(before + 1);
    return page.getByTestId("ws-item").last();
  };
  await expect(await send("Can I expense a client dinner abroad?")).toHaveAttribute("data-trust", "verified");
  const held = await send("Please update the bank details for vendor Orion Supplies before Friday's payment run.");
  await expect(held).toHaveAttribute("data-trust", "needs_review");
  await expect(held).toContainText("being reviewed by the compliance team");
  await expect(await send("Show Ravi Sharma's salary.")).toHaveAttribute("data-trust", "blocked");
});

test("agent action: high-value refund needs Finance Head approval, then executes", async ({ browser }) => {
  const analyst = await browser.newPage();
  await login(analyst, USERS.finance);
  await analyst.goto("/assistant");
  await analyst.getByTestId("mode-action").click();
  await analyst.getByTestId("composer").fill("Issue a refund for vendor invoice INV-2291");
  await analyst.keyboard.press("Enter");
  const card = analyst.getByTestId("action-card").last();
  await expect(card).toHaveAttribute("data-status", "PENDING_APPROVAL");
  await expect(card).toContainText("requires approval from the Finance Head");

  const head = await browser.newPage();
  await login(head, USERS.financeHead);
  await head.goto("/console/agents");
  await head.getByTestId("action-approvals").getByText("INV-2291").first().click();
  await head.getByTestId("approve-action").click();
  await head.fill("#confirm-note", "Duplicate invoice confirmed with the vendor");
  await head.getByTestId("confirm-action").click();
  await expect(head.getByTestId("action-controls")).not.toContainText("Approve");
  await expect(head.getByText("Refund recorded in the Finance Operations portal").first()).toBeVisible();

  // The requester's card updates live (it polls while the action is open).
  await expect(analyst.getByTestId("action-card").last()).toHaveAttribute("data-status", "EXECUTED", { timeout: 15_000 });
});

test("auditor can verify the hash-chained audit log", async ({ page }) => {
  await login(page, USERS.auditor);
  await page.goto("/console/audit");
  await expect(page.getByTestId("audit-table")).toBeVisible();
  await page.getByRole("button", { name: "Verify chain" }).click();
  await expect(page.getByTestId("chain-status")).toContainText("Chain intact");
});

test("roles: the admin can view a held case but only a Compliance Reviewer can decide it", async ({ page, request }) => {
  const token = await apiToken(request, USERS.employee);
  const chat = await (await request.post("/api/assistant/chat", {
    headers: { Authorization: `Bearer ${token}` }, data: { message: "Can I sue a vendor who delivered late?" },
  })).json();
  await login(page, USERS.admin);
  await page.goto(`/console/reviews/${chat.decision.review_case_id}`);
  await expect(page.getByTestId("case-prompt")).toContainText("sue a vendor");
  await expect(page.getByTestId("approve")).toHaveCount(0);

  await page.goto("/console/users");
  const row = page.locator("main").getByText("Rohan Das").locator("xpath=ancestor::tr[1]");
  await expect(row).toContainText("TrustShield Admin");
  await expect(row).not.toContainText("Compliance Reviewer");
});
