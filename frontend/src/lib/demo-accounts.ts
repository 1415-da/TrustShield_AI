import { ROLE_BY_KEY } from "@/lib/roles";

/** Accounts in the live NovaCorp workspace — one per job role, each showing TrustShield from a different seat. */
export const DEMO_PASSWORD = process.env.NEXT_PUBLIC_DEMO_PASSWORD ?? "TrustShield-demo-2024";

const PERSONAS: { email: string; name: string; roleKey: string; note: string }[] = [
  { email: "ananya.rao@novacorp.test", name: "Ananya Rao", roleKey: "employee", note: "Asks the assistant; approves nothing" },
  { email: "neha.kapoor@novacorp.test", name: "Neha Kapoor", roleKey: "hr_manager", note: "Sees salary bands; approves salary changes" },
  { email: "rahul.verma@novacorp.test", name: "Rahul Verma", roleKey: "finance_analyst", note: "Requests refunds and reimbursements" },
  { email: "aditya.kulkarni@novacorp.test", name: "Aditya Kulkarni", roleKey: "people_manager", note: "Approves INR 5k–50k claims and leave changes" },
  { email: "vivek.raman@novacorp.test", name: "Vivek Raman", roleKey: "finance_head", note: "Approves claims over INR 50k and refunds over 10k" },
  { email: "tara.bose@novacorp.test", name: "Tara Bose", roleKey: "security_admin", note: "Approves access removal and deletions" },
  { email: "kavya.menon@novacorp.test", name: "Kavya Menon", roleKey: "compliance_reviewer", note: "Decides held answers and policy changes" },
  { email: "sanjay.gupta@novacorp.test", name: "Sanjay Gupta", roleKey: "security_auditor", note: "Read-only oversight; verifies the audit chain" },
  { email: "rohan.das@novacorp.test", name: "Rohan Das", roleKey: "trustshield_admin", note: "Runs policies, users and apps; approves nothing" },
];

export const DEMO_ACCOUNTS = PERSONAS.map((p) => ({
  ...p,
  role: ROLE_BY_KEY[p.roleKey].label,
  lands: ROLE_BY_KEY[p.roleKey].homeLabel,
}));
