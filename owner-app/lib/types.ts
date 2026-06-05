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

export type ExpenseCategory = {
  name: string;        // same as category_name
  category_name: string;
  description?: string;
};

export type ExpenseFrequency = 'Monthly' | 'Quarterly' | 'Annually';

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
