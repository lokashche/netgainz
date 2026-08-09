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

export type PlanType = 'Monthly' | 'Quarterly' | 'Half-Yearly' | 'Yearly' | 'Custom';
export type BillingMode = 'Commitment' | 'Pay-as-you-go';
export type PaymentDueRule = 'On joining' | 'Within 7 days' | 'By the 5th of next month';

export type MembershipPlan = {
  name: string;         // same as plan_name
  plan_name: string;
  plan_type?: PlanType;
  billing_mode?: BillingMode;
  duration_in_days?: number;
  amount?: number;
  payment_due_rule?: PaymentDueRule;
  installment_count?: number;
  installment_gap_days?: number;
  description?: string;
  is_active: 0 | 1;
};

/** One thing the member owes, and when. Both billing modes reduce to this. */
export type Obligation = {
  due_date: string | null;
  amount: number;
  outstanding: number;
  sales_invoice: string;
  payment_term: string | null;
  idx: number;
};

export type Obligations = {
  obligations: Obligation[];
  total: number;
  outstanding: number;
  refunded: number;
  written_off: number;
  advance_balance: number;
};

export type SubscriptionStatus =
  | 'Pending'
  | 'Paid'
  | 'Overdue'
  | 'Partial'
  // WP-8: settled as uncollectable rather than collected. ERPNext calls the
  // invoice "Paid" once the receivable is written off; the owner needs the truth.
  | 'Written Off';

export type Subscription = {
  name: string;         // SUB-2026-0001
  member: string;       // MEM-0001
  member_name?: string;
  membership_plan?: string;
  month?: string;
  /** What THIS member pays. Blank fills from the plan; a figure overrides it. */
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
  // WP-8 settlement, derived per current invoice (read-only).
  refunded_amount?: number;
  written_off_amount?: number;
  // Set once billing is provisioned. Absent means the membership has no
  // resolvable price, so nothing is being billed yet.
  subscription?: string | null;
  current_sales_invoice?: string | null;
};

/** WP-8: what a membership's money can still do, and what already happened. */
export type RefundContext = {
  sales_invoice: string | null;
  invoice_total?: number;
  refundable: number;
  credited: number;
  collected: number;
  reasons: string[];
};

export type RefundResult = {
  credit_note: string;
  payment_entry: string | null;
  cash_refunded: number;
  credit_applied: number;
  warnings: string[];
};

export type WriteOffContext = {
  sales_invoice: string | null;
  outstanding: number;
  written_off: number;
  reasons: string[];
};

export type MemberAdvance = {
  payment_entry: string;
  posting_date: string;
  paid_amount: number;
  unapplied: number;
  payment_mode?: string | null;
};

export type AdvanceContext = {
  balance: number;
  advances: MemberAdvance[];
};

/** WP-8: which product role the signed-in user holds, so the UI hides what they
 * cannot do rather than letting the server reject the click. */
export type Capabilities = {
  roles: string[];
  can_refund: boolean;
  can_write_off: boolean;
  can_record_payment: boolean;
  can_manage_finance: boolean;
};

export type AccountingMethod = 'Cash' | 'Accrual';

export type CommissionPercentageBasis = 'Assigned Member Revenue' | 'All Gym Revenue';

export type GymSettings = {
  accounting_method: AccountingMethod;
  member_id_prefix: string;
  commission_percentage_basis?: CommissionPercentageBasis;
  commission_post_to_ledger?: 0 | 1;
  commission_expense_account?: string;
  commission_payable_account?: string;
  renewal_reminder_days?: number;
  renewal_reminders_enabled?: 0 | 1;
  class_term_singular?: string;
  class_term_plural?: string;
  class_auto_generate?: 0 | 1;
  class_schedule_horizon_days?: number;
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

// ── Operations Depth — Stage 6 (Coaches, Programs, Classes, Commissions) ─────

export type CoachStatus = 'Active' | 'Inactive';
export type CoachCommissionType = 'None' | 'Fixed' | 'Per Member' | 'Percentage';

export type Coach = {
  name: string;          // same as coach_name
  coach_name: string;
  date_of_joining?: string;
  phone?: string;
  email?: string;
  specialization?: string;
  monthly_salary?: number;
  commission_type?: CoachCommissionType;
  commission_amount?: number;   // ₹ for Fixed/Per Member, percent for Percentage
  status: CoachStatus;
};

export type Program = {
  name: string;          // same as program_name
  program_name: string;
  description?: string;
  is_active: 0 | 1;
};

export type ClassSessionStatus = 'Scheduled' | 'Completed' | 'Cancelled';

export type ClassSession = {
  name: string;          // CLS-2026-0001
  title: string;
  program?: string;      // Link to Program
  coach?: string;        // Link to Coach
  start_time?: string;
  duration_mins?: number;
  capacity?: number;     // 0 = unlimited
  status: ClassSessionStatus;
  class_schedule?: string; // Link to Class Schedule (set when auto-generated)
  notes?: string;
  booked_count?: number; // augmented by the BFF, not stored on the doc
};

export type ClassSchedule = {
  name: string;          // CSCH-0001
  title: string;
  program?: string;      // Link to Program
  coach?: string;        // Link to Coach
  start_time?: string;   // "HH:MM:SS"
  duration_mins?: number;
  capacity?: number;     // 0 = unlimited
  on_monday: 0 | 1;
  on_tuesday: 0 | 1;
  on_wednesday: 0 | 1;
  on_thursday: 0 | 1;
  on_friday: 0 | 1;
  on_saturday: 0 | 1;
  on_sunday: 0 | 1;
  is_active: 0 | 1;
  notes?: string;
};

export type ClassBookingStatus = 'Booked' | 'Attended' | 'No Show' | 'Cancelled';

export type ClassBooking = {
  name: string;          // BKG-2026-0001
  class_session: string; // Link to Class Session
  member: string;        // Link to Member
  member_name?: string;
  coach?: string;        // Link to Coach (fetched from the session)
  start_time?: string;
  status: ClassBookingStatus;
  check_in_time?: string;
  notes?: string;
};

export type CoachCommissionLine = {
  coach: string;             // Link to Coach
  commission_type?: string;
  basis_label?: string;
  base_amount?: number;
  rate?: number;
  commission_amount?: number;
  member_count?: number;     // only present on a preview payload
};

export type CoachCommissionRun = {
  name: string;          // CCR-2026-0001
  period_start?: string;
  period_end?: string;
  company?: string;
  total_commission?: number;
  percentage_basis?: string;
  post_to_ledger: 0 | 1;
  commission_expense_account?: string;
  commission_payable_account?: string;
  journal_entry?: string;
  docstatus: DocStatus;
  lines?: CoachCommissionLine[];
};

export type CommissionPreview = {
  period_start: string;
  period_end: string;
  percentage_basis: string;
  total: number;
  lines: CoachCommissionLine[];
};

export type RenewalRow = {
  subscription: string;
  member: string;
  member_name?: string;
  phone?: string | null;
  membership_plan?: string;
  next_renewal: string;
  days_until: number;        // negative when overdue
  status: SubscriptionStatus;
};

export type RenewalsDue = {
  within_days: number;
  due_soon: RenewalRow[];
  overdue: RenewalRow[];
  due_soon_count: number;
  overdue_count: number;
};
