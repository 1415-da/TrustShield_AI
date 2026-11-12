/** Accounts in the live NovaCorp workspace, each showing TrustShield from a different seat. */
export const DEMO_PASSWORD = process.env.NEXT_PUBLIC_DEMO_PASSWORD ?? "TrustShield-demo-2024";

export const DEMO_ACCOUNTS = [
  { email: "ananya.rao@novacorp.test", name: "Ananya Rao", role: "Employee", note: "Uses the assistant", lands: "Assistant" },
  { email: "neha.kapoor@novacorp.test", name: "Neha Kapoor", role: "HR Manager", note: "Has compensation scope", lands: "Assistant" },
  { email: "kavya.menon@novacorp.test", name: "Kavya Menon", role: "Compliance Reviewer", note: "Works the review queue", lands: "Review queue" },
  { email: "rahul.verma@novacorp.test", name: "Rahul Verma", role: "Finance Analyst", note: "Requests agent actions", lands: "Assistant" },
  { email: "vivek.raman@novacorp.test", name: "Vivek Raman", role: "Finance Head", note: "Approves high-value actions", lands: "Agent approvals" },
  { email: "rohan.das@novacorp.test", name: "Rohan Das", role: "TrustShield Admin", note: "Policies, users, apps", lands: "Console" },
  { email: "sanjay.gupta@novacorp.test", name: "Sanjay Gupta", role: "Security / Audit", note: "Read-only oversight", lands: "Audit log" },
];
