"use client";

import { useState, useEffect } from "react";
import type { GymSettings } from "@/lib/types";

export type ClassTerm = { singular: string; plural: string };

const DEFAULT: ClassTerm = { singular: "Class", plural: "Classes" };

// Module-level cache so the gym's term isn't refetched on every navigation.
let cached: ClassTerm | null = null;

// Client hook: returns the gym's configured word for a class (e.g. "Batch").
// Falls back to "Class"/"Classes" until the setting loads.
export function useClassTerm(): ClassTerm {
  const [term, setTerm] = useState<ClassTerm>(cached ?? DEFAULT);

  useEffect(() => {
    if (cached) return;
    let alive = true;
    fetch("/api/settings")
      .then((res) => (res.ok ? res.json() : null))
      .then((body: { data?: GymSettings } | null) => {
        if (!alive || !body?.data) return;
        cached = {
          singular: body.data.class_term_singular || "Class",
          plural: body.data.class_term_plural || "Classes",
        };
        setTerm(cached);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  return term;
}
