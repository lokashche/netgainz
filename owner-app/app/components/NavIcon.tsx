/**
 * One icon per screen, drawn as inline SVG.
 *
 * Deliberately not an icon library: the whole owner app has three runtime
 * dependencies, and 26 outlines are not worth a fourth. Every path below is
 * drawn on the same 24x24 grid with the same 1.75 stroke and round caps, so
 * the set reads as one family.
 *
 * Add a screen to the nav and it falls back to a neutral dot rather than
 * breaking the row.
 */

const PATHS: Record<string, React.ReactNode> = {
  "/dashboard": (
    <>
      <rect x="3" y="3" width="7" height="9" rx="1.5" />
      <rect x="14" y="3" width="7" height="5" rx="1.5" />
      <rect x="14" y="12" width="7" height="9" rx="1.5" />
      <rect x="3" y="16" width="7" height="5" rx="1.5" />
    </>
  ),
  "/profit-first": (
    <>
      <path d="M21 12a9 9 0 1 1-9-9v9z" />
      <path d="M21 8a9 9 0 0 0-5-5" />
    </>
  ),

  /* Setup */
  "/members": (
    <>
      <circle cx="9" cy="8" r="3.2" />
      <path d="M3 20a6 6 0 0 1 12 0" />
      <path d="M17 11a2.6 2.6 0 1 0 0-5.2" />
      <path d="M18 20a5.2 5.2 0 0 0-2-4" />
    </>
  ),
  "/coaches": (
    <>
      <circle cx="12" cy="7.5" r="3.2" />
      <path d="M5.5 20a6.5 6.5 0 0 1 13 0" />
      <path d="m12 12.8 1 2 2.2.3-1.6 1.5.4 2.2-2-1-2 1 .4-2.2L8.8 15l2.2-.3z" />
    </>
  ),
  "/programs": (
    <>
      <path d="m12 3 8.5 4.5L12 12 3.5 7.5z" />
      <path d="m3.5 12 8.5 4.5L20.5 12" />
      <path d="m3.5 16.5 8.5 4.5 8.5-4.5" />
    </>
  ),
  "/plans": (
    <>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="M3 10h18" />
      <path d="M7 15h4" />
    </>
  ),
  "/offers": (
    <>
      <path d="M20.6 12.4 12.4 20.6a2 2 0 0 1-2.8 0l-6.2-6.2a2 2 0 0 1-.6-1.5l.3-5.4a2 2 0 0 1 1.9-1.9l5.4-.3a2 2 0 0 1 1.5.6l6.7 6.7a2 2 0 0 1 0 2.8z" />
      <circle cx="8.2" cy="8.2" r="1.3" />
    </>
  ),
  "/expense-categories": (
    <>
      <path d="M3 7a2 2 0 0 1 2-2h4l2 2.5h8a2 2 0 0 1 2 2V17a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
    </>
  ),

  /* Cashflow */
  "/subscriptions": (
    <>
      <path d="M3 12a9 9 0 0 1 15.5-6.2L21 8" />
      <path d="M21 4v4h-4" />
      <path d="M21 12a9 9 0 0 1-15.5 6.2L3 16" />
      <path d="M3 20v-4h4" />
    </>
  ),
  "/collections": (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M9 8h6" />
      <path d="M9 11h6" />
      <path d="M9 8c3 0 4.5 1 4.5 3S12 14 9 14l5 4" />
    </>
  ),
  "/expenses": (
    <>
      <path d="M3 8a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2" />
      <rect x="3" y="8" width="18" height="11" rx="2" />
      <path d="M12 11v5" />
      <path d="m9.6 13.6 2.4 2.4 2.4-2.4" />
    </>
  ),
  "/discounts": (
    <>
      <path d="M6 18 18 6" />
      <circle cx="7.8" cy="7.8" r="2.3" />
      <circle cx="16.2" cy="16.2" r="2.3" />
    </>
  ),
  "/billing": (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="m10 8.5 6 3.5-6 3.5z" />
    </>
  ),

  /* Operations */
  "/enquiries": (
    <>
      <path d="M20 13a2 2 0 0 1-2 2H8l-4 4V6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2z" />
      <path d="M12 7.5v3" />
      <path d="M12 12.8h.01" />
    </>
  ),
  "/check-in": (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="m8 12.2 2.6 2.6L16 9.4" />
    </>
  ),
  "/packs": (
    <>
      <path d="m12 3 8 4.2v9.6L12 21l-8-4.2V7.2z" />
      <path d="M4 7.2 12 11.5l8-4.3" />
      <path d="M12 11.5V21" />
    </>
  ),
  "/day-pass": (
    <>
      <path d="M3 9.5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2 2.5 2.5 0 0 0 0 5 2 2 0 0 1-2 2H5a2 2 0 0 1-2-2 2.5 2.5 0 0 0 0-5z" />
      <path d="M14 8v8" />
    </>
  ),
  "/classes": (
    <>
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M3 10h18" />
      <path d="M8 3v4" />
      <path d="M16 3v4" />
    </>
  ),
  "/schedules": (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5.2l3.4 2" />
    </>
  ),
  "/attendance": (
    <>
      <rect x="5" y="4" width="14" height="17" rx="2" />
      <path d="M9 3h6v3H9z" />
      <path d="m9 12.5 1.8 1.8 3.6-3.6" />
      <path d="M9 17.5h6" />
    </>
  ),
  "/churn-risk": (
    <>
      <path d="M10.3 4.3 2.6 17.5A1.9 1.9 0 0 0 4.3 20.4h15.4a1.9 1.9 0 0 0 1.7-2.9L13.7 4.3a1.9 1.9 0 0 0-3.4 0z" />
      <path d="M12 9.5v4" />
      <path d="M12 16.8h.01" />
    </>
  ),
  "/assessments": (
    <>
      <path d="M4 20V10" />
      <path d="M10 20V4" />
      <path d="M16 20v-7" />
      <path d="M3 20h18" />
    </>
  ),
  "/commissions": (
    <>
      <path d="M3 12h4l2.5 6 5-13 2.5 7h4" />
    </>
  ),
  "/renewals": (
    <>
      <path d="M20.5 11a8.5 8.5 0 1 0-1.6 6" />
      <path d="M20.5 21v-5h-5" />
      <path d="M12 7.5V12l3 1.8" />
    </>
  ),
  "/data-load": (
    <>
      <path d="M20 15.5V19a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-3.5" />
      <path d="M12 15V3.5" />
      <path d="m7.8 7.7 4.2-4.2 4.2 4.2" />
    </>
  ),

  "/settings": (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.1 14.4a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-2.7 1.1V21a2 2 0 1 1-4 0v-.1a1.6 1.6 0 0 0-2.7-1.1l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0-1.1-2.7H3a2 2 0 1 1 0-4h.1a1.6 1.6 0 0 0 1.1-2.7l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 2.7-1.1V3a2 2 0 1 1 4 0v.1a1.6 1.6 0 0 0 2.7 1.1l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0 1.1 2.7H21a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.8 1.1z" />
    </>
  ),

  /* Opens the full menu. Not a route — keyed by name. */
  more: (
    <>
      <path d="M4 7h16" />
      <path d="M4 12h16" />
      <path d="M4 17h16" />
    </>
  ),
};

export default function NavIcon({
  href,
  className = "w-5 h-5",
}: {
  /** A route such as "/members", or "more" for the menu button. */
  href: string;
  className?: string;
}) {
  const path = PATHS[href] ?? <circle cx="12" cy="12" r="3.5" />;
  return (
    <svg
      className={`${className} shrink-0`}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {path}
    </svg>
  );
}
