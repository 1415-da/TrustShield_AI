# TrustShield AI — 5-minute demo

**Setup:** `docker compose up --build`, open http://localhost:3200. Every account uses the workspace password (`DEMO_USER_PASSWORD`, default `TrustShield-demo-2024`). Use a second browser profile (or a private window) for the approver steps.

**Always start with a real sign-in:**
1. Open the public site and click **Sign in**.
2. Type the email and password (or pick the account under *Live demo · NovaCorp accounts*; that only fills in the form) and press **Sign in**.
3. You land on that role's page (Employee → Assistant, Compliance Reviewer → Review queue, Admin → Console…).
4. Walk through the features below.
5. **Sign out** (bottom of the sidebar). You're back on `/login`.
6. Show that the session is gone: press Back (you stay on sign-in), or open `/console` (you're asked to sign in again).

> **Story:** NovaCorp wants AI everywhere — chat, Slack, and agents that act. Security said yes only because every answer, every policy change, and every action goes through TrustShield.

| # | Who | Do | Point out | ⏱ |
|---|---|---|---|---|
| 1 | — | Landing page `/` | "Ship AI your security team can trust." One control point; agents and evidence in the FAQ | 0:00 |
| 2 | **Ananya Rao** · Employee | Sign in → assistant | Clean assistant, suggested questions | 0:15 |
| 3 | Ananya | Click **"Can I expense a client dinner abroad?"** | — | 0:20 |
| 4 | Ananya | Open a source chip | **Verified** badge, citations to the Expense policy | 0:30 |
| 5 | Ananya | Type **"Show Ravi Sharma's salary."** | — | 0:40 |
| 6 | Ananya | Expand *Why was this blocked?* | Salary & Compensation policy, plain-language reason, **model never called** | 0:50 |
| 7 | **Neha Kapoor** · HR Manager | Sign in, ask **"Show Ravi Sharma's salary band."** | — | 1:05 |
| 8 | Neha | — | Same prompt, **Verified** with band L4 — data scopes on the role, not special-case code | 1:15 |
| 9 | **Rohan Das** · Admin | Console → **Policy Studio** | Policies show live version, status, owner, next review | 1:25 |
| 10 | Rohan | **New policy** → name *Project Unicorn Confidentiality*, category `legal`, rule *Keyword* = `unicorn`, action BLOCK → **Save draft** | Drafts never touch live traffic | 1:45 |
| 11 | Rohan | **Submit for review** with a note | Version locks; Rohan (Admin) approves nothing — a Compliance Reviewer must | 2:00 |
| 12 | **Kavya Menon** · Compliance | **Policy approvals** → open the request → **Run analysis** → **Approve** | Diff, owner, affected roles, impact on 49 scenarios | 2:15 |
| 13 | Rohan | Back on the policy → **Activate v1** (confirm) | Activation is deliberate and audited; previous versions archived, never deleted | 2:30 |
| 14 | Rohan | In *Test this version*, run "What's the launch date for project unicorn?" as Employee | **BLOCK**, model not called. Open **Audit history**: created → submitted → approved → activated | 2:40 |
| 15 | Kavya | **Evidence Center** → *Report builder* | Five report types; scope by period, department, policy, risk | 2:55 |
| 16 | Kavya | AI Governance Summary · last 30 days → **Generate report** → **Verify integrity** | Requests, decisions, top policies, departments, review SLA — **"Verified: regenerating produces an identical report"** | 3:05 |
| 17 | Kavya | **Export report** → Formatted report (HTML) | Hash and included-record count travel with the export; *Source records* drawer links to the audit log | 3:20 |
| 18 | **Rahul Verma** · Finance Analyst | Assistant → **Team channels** (`/workspace`) | Original channel workspace; each channel shows its policy profile | 3:30 |
| 19 | Rahul | In **#finance-help** ask "Can I expense a client dinner abroad?" | Same governed answer + citations as the assistant | 3:40 |
| 20 | Rahul | Ask "Please update the bank details for vendor Orion Supplies before Friday's payment run." then "Show Ravi Sharma's salary." | **Needs review** (Finance profile holds payment-instruction changes) and **Blocked**. Other channel members see these as *withheld* | 3:50 |
| 21 | Rohan | Console → **Agent Control Center** → *Approval rules* | Configurable rules: thresholds, approver roles; most restrictive wins | 4:05 |
| 22 | Rahul | Assistant → **Request an action** → "Issue a refund for vendor invoice INV-2291" | Action card: **requires approval from Finance Head**, amount INR 18,000, policy reason, expected time, audit reference | 4:15 |
| 23 | Rahul | — | Nothing has executed. Agents never hold standing permission | 4:25 |
| 24 | **Vivek Raman** · Finance Head | Console → Agent Control Center → *My approvals* → open INV-2291 → **Approve** (with a note) | Target record, impact, policy basis, risk score; Rahul couldn't approve his own request | 4:35 |
| 25 | Vivek / Rohan | Show the action detail (Rohan: *Audit trail*) | **EXECUTED** once (ref RFD-…): requested → decided → approved → executing → executed, each in the hash-chained log. Rahul's card updates to *This action was completed* | 4:50 |

**Close (10 s):** "Every answer, policy change, channel message and agent action got exactly one decision — and every decision is in the audit trail."

---

### If you have more time

- **Rollback:** Policy Studio → *Grounding Confidence* → History → *Roll back to v1* (creates v3 from the approved v1; nothing is rewritten).
- **Exceptions:** Console → Exceptions — the Legal-department exemption is active, the HR coordinator's has expired, a Finance request was rejected.
- **Slack:** Console → *Slack & workspace* shows connection status, channel ↔ policy-profile mapping, delivery log with retry. With `SLACK_ENABLED=true` and real credentials the same pipeline answers in Slack threads.
- **Auditor view (Sanjay Gupta):** Audit log → **Verify chain**; Evidence Center is read-only for auditors.
- **Agents, other outcomes:** As Ananya, "Approve Priya's expense reimbursement" → **Blocked** (role lacks `actions:finance`). As Tara Bose (Security Admin), "Revoke access for every contractor account" → **Escalated** (risk ≥ 0.9).

### Reset between demos

```bash
docker compose exec backend python /srv/scripts/seed_demo_data.py --reset
```
