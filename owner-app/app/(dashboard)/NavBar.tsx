"use client";

import { useState, useRef, useEffect } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import LogoutButton from "./LogoutButton";

type NavItem = { href: string; label: string };

const SETUP_ITEMS: NavItem[] = [
  { href: "/members", label: "Members" },
  { href: "/coaches", label: "Coaches" },
  { href: "/programs", label: "Programs" },
  { href: "/plans", label: "Plans" },
  { href: "/offers", label: "Offers" },
  { href: "/expense-categories", label: "Categories" },
];

const CASHFLOW_ITEMS: NavItem[] = [
  { href: "/subscriptions", label: "Subscriptions" },
  { href: "/expenses", label: "Expenses" },
  { href: "/discounts", label: "Discounts" },
  // Go-live: members loaded from the gym's own records are not billed until the
  // owner switches them on here.
  { href: "/billing", label: "Start Billing" },
];

const linkClass =
  "text-sm font-medium px-3 py-2 rounded-lg text-[#8A97B2] hover:text-[#E6EDF7] hover:bg-[#1A2540] transition-colors";

const activeLinkClass =
  "text-sm font-medium px-3 py-2 rounded-lg text-[#E6EDF7] bg-[#1A2540]";

function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

function NavGroup({
  label,
  items,
  pathname,
}: {
  label: string;
  items: NavItem[];
  pathname: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const groupActive = items.some((it) => isActive(pathname, it.href));

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    }
    if (open) document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className={`${groupActive ? activeLinkClass : linkClass} inline-flex items-center gap-1`}
      >
        {label}
        <svg
          className={`w-3 h-3 transition-transform ${open ? "rotate-180" : ""}`}
          viewBox="0 0 12 12"
          fill="none"
          aria-hidden="true"
        >
          <path
            d="M3 4.5L6 7.5L9 4.5"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>

      {open && (
        <div
          role="menu"
          className="absolute left-0 mt-1 min-w-[180px] rounded-lg border border-[#1E2D45] bg-[#111A2E] shadow-lg py-1 z-20"
        >
          {items.map((it) => {
            const active = isActive(pathname, it.href);
            return (
              <Link
                key={it.href}
                href={it.href}
                role="menuitem"
                onClick={() => setOpen(false)}
                className={`block px-3 py-2 text-sm transition-colors ${
                  active
                    ? "text-[#22D38C] bg-[#1A2540]"
                    : "text-[#8A97B2] hover:text-[#E6EDF7] hover:bg-[#1A2540]"
                }`}
              >
                {it.label}
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function NavBar({
  fullName,
  classTermSingular,
  classTermPlural,
}: {
  fullName: string;
  classTermSingular: string;
  classTermPlural: string;
}) {
  const pathname = usePathname();

  const OPERATIONS_ITEMS: NavItem[] = [
    { href: "/check-in", label: "Check-in" },
    { href: "/classes", label: classTermPlural },
    { href: "/schedules", label: `${classTermSingular} Schedules` },
    { href: "/attendance", label: "Attendance" },
    { href: "/churn-risk", label: "Churn Risk" },
    { href: "/commissions", label: "Commissions" },
    { href: "/renewals", label: "Renewals" },
  ];

  return (
    <nav className="bg-[#111A2E] border-b border-[#1E2D45] sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex flex-wrap items-center gap-x-4 gap-y-2 py-2 sm:py-0 sm:flex-nowrap justify-between">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
          <Link href="/dashboard" className="font-bold tracking-wide text-[#E6EDF7]">
            NetGain<span className="text-[#22D38C]">Z</span>
          </Link>
          <Link
            href="/dashboard"
            className={isActive(pathname, "/dashboard") ? activeLinkClass : linkClass}
          >
            Dashboard
          </Link>
          <NavGroup label="Setup" items={SETUP_ITEMS} pathname={pathname} />
          <NavGroup label="Cashflow" items={CASHFLOW_ITEMS} pathname={pathname} />
          <NavGroup label="Operations" items={OPERATIONS_ITEMS} pathname={pathname} />
          <Link
            href="/profit-first"
            className={isActive(pathname, "/profit-first") ? activeLinkClass : linkClass}
          >
            Profit First
          </Link>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/settings"
            aria-label="Settings"
            className={`p-1.5 rounded-lg transition-colors ${
              isActive(pathname, "/settings")
                ? "text-[#22D38C] bg-[#1A2540]"
                : "text-[#8A97B2] hover:text-[#E6EDF7] hover:bg-[#1A2540]"
            }`}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
            </svg>
          </Link>
          <span className="text-sm text-[#8A97B2] hidden sm:inline">{fullName}</span>
          <LogoutButton />
        </div>
      </div>
    </nav>
  );
}
