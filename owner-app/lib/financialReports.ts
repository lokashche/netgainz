/** Stage 11.5: the financial reports the owner-app offers (keys match the backend). */
export const FINANCIAL_REPORTS: { key: string; label: string; periods: boolean }[] = [
  { key: "profit_and_loss", label: "Profit & Loss", periods: true },
  { key: "balance_sheet", label: "Balance Sheet", periods: true },
  { key: "cash_flow", label: "Cash Flow", periods: true },
  { key: "trial_balance", label: "Trial Balance", periods: false },
  { key: "general_ledger", label: "Day Book (every entry)", periods: false },
  { key: "cash_book", label: "Cash Book", periods: false },
  { key: "bank_book", label: "Bank Book", periods: false },
  { key: "receivables", label: "Who owes the gym (ageing)", periods: false },
];

export type FinancialReport = {
  report: string;
  title: string;
  columns: { fieldname: string; label: string; fieldtype: string }[];
  rows: (Record<string, string | number | null> & { _indent: number })[];
};

export function reportPath(q: { report: string; from: string; to: string; periodicity: string }, branch: string) {
  const qs = new URLSearchParams({ report: q.report, start: q.from, end: q.to, periodicity: q.periodicity });
  if (branch) qs.set("branch", branch);
  return `api/method/netgainz.net_gainz.accounting.financial_reports.get_financial_report?${qs.toString()}`;
}
