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
  referred_by?: string;
  status: MemberStatus;
  inactive_reason?: string;
};

export type PlanType = 'Monthly' | 'Quarterly' | 'Half-Yearly' | 'Yearly' | 'Custom';
export type BillingMode = 'Commitment' | 'Pay-as-you-go';
export type PaymentDueRule = 'On joining' | 'Within 7 days' | 'By the 5th of next month';
/** How the gap between parts is counted. Months means the calendar month. */
export type GapUnit = 'Days' | 'Weeks' | 'Months';

export type MembershipPlan = {
  name: string;         // same as plan_name
  plan_name: string;
  plan_type?: PlanType;
  billing_mode?: BillingMode;
  duration_in_days?: number;
  amount?: number;
  payment_due_rule?: PaymentDueRule;
  installment_count?: number;
  /** How long after one part the next is due, counted in installment_gap_unit. */
  installment_gap_days?: number;
  installment_gap_unit?: GapUnit;
  /** DS-4: days a new member trains free before their first invoice. 0 = no trial. */
  trial_days?: number;
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
  // DS-4: enrolled on a free trial — nothing is invoiced until it ends, so this is
  // not "Pending payment"; no money is owed yet.
  | 'Trial'
  | 'Pending'
  | 'Paid'
  | 'Overdue'
  | 'Partial'
  // WP-8: settled as uncollectable rather than collected. ERPNext calls the
  // invoice "Paid" once the receivable is written off; the owner needs the truth.
  | 'Written Off'
  // OP-3: terminal — billing stopped, nothing renews, the status never re-derives.
  | 'Cancelled';

export type Subscription = {
  name: string;         // SUB-2026-0001
  member: string;       // MEM-0001
  member_name?: string;
  membership_plan?: string;
  month?: string;
  /** What THIS member pays. Blank fills from the plan; a figure overrides it. */
  tariff?: number;
  /** DS-4: set while a free trial runs. Billing starts the day after. */
  trial_ends_on?: string | null;
  trial_days?: number;
  skip_trial?: number;
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
  // Stage 8 DS-1: this member's negotiated discount. It changes the invoice, never
  // the plan's price, and always carries an explicit end (R18).
  /** The offer this membership was given, if any. It fills the discount fields below. */
  offer?: string | null;
  discount_type?: DiscountType;
  discount_value?: number;
  discount_duration?: DiscountDuration;
  discount_until?: string | null;
  discount_reason?: string;
  discount_granted_by?: string | null;
  // Set once billing is provisioned. Absent means the membership has no
  // resolvable price, so nothing is being billed yet.
  subscription?: string | null;
  current_sales_invoice?: string | null;
};

/** DS-6: one row of a discounts breakdown (by offer, reason, staff member or plan). */
export type DiscountGroup = {
  label: string;
  gross: number;
  given: number;
  net: number;
  invoices: number;
};

/** DS-6: what the gym gave away in a window, and what it cost. */
export type DiscountsGiven = {
  start: string;
  end: string;
  branch?: string | null;
  gross: number;
  given: number;
  net: number;
  given_percent: number;
  invoices: number;
  members: number;
  by_offer: DiscountGroup[];
  by_reason: DiscountGroup[];
  by_staff: DiscountGroup[];
  by_plan: DiscountGroup[];
  by_branch: DiscountGroup[];
  biggest: {
    sales_invoice: string;
    posting_date: string;
    membership: string;
    member_name?: string;
    membership_plan?: string;
    offer?: string | null;
    discount_reason?: string;
    discount_granted_by?: string;
    gross: number;
    given: number;
    net: number;
  }[];
  profit_impact: DiscountPreview["profit_impact"];
};

/** DS-6: the dashboard's one-liner. */
export type DiscountsThisMonth = {
  start: string;
  end: string;
  given: number;
  gross: number;
  given_percent: number;
  members: number;
  profit_impact: DiscountPreview["profit_impact"];
};

/** DS-5: one line of a membership's discount history. */
export type DiscountLogRow = {
  name: string;
  creation: string;
  action: "Given" | "Changed" | "Removed";
  granted_by?: string;
  approved?: 0 | 1;
  discount_type?: string;
  discount_value?: number;
  discount_duration?: string;
  discount_until?: string | null;
  offer?: string | null;
  previous_type?: string;
  previous_value?: number;
  reason?: string;
};

/** DS-4: a member on a free trial, and when it ends. */
export type TrialRow = {
  name: string;
  member: string;
  member_name?: string;
  membership_plan?: string;
  tariff?: number;
  trial_ends_on: string;
  status?: string;
};

export type TrialsEnding = {
  within_days: number;
  on_trial: number;
  ending_soon: TrialRow[];
  later: TrialRow[];
};

/** Stage 8 DS-2: a campaign the gym runs. Giving it to a member fills in their discount. */
export type Offer = {
  name: string;
  offer_name: string;
  description?: string;
  discount_type: "Percentage" | "Amount";
  discount_value: number;
  discount_duration: OfferDuration;
  valid_from: string;
  valid_upto?: string | null;
  max_total_uses?: number;
  branch?: string | null;
  disabled?: number;
  /** DS-3: set, and the offer is only reachable by quoting this code. */
  coupon_code?: string;
  max_uses_per_member?: number;
  plans?: { membership_plan: string }[];
};

/** What a typed coupon code turns out to be worth. */
export type RedeemedCoupon = {
  offer: string;
  offer_name: string;
  description?: string;
  coupon_code: string;
  discount_type: "Percentage" | "Amount";
  discount_value: number;
  discount_duration: OfferDuration;
  valid_upto?: string | null;
  uses_left: number | null;
};

export type OfferDuration = "First invoice only" | "Every invoice" | "Until the offer ends";

/** An offer the desk may give out right now, with how much of it is left. */
export type AvailableOffer = Pick<
  Offer,
  | "name"
  | "offer_name"
  | "description"
  | "discount_type"
  | "discount_value"
  | "discount_duration"
  | "valid_from"
  | "valid_upto"
  | "max_total_uses"
  | "branch"
> & {
  /** null when the offer has no limit. */
  uses_left: number | null;
  times_used: number;
};

/** Blank means no discount at all. */
export type DiscountType = "" | "Percentage" | "Amount";

export type DiscountDuration = "First invoice only" | "Every invoice" | "Until a date";

/** What a proposed discount costs — computed by the backend, never in the browser. */
export type DiscountPreview = {
  gross: number;
  discount: number;
  net: number;
  profit_impact: {
    amount: number;
    applicable: boolean;
    tier_code?: string | null;
    taps?: Record<string, number>;
    buckets: Record<string, number>;
  };
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

/** Go-live: one membership's billing-readiness row. */
export type ReadinessRow = {
  membership: string;
  member: string;
  member_name: string;
  membership_plan?: string;
  price: number;
  ready: boolean;
  already_billing: boolean;
  blocked_reason: string | null;
  joining_date: string | null;
  current_period_start?: string;
  next_period_start?: string;
  calendar_month_start?: string;
  part_month_days?: number;
  part_month_amount?: number;
  warnings: string[];
};

export type BillingReadiness = {
  total: number;
  ready_count: number;
  blocked_count: number;
  already_billing_count: number;
  warning_count: number;
  ready: ReadinessRow[];
  blocked: ReadinessRow[];
  start_modes: string[];
};

export type StartBillingResult = {
  dry_run: boolean;
  start_mode: string;
  bill_part_month: boolean;
  part_month_total: number;
  started_count: number;
  skipped_count: number;
  failed_count: number;
  started: {
    membership: string;
    member_name: string;
    price: number;
    first_invoice_on: string;
    part_month_amount?: number;
    part_month_days?: number;
    subscription?: string;
    warnings: string[];
  }[];
  skipped: { membership: string; reason: string }[];
  failed: { membership: string; error: string }[];
};

/** WP-8: which product role the signed-in user holds, so the UI hides what they
 * cannot do rather than letting the server reject the click. */
export type Capabilities = {
  roles: string[];
  can_refund: boolean;
  can_write_off: boolean;
  can_record_payment: boolean;
  can_manage_finance: boolean;
  // DS-5: the discount policy this user works under, so the desk can ask for the
  // owner's PIN at the right moment instead of after a refused save.
  can_discount_freely: boolean;
  max_discount_percent: number;
  complimentary_requires_owner: boolean;
  can_see_discount_history: boolean;
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
  /** DS-5: the discount policy. */
  max_discount_percent?: number;
  complimentary_requires_owner?: 0 | 1;
  renewal_reminder_days?: number;
  renewal_reminders_enabled?: 0 | 1;
  class_term_singular?: string;
  class_term_plural?: string;
  class_auto_generate?: 0 | 1;
  class_schedule_horizon_days?: number;
  absence_alert_days?: number;
  absence_alerts_enabled?: 0 | 1;
  followup_reminders_enabled?: 0 | 1;
  cancellation_refund_policy?: CancellationRefundPolicy;
  pack_expiry_alert_days?: number;
  pack_alerts_enabled?: 0 | 1;
  day_pass_price?: number;
  assessment_interval_days?: number;
  assessment_due_soon_days?: number;
  assessment_reminders_enabled?: 0 | 1;
  dues_reminder_days?: number;
  dues_reminders_enabled?: 0 | 1;
  recurring_expenses_enabled?: 0 | 1;
};

export type CancellationRefundPolicy = 'No refund' | 'Prorated unused days';

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

// ── OP-1: gym-wide check-in & attendance ────────────────────────────────────

export type CheckinSearchRow = {
  name: string;
  member_code?: string;
  full_name: string;
  phone?: string | null;
  status: MemberStatus;
  branch?: string;
  /** Timestamp of today's earliest check-in, null when not yet in. */
  checked_in_today: string | null;
};

/** The soft prompt: never blocks a check-in, only tells the desk. */
export type CheckinAlert = {
  overdue: boolean;
  frozen: boolean;
  balance_due: number;
  due_date: string | null;
  memberships: string[];
};

export type CheckinResult = {
  check_in: string;
  member: string;
  member_name?: string;
  timestamp: string;
  branch?: string;
  previous_today: string | null;
  alert: CheckinAlert | null;
};

export type VisitRow = {
  name: string;
  member: string;
  member_name?: string;
  timestamp: string;
  source: string;
  branch?: string;
};

export type TodaysVisits = {
  visits: VisitRow[];
  count: number;
};

export type ChurnRiskRow = {
  member: string;
  member_name?: string;
  phone?: string | null;
  branch?: string;
  last_visit: string | null;
  never_visited: boolean;
  days_absent: number;
};

export type ChurnRisk = {
  threshold_days: number;
  absent: ChurnRiskRow[];
  absent_count: number;
};

// ── OP-2: enquiry → trial → member pipeline ─────────────────────────────────

export type EnquiryStatus =
  | 'New'
  | 'Contacted'
  | 'Trial Scheduled'
  | 'Joined'
  | 'Lost';

export type EnquirySource = 'Walk-in' | 'Instagram' | 'Referral' | 'Other';

export type Enquiry = {
  name: string;
  full_name: string;
  phone?: string | null;
  email?: string | null;
  source: EnquirySource;
  referred_by?: string | null;
  interested_program?: string | null;
  status: EnquiryStatus;
  next_follow_up?: string | null;
  lost_reason?: string | null;
  notes?: string | null;
  member?: string | null;
  joined_on?: string | null;
  branch?: string;
};

export type FollowupRow = {
  enquiry: string;
  full_name: string;
  phone?: string | null;
  source: EnquirySource;
  interested_program?: string | null;
  status: EnquiryStatus;
  next_follow_up: string;
  days_overdue: number;
  branch?: string;
};

export type FollowupsDue = {
  due_today: FollowupRow[];
  overdue: FollowupRow[];
  due_today_count: number;
  overdue_count: number;
};

export type ConversionSourceRow = {
  source: string;
  total: number;
  joined: number;
  lost: number;
  open: number;
  /** joined / closed; null while a source has no closed enquiries yet. */
  conversion_pct: number | null;
};

export type ConversionBySource = {
  sources: ConversionSourceRow[];
  total: number;
};

export type ConvertResult = {
  enquiry: string;
  member: string;
  member_name?: string;
  already_converted: boolean;
};

// ── OP-3: membership lifecycle ──────────────────────────────────────────────

export type FreezeRow = {
  name: string;
  from_date: string;
  to_date: string;
  days_shifted: number;
  reason?: string | null;
};

export type FreezeResult = {
  freeze: string;
  days: number;
  next_bill_moved_from?: string | null;
  next_bill_moved_to?: string | null;
};

export type ChangePlanResult = {
  membership: string;
  old_plan: string;
  new_plan: string;
  credit: number;
  unused_days: number;
  invoice?: string | null;
};

export type CancelResult = {
  membership: string;
  cancelled_on: string;
  refund_policy: string;
  refund_amount: number;
};

export type TransferResult = {
  old_membership: string;
  new_membership: string;
  to_member: string;
  credit: number;
  unused_days: number;
};

// ── OP-4: session packs & day passes ────────────────────────────────────────

export type SessionPack = {
  name: string;
  pack_name: string;
  sessions: number;
  validity_days: number;
  price: number;
  is_active: 0 | 1;
  description?: string | null;
};

export type PackStatus = 'Active' | 'Exhausted' | 'Expired';

export type PackBalanceRow = {
  pack_purchase: string;
  member: string;
  member_name?: string;
  session_pack: string;
  used: number;
  total: number;
  remaining: number;
  purchased_on: string;
  expires_on: string;
  days_left: number;
  status: PackStatus;
};

export type PackBalances = {
  active: PackBalanceRow[];
  closed: PackBalanceRow[];
  active_count: number;
};

export type PackAlertRow = PackBalanceRow & {
  expiring: boolean;
  low_balance: boolean;
};

export type PackAlerts = {
  within_days: number;
  alerts: PackAlertRow[];
  alert_count: number;
};

export type PackSaleResult = {
  pack_purchase: string;
  member: string;
  member_name?: string;
  sessions: number;
  expires_on: string;
  amount: number;
  sales_invoice: string;
  payment_entry: string;
};

export type UseSessionResult = {
  pack_purchase: string;
  used: number;
  total: number;
  remaining: number;
  status: PackStatus;
};

export type DayPassRow = {
  name: string;
  guest_name: string;
  phone?: string | null;
  amount: number;
  payment_mode?: string;
  creation: string;
};

export type TodaysDayPasses = {
  passes: DayPassRow[];
  count: number;
  total: number;
};

export type DayPassSaleResult = {
  day_pass: string;
  guest_name: string;
  amount: number;
  sales_invoice: string;
  payment_entry: string;
};

// ── OP-5: fitness assessments & progress ────────────────────────────────────

export type MetricGroup = 'Body Composition' | 'Performance' | 'Other';
export type MetricDirection = 'Higher is better' | 'Lower is better';
export type MetricAppliesTo = 'Everyone' | 'Sport' | 'General';

export type AssessmentMetric = {
  name: string;              // same as metric_name
  unit: string;
  direction: MetricDirection;
  metric_group: MetricGroup;
  applies_to: MetricAppliesTo;
  description?: string | null;
  is_active: 0 | 1;
};

/** One reading the coach is about to file. */
export type MeasurementInput = {
  metric: string;
  value: number | string;
  note?: string;
};

export type ProgressReading = {
  date: string;
  value: number;
  assessment: string;
  note?: string | null;
};

/** One metric's whole story for one member. Deltas are signed so positive is
 *  always an improvement, whichever way the metric runs. */
export type ProgressSeries = {
  metric: string;
  unit: string;
  direction: MetricDirection;
  group: MetricGroup;
  is_builtin: 0 | 1;
  readings: ProgressReading[];
  count: number;
  current: number | null;
  current_date: string | null;
  change_since_last: number | null;
  change_since_first: number | null;
  target: number | null;
  target_date: string | null;
  target_name: string | null;
  baseline: number | null;
  percent_to_target: number | null;
};

export type ProgressVisit = {
  assessment: string;
  date: string;
  coach?: string | null;
  bmi?: number | null;
  age_years?: number | null;
  notes?: string | null;
};

export type MemberProgress = {
  member: string;
  member_name?: string | null;
  sport_goal?: string | null;
  category?: string | null;
  coach?: string | null;
  assessment_count: number;
  first_assessment: string | null;
  last_assessment: string | null;
  next_due_date: string | null;
  series: ProgressSeries[];
  visits: ProgressVisit[];
};

export type RecordAssessmentResult = {
  assessment: string;
  member: string;
  member_name?: string | null;
  assessment_date: string;
  bmi?: number | null;
  age_years?: number | null;
  next_due_date: string | null;
  branch?: string | null;
  progress: MemberProgress;
};

export type AssessmentDueRow = {
  member: string;
  member_name?: string | null;
  phone?: string | null;
  coach?: string | null;
  category?: string | null;
  sport_goal?: string | null;
  branch?: string | null;
  last_assessment: string;
  assessment: string;
  next_due_date: string;
  days_until: number;
};

export type AssessmentNeverRow = {
  member: string;
  member_name?: string | null;
  phone?: string | null;
  coach?: string | null;
  category?: string | null;
  sport_goal?: string | null;
  branch?: string | null;
};

export type AssessmentsDue = {
  within_days: number;
  due_soon: AssessmentDueRow[];
  overdue: AssessmentDueRow[];
  never_assessed: AssessmentNeverRow[];
  due_soon_count: number;
  overdue_count: number;
  never_assessed_count: number;
};

export type SetTargetResult = {
  target: string;
  member: string;
  metric: string;
  target_value: number;
  baseline_value?: number | null;
  branch?: string | null;
};

/* ── Data load (TL-1) ─────────────────────────────────────────────────────── */

export type DataLoadStatus =
  | 'Not started'
  | 'Importing'
  | 'Partial'
  | 'Complete'
  | 'Failed';

/** A problem found by reading the file. `error` blocks the load; `info` does not. */
export type DataLoadProblem = {
  rows: number[];
  message: string;
  kind: 'error' | 'info';
};

export type DataLoadValidation = {
  ok: boolean;
  step: string;
  label?: string;
  total_rows: number;
  already_loaded?: number;
  problems: DataLoadProblem[];
};

export type DataLoadFailure = {
  rows: string;
  message: string;
};

export type DataLoadStep = {
  key: string;
  label: string;
  blurb?: string;
  doctype: string;
  required_columns?: string[];
  step: string;
  status: DataLoadStatus;
  total_rows?: number;
  imported_rows?: number;
  failed_rows?: number;
  last_run?: string | null;
  message?: string | null;
  failures?: DataLoadFailure[];
  /** How many of this record type exist in the system right now. */
  loaded: number;
};

export type DataLoadRunResult = {
  started: boolean;
  validation: DataLoadValidation;
  status?: DataLoadStep;
  error?: string;
  /** Every row in the file is already loaded, so no import was started. */
  nothing_to_do?: boolean;
  message?: string;
};


/* ── Payment terms (WP-10 / per-member splits) ────────────────────────────── */

export type MembershipTerms = {
  membership: string;
  /** True when this member has terms of their own rather than the plan's. */
  uses_own_terms: boolean;
  payment_due_rule: PaymentDueRule;
  installment_count: number;
  installment_gap_days: number;
  installment_gap_unit: GapUnit;
  /** The policy in plain words, e.g. "Pays in 2 parts every month". */
  summary: string;
  plan: string | null;
  plan_summary: string;
  due_rules: PaymentDueRule[];
  gap_units: GapUnit[];
  max_installments: number;
};

export type DueRow = {
  membership: string;
  member: string;
  member_name: string | null;
  membership_plan: string | null;
  branch: string | null;
  due_date: string;
  amount: number;
  outstanding: number;
  sales_invoice: string | null;
  part: number | null;
  days_late: number;
};

export type Collections = {
  within_days: number;
  late: DueRow[];
  due_today: DueRow[];
  due_soon: DueRow[];
  total_late: number;
  total_due_today: number;
  total_due_soon: number;
};


/* ── Repeating expenses ───────────────────────────────────────────────────── */

export type RepeatingRow = {
  root: string;
  category: string | null;
  amount: number;
  vendor: string | null;
  frequency: string;
  last_raised: string;
  /** Dates waiting to be raised as drafts. */
  due: string[];
  /** How many further periods were beyond the catch-up cap. */
  skipped: number;
};

export type RepeatingExpenses = {
  rows: RepeatingRow[];
  due_now: number;
  max_catch_up: number;
};
