"use client";

import { useState, useEffect } from "react";
import type { Branch } from "@/lib/types";

export type BranchChoice = {
  /** Branches that are switched on, default first. */
  branches: Branch[];
  /** Name of the default branch, or "" until loaded. */
  defaultBranch: string;
  /** True when the gym runs more than one branch — only then is a picker shown. */
  multi: boolean;
};

const EMPTY: BranchChoice = { branches: [], defaultBranch: "", multi: false };

// Module-level cache so every form doesn't refetch the list. The Branches screen
// calls forgetBranches() after a change so the next form sees it.
let cached: BranchChoice | null = null;

export function forgetBranches() {
  cached = null;
}

// Stage 10.2: the gym's active branches for a form's branch picker. A gym with
// one branch gets multi = false, and the picker stays hidden.
export function useBranches(): BranchChoice {
  const [choice, setChoice] = useState<BranchChoice>(cached ?? EMPTY);

  useEffect(() => {
    if (cached) return;
    let alive = true;
    fetch("/api/branches")
      .then((res) => (res.ok ? res.json() : null))
      .then((body: { message?: Branch[] } | null) => {
        if (!alive || !body?.message) return;
        const active = body.message.filter((b) => !b.disabled);
        cached = {
          branches: active,
          defaultBranch: active.find((b) => b.is_default)?.name ?? active[0]?.name ?? "",
          multi: active.length > 1,
        };
        setChoice(cached);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  return choice;
}

// Stage 10.2: which branch a front-desk device is at (check-in, day passes).
// Remembered on the device so a desk tablet is set once. Browser storage can be
// unavailable (private mode); callers then fall back to the default branch.
const DESK_BRANCH_KEY = "netgainz.deskBranch";

export function readDeskBranch(): string {
  try {
    return typeof window === "undefined" ? "" : window.localStorage.getItem(DESK_BRANCH_KEY) ?? "";
  } catch {
    return "";
  }
}

export function rememberDeskBranch(value: string) {
  try {
    window.localStorage.setItem(DESK_BRANCH_KEY, value);
  } catch {
    /* not remembered on this device — still used for this session */
  }
}

/** The desk's branch: the remembered one if still active, else the default. */
export function useDeskBranch(): [string, (value: string) => void] {
  const { branches, defaultBranch } = useBranches();
  const [remembered, setRemembered] = useState(readDeskBranch);
  const desk = branches.some((b) => b.name === remembered) ? remembered : defaultBranch;
  const setDesk = (value: string) => {
    setRemembered(value);
    rememberDeskBranch(value);
  };
  return [desk, setDesk];
}
