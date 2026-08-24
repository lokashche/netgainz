// Mirrors membership_plan.py PLAN_TYPE_DURATIONS: the cadence dictates the day
// count, so a plan form can show the number the moment a type is picked. The
// backend derives the same value on save; "Custom" is the only type where the
// owner types the days themselves.
export const PLAN_TYPE_DAYS: Record<string, number> = {
  Monthly: 30,
  Quarterly: 90,
  "Half-Yearly": 180,
  Yearly: 365,
};
