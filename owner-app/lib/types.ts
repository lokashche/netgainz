export type MemberStatus = 'Active' | 'Inactive' | 'Frozen';

export type Member = {
  name: string; // MEM-0001
  full_name: string;
  phone?: string;
  email?: string;
  date_of_birth?: string;
  blood_group?: string;
  address?: string;
  emergency_contact?: string;
  date_of_joining?: string;
  category?: string;
  source_of_reference?: string;
  status: MemberStatus;
  inactive_reason?: string;
};

export type MembershipPlan = {
  name: string;         // same as plan_name
  plan_name: string;
  duration_in_days?: number;
  amount?: number;
  description?: string;
  is_active: 0 | 1;
};

export type SubscriptionStatus = 'Pending' | 'Paid' | 'Overdue' | 'Partial';

export type Subscription = {
  name: string;         // SUB-2026-0001
  member: string;       // MEM-0001
  member_name?: string;
  membership_plan?: string;
  month?: string;
  tariff?: number;
  fee_collected?: number;
  payment_mode?: string;
  balance_due?: number;
  due_date?: string;
  paid_date?: string;
  split_due_date?: string;
  next_renewal?: string;
  overdue_days?: number;
  status: SubscriptionStatus;
  comments?: string;
};

export type AccountingMethod = 'Cash' | 'Accrual';

export type GymSettings = {
  accounting_method: AccountingMethod;
  member_id_prefix: string;
};

export type PFBucket =
  | 'Operating Expenses'
  | "Owner's Pay"
  | 'Tax'
  | 'Pass-Through';

export type ExpenseCategory = {
  name: string;        // same as category_name
  category_name: string;
  pf_bucket?: PFBucket;
  description?: string;
};

export type ExpenseFrequency = 'Monthly' | 'Quarterly' | 'Annually';

// ── Profit First — Stage 5a Instant Assessment (read-only) ──────────────────

export type PFAllocationBucket = 'Profit' | "Owner's Pay" | 'Tax' | 'Operating Expenses';

export type AssessmentRow = {
  bucket: PFAllocationBucket;
  label: string;            // "Undistributed Cash (residual)" for the Profit row
  actual: number;
  cap_pct: number | null;   // Current Allocation % (null when not applicable)
  tap_pct: number | null;   // Target Allocation %
  target: number | null;    // Target ₹
  gap: number | null;       // Actual − Target, in ₹
  gap_pct: number | null;   // CAP − TAP
};

export type InstantAssessment = {
  enabled: boolean;
  applicable?: boolean;
  basis?: string;           // "Cash"
  window?: string;          // "Trailing 12 Months" | "This Month"
  period_label?: string;
  topline?: number;
  passthrough?: number;
  real_revenue?: number;
  tier_code?: string | null;
  tier_provisional?: boolean;
  rows?: AssessmentRow[];
  notice?: string | null;
  warnings?: string[];
  profit_is_residual?: boolean;
  passthrough_breakdown?: { category: string; amount: number }[];
};

// ── Profit First sweep (Stage 5b) ───────────────────────────────────────────

// 0 = Draft, 1 = Posted, 2 = Cancelled
export type DocStatus = 0 | 1 | 2;

export type PFSweepAllocation = {
  account_role: PFAllocationBucket;
  pf_account?: string;
  target_pct?: number;
  amount?: number;
  cost_center?: string;
};

export type PFSweep = {
  name: string;
  sweep_date?: string;
  assessment_window?: string;
  company?: string;
  real_revenue?: number;
  tier_code?: string;
  period_label?: string;
  income_account?: string;
  income_cost_center?: string;
  journal_entry?: string;
  docstatus: DocStatus;
  allocations?: PFSweepAllocation[];
};

// ── Profit First dashboard + schedule (Stage 5c) ────────────────────────────

export type PFReserve = {
  role: PFAllocationBucket;
  account?: string | null;
  balance: number;
};

export type PFDashboard = {
  enabled: boolean;
  accounts_ready?: boolean;
  reserves?: PFReserve[];
  allocation_days?: string;
  auto_create?: boolean;
  next_sweep_date?: string | null;
  pending_sweeps?: {
    name: string;
    sweep_date?: string;
    real_revenue?: number;
    tier_code?: string;
  }[];
  last_sweep?: {
    name: string;
    sweep_date?: string;
    real_revenue?: number;
    journal_entry?: string;
  } | null;
};

export type GymExpense = {
  name: string;        // EXP-2026-0001
  date?: string;
  category?: string;   // Link to Expense Category name
  amount?: number;
  vendor?: string;
  is_recurring: 0 | 1;
  frequency?: ExpenseFrequency | '';
  notes?: string;
};
