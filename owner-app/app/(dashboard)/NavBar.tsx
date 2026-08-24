"use client";

import { useState, useRef, useEffect } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import LogoutButton from "./LogoutButton";
import NavIcon from "@/app/components/NavIcon";

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
  // Where the daily money reminder points: one line per unpaid part.
  { href: "/collections", label: "Money to Collect" },
  { href: "/expenses", label: "Expenses" },
  { href: "/discounts", label: "Discounts" },
  // Go-live: members loaded from the gym's own records are not billed until the
  // owner switches them on here.
  { href: "/billing", label: "Start Billing" },
];

const BOTTOM_TABS: NavItem[] = [
  { href: "/dashboard", label: "Home" },
  { href: "/collections", label: "Money" },
  { href: "/check-in", label: "Check-in" },
  { href: "/members", label: "Members" },
];

const linkClass =
  "text-sm font-medium px-3 py-2 rounded-lg text-[#8A97B2] hover:text-[#E6EDF7] hover:bg-[#1A2540] transition-colors";

const activeLinkClass =
  "text-sm font-medium px-3 py-2 rounded-lg text-[#E6EDF7] bg-[#1A2540]";

function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

/* ── Desktop / tablet: a drop-down per group ────────────────────────── */

function NavGroup({
  label,
  items,
  pathname,
  align = "left",
}: {
  label: string;
  items: NavItem[];
  pathname: string;
  /* Groups near the right edge open leftwards so the menu stays on screen
     on a narrow tablet. */
  align?: "left" | "right";
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
        className={`${groupActive ? activeLinkClass : linkClass} inline-flex items-center gap-1 whitespace-nowrap`}
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
          className={`absolute ${align === "right" ? "right-0" : "left-0"} mt-1 w-[min(220px,calc(100vw-2rem))] max-h-[70vh] overflow-y-auto rounded-lg border border-[#1E2D45] bg-[#111A2E] shadow-lg py-1 z-20`}
        >
          {items.map((it) => {
            const active = isActive(pathname, it.href);
            return (
              <Link
                key={it.href}
                href={it.href}
                role="menuitem"
                onClick={() => setOpen(false)}
                className={`flex items-center gap-2.5 px-3 py-2 text-sm transition-colors ${
                  active
                    ? "text-[#22D38C] bg-[#1A2540]"
                    : "text-[#8A97B2] hover:text-[#E6EDF7] hover:bg-[#1A2540]"
                }`}
              >
                <NavIcon href={it.href} className="w-4 h-4" />
                {it.label}
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ── Phone: one drawer, groups folded shut until you tap one ────────── */

function DrawerSection({
  label,
  items,
  pathname,
  open,
  onToggle,
  onNavigate,
}: {
  label: string;
  items: NavItem[];
  pathname: string;
  open: boolean;
  onToggle: () => void;
  onNavigate: () => void;
}) {
  // Expanding all three groups makes a 23-line list you have to scroll.
  // Folded, the whole menu fits one phone screen.
  const groupActive = items.some((it) => isActive(pathname, it.href));

  return (
    <div>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="w-full flex items-center justify-between gap-3 min-h-[48px] px-4 text-sm font-semibold text-left transition-colors hover:bg-[#1A2540]"
      >
        <span className={groupActive ? "text-[#22D38C]" : "text-[#E6EDF7]"}>
          {label}
        </span>
        <span className="flex items-center gap-2 shrink-0">
          {/* A dot marks the group you are currently inside while it is shut. */}
          {groupActive && !open && (
            <span className="w-1.5 h-1.5 rounded-full bg-[#22D38C]" aria-hidden="true" />
          )}
          <svg
            className={`w-4 h-4 text-[#8A97B2] transition-transform ${open ? "rotate-180" : ""}`}
            viewBox="0 0 16 16"
            fill="none"
            aria-hidden="true"
          >
            <path
              d="M4 6L8 10L12 6"
              stroke="currentColor"
              strokeWidth="1.75"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </span>
      </button>

      {open && (
        <div className="pb-2">
          {items.map((it) => {
            const active = isActive(pathname, it.href);
            return (
              <Link
                key={it.href}
                href={it.href}
                onClick={onNavigate}
                className={`flex items-center gap-3 min-h-[44px] pl-9 pr-4 text-sm transition-colors border-l-[3px] ${
                  active
                    ? "text-[#22D38C] bg-[#1A2540] border-[#22D38C]"
                    : "text-[#E6EDF7] hover:bg-[#1A2540] border-transparent"
                }`}
              >
                <NavIcon href={it.href} className="w-[18px] h-[18px]" />
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
  const [menuOpen, setMenuOpen] = useState(false);

  const OPERATIONS_ITEMS: NavItem[] = [
    { href: "/enquiries", label: "Enquiries" },
    { href: "/check-in", label: "Check-in" },
    { href: "/packs", label: "Packs" },
    { href: "/day-pass", label: "Day Pass" },
    { href: "/classes", label: classTermPlural },
    { href: "/schedules", label: `${classTermSingular} Schedules` },
    { href: "/attendance", label: "Attendance" },
    { href: "/churn-risk", label: "Churn Risk" },
    { href: "/assessments", label: "Assessments" },
    { href: "/commissions", label: "Commissions" },
    { href: "/renewals", label: "Renewals" },
    // TL-1: loading the gym's own register, in the owner app rather than Frappe Desk.
    { href: "/data-load", label: "Load Records" },
  ];

  const GROUPS = [
    { key: "setup", label: "Setup", items: SETUP_ITEMS },
    { key: "cashflow", label: "Cashflow", items: CASHFLOW_ITEMS },
    { key: "operations", label: "Operations", items: OPERATIONS_ITEMS },
  ];

  // Which group holds the page you are on right now.
  const activeGroup =
    GROUPS.find((g) => g.items.some((it) => isActive(pathname, it.href)))?.key ?? null;

  // One group open at a time, so the menu always fits one screen.
  const [openSection, setOpenSection] = useState<string | null>(null);

  // Tapping a link navigates without unmounting the bar, so close by hand.
  const closeMenu = () => setMenuOpen(false);

  function toggleMenu() {
    if (menuOpen) {
      setMenuOpen(false);
      return;
    }
    // Opening: unfold the group you are already in, so you can see where
    // you are without hunting for it.
    setOpenSection(activeGroup);
    setMenuOpen(true);
  }

  // A route change always closes the drawer, however it was triggered —
  // a link, the back button, anything. Derived during render rather than in
  // an effect, so there is no second render pass showing a stale open menu.
  const [lastPath, setLastPath] = useState(pathname);
  if (lastPath !== pathname) {
    setLastPath(pathname);
    setMenuOpen(false);
  }

  // Escape closes it, and the page behind must not scroll under the drawer.
  useEffect(() => {
    if (!menuOpen) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setMenuOpen(false);
    }
    document.addEventListener("keydown", onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [menuOpen]);

  const settingsIcon = (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  );

  return (
    <nav className="bg-[#111A2E] border-b border-[#1E2D45] sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center gap-x-2 lg:gap-x-4 justify-between">
        {/* Left: brand, then the full menu on tablet and up */}
        <div className="flex items-center gap-x-2 lg:gap-x-4 min-w-0">
          <Link
            href="/dashboard"
            className="font-bold tracking-wide text-[#E6EDF7] whitespace-nowrap"
          >
            NetGain<span className="text-[#22D38C]">Z</span>
          </Link>

          <div className="hidden md:flex items-center gap-x-1 lg:gap-x-2">
            <Link
              href="/dashboard"
              className={`${isActive(pathname, "/dashboard") ? activeLinkClass : linkClass} whitespace-nowrap`}
            >
              Dashboard
            </Link>
            <NavGroup label="Setup" items={SETUP_ITEMS} pathname={pathname} />
            <NavGroup label="Cashflow" items={CASHFLOW_ITEMS} pathname={pathname} />
            <NavGroup
              label="Operations"
              items={OPERATIONS_ITEMS}
              pathname={pathname}
              align="right"
            />
            <Link
              href="/profit-first"
              className={`${isActive(pathname, "/profit-first") ? activeLinkClass : linkClass} whitespace-nowrap`}
            >
              Profit First
            </Link>
          </div>
        </div>

        {/* Right: settings + who is signed in, and the phone menu button */}
        <div className="flex items-center gap-2 sm:gap-3 shrink-0">
          <Link
            href="/settings"
            aria-label="Settings"
            className={`hidden md:inline-flex p-2 rounded-lg transition-colors ${
              isActive(pathname, "/settings")
                ? "text-[#22D38C] bg-[#1A2540]"
                : "text-[#8A97B2] hover:text-[#E6EDF7] hover:bg-[#1A2540]"
            }`}
          >
            {settingsIcon}
          </Link>
          <span className="text-sm text-[#8A97B2] hidden lg:inline truncate max-w-[12rem]">
            {fullName}
          </span>
          <div className="hidden md:block">
            <LogoutButton />
          </div>

          <button
            type="button"
            onClick={toggleMenu}
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            aria-expanded={menuOpen}
            aria-controls="mobile-menu"
            className="md:hidden inline-flex items-center justify-center w-11 h-11 -mr-2 rounded-lg text-[#E6EDF7] hover:bg-[#1A2540] transition-colors"
          >
            <svg
              width="22"
              height="22"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              aria-hidden="true"
            >
              {menuOpen ? (
                <>
                  <path d="M18 6 6 18" />
                  <path d="m6 6 12 12" />
                </>
              ) : (
                <>
                  <path d="M3 6h18" />
                  <path d="M3 12h18" />
                  <path d="M3 18h18" />
                </>
              )}
            </svg>
          </button>
        </div>
      </div>

      {/* Phone drawer. Sits under the bar, scrolls on its own, dims the page. */}
      {menuOpen && (
        <>
          <div
            className="md:hidden fixed inset-0 top-14 bg-black/50 z-30"
            onClick={closeMenu}
            aria-hidden="true"
          />
          <div
            id="mobile-menu"
            className="md:hidden absolute left-0 right-0 top-14 z-40 bg-[#111A2E] border-b border-[#1E2D45] shadow-xl max-h-[calc(100dvh-3.5rem)] overflow-y-auto overscroll-contain"
          >
            <div className="py-2 pb-[calc(4.5rem+env(safe-area-inset-bottom))] divide-y divide-[#1E2D45]">
              <div className="py-2">
                <Link
                  href="/dashboard"
                  onClick={closeMenu}
                  className={`flex items-center gap-3 min-h-[44px] px-4 text-sm font-medium transition-colors ${
                    isActive(pathname, "/dashboard")
                      ? "text-[#22D38C] bg-[#1A2540]"
                      : "text-[#E6EDF7] hover:bg-[#1A2540]"
                  }`}
                >
                  <NavIcon href="/dashboard" className="w-[18px] h-[18px]" />
                  Dashboard
                </Link>
                <Link
                  href="/profit-first"
                  onClick={closeMenu}
                  className={`flex items-center gap-3 min-h-[44px] px-4 text-sm font-medium transition-colors ${
                    isActive(pathname, "/profit-first")
                      ? "text-[#22D38C] bg-[#1A2540]"
                      : "text-[#E6EDF7] hover:bg-[#1A2540]"
                  }`}
                >
                  <NavIcon href="/profit-first" className="w-[18px] h-[18px]" />
                  Profit First
                </Link>
              </div>

              {GROUPS.map((g) => (
                <DrawerSection
                  key={g.key}
                  label={g.label}
                  items={g.items}
                  pathname={pathname}
                  open={openSection === g.key}
                  onToggle={() =>
                    setOpenSection((cur) => (cur === g.key ? null : g.key))
                  }
                  onNavigate={closeMenu}
                />
              ))}

              {/* Signed-in row, last so the menu reads top-to-bottom */}
              <div className="py-2">
                <Link
                  href="/settings"
                  onClick={closeMenu}
                  className={`flex items-center gap-3 min-h-[44px] px-4 text-sm transition-colors ${
                    isActive(pathname, "/settings")
                      ? "text-[#22D38C] bg-[#1A2540]"
                      : "text-[#E6EDF7] hover:bg-[#1A2540]"
                  }`}
                >
                  <NavIcon href="/settings" className="w-[18px] h-[18px]" />
                  Settings
                </Link>
                <div className="flex items-center justify-between gap-3 px-4 min-h-[44px]">
                  <span className="text-sm text-[#8A97B2] truncate">{fullName}</span>
                  <LogoutButton />
                </div>
              </div>
            </div>
          </div>
        </>
      )}

      {/* ── Phone: the four daily screens, always within thumb reach ──
          Fixed to the bottom of the window. "More" opens the same drawer as
          the hamburger above. pb-[env(safe-area-inset-bottom)] keeps the row
          clear of the iPhone home bar — that is what viewportFit:"cover" in
          app/layout.tsx was for. */}
      <div className="md:hidden fixed bottom-0 left-0 right-0 z-50 bg-[#111A2E] border-t border-[#1E2D45] pb-[env(safe-area-inset-bottom)]">
        <div className="grid grid-cols-5">
          {BOTTOM_TABS.map((t) => {
            const active = isActive(pathname, t.href);
            return (
              <Link
                key={t.href}
                href={t.href}
                aria-current={active ? "page" : undefined}
                className={`flex flex-col items-center justify-center gap-1 min-h-[56px] px-1 py-1.5 transition-colors ${
                  active ? "text-[#22D38C]" : "text-[#8A97B2] active:bg-[#1A2540]"
                }`}
              >
                <NavIcon href={t.href} className="w-[22px] h-[22px]" />
                <span className="text-[10px] font-medium leading-none truncate max-w-full">
                  {t.label}
                </span>
              </Link>
            );
          })}

          <button
            type="button"
            onClick={toggleMenu}
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            aria-expanded={menuOpen}
            aria-controls="mobile-menu"
            className={`flex flex-col items-center justify-center gap-1 min-h-[56px] px-1 py-1.5 transition-colors ${
              menuOpen ? "text-[#22D38C]" : "text-[#8A97B2] active:bg-[#1A2540]"
            }`}
          >
            <NavIcon href="more" className="w-[22px] h-[22px]" />
            <span className="text-[10px] font-medium leading-none">More</span>
          </button>
        </div>
      </div>
    </nav>
  );
}
