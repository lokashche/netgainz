"use client";

import { useState, useEffect, useRef, useId, useCallback, KeyboardEvent } from "react";

export type LinkFieldOption = {
  id: string;
  label: string;
  sub?: string;
};

interface LinkFieldPickerProps {
  value: string;
  displayLabel?: string;
  onChange: (id: string, label: string) => void;
  fetchOptions: (q: string) => Promise<LinkFieldOption[]>;
  placeholder?: string;
  required?: boolean;
  emptyHint?: string;
  inputClassName: string;
  disabled?: boolean;
}

export default function LinkFieldPicker({
  value,
  displayLabel,
  onChange,
  fetchOptions,
  placeholder,
  required = false,
  emptyHint = "No matches",
  inputClassName,
  disabled = false,
}: LinkFieldPickerProps) {
  const listboxId = useId();
  const wrapperRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const requestSeq = useRef(0);

  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [options, setOptions] = useState<LinkFieldOption[]>([]);
  const [highlight, setHighlight] = useState(0);

  const selectedText = displayLabel ?? value ?? "";
  const inputValue = open ? query : selectedText;

  const runFetch = useCallback(
    async (q: string) => {
      const seq = ++requestSeq.current;
      setLoading(true);
      try {
        const opts = await fetchOptions(q);
        if (seq === requestSeq.current) {
          setOptions(opts);
          setHighlight(0);
        }
      } catch {
        if (seq === requestSeq.current) {
          setOptions([]);
        }
      } finally {
        if (seq === requestSeq.current) {
          setLoading(false);
        }
      }
    },
    [fetchOptions]
  );

  useEffect(() => {
    if (!open) return;
    const handle = setTimeout(() => {
      runFetch(query.trim());
    }, 200);
    return () => clearTimeout(handle);
  }, [query, open, runFetch]);

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (!wrapperRef.current?.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  function selectOption(opt: LinkFieldOption) {
    onChange(opt.id, opt.label);
    setOpen(false);
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (!open && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
      setOpen(true);
      e.preventDefault();
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlight((h) => Math.min(h + 1, options.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlight((h) => Math.max(h - 1, 0));
    } else if (e.key === "Enter") {
      if (open && options[highlight]) {
        e.preventDefault();
        selectOption(options[highlight]);
      }
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  function handleChange(next: string) {
    setQuery(next);
    if (!open) setOpen(true);
    if (next === "" && value) {
      onChange("", "");
    }
  }

  return (
    <div ref={wrapperRef} className="relative">
      <input
        ref={inputRef}
        type="text"
        role="combobox"
        aria-expanded={open}
        aria-controls={listboxId}
        aria-autocomplete="list"
        autoComplete="off"
        required={required}
        disabled={disabled}
        value={inputValue}
        placeholder={placeholder}
        onFocus={() => {
          setQuery("");
          setOpen(true);
        }}
        onChange={(e) => handleChange(e.target.value)}
        onKeyDown={handleKeyDown}
        className={inputClassName}
      />
      {/* Hidden input ensures the resolved id is what gets submitted, not the query text */}
      <input type="hidden" value={value} readOnly />

      {open && (
        <ul
          id={listboxId}
          role="listbox"
          className="absolute z-20 mt-1 w-full max-h-64 overflow-y-auto rounded-lg border border-[#1E2D45] bg-[#1A2540] shadow-lg"
        >
          {loading && (
            <li className="px-3 py-2 text-sm text-[#8A97B2]">Searching…</li>
          )}
          {!loading && options.length === 0 && (
            <li className="px-3 py-2 text-sm text-[#8A97B2]">{emptyHint}</li>
          )}
          {!loading &&
            options.map((opt, idx) => {
              const active = idx === highlight;
              return (
                <li
                  key={opt.id}
                  role="option"
                  aria-selected={active}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    selectOption(opt);
                  }}
                  onMouseEnter={() => setHighlight(idx)}
                  className={`cursor-pointer px-3 py-2 text-sm ${
                    active
                      ? "bg-[#22D38C] text-[#0B1220]"
                      : "text-[#E6EDF7] hover:bg-[#111A2E]"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate">{opt.label}</span>
                    <span
                      className={`font-mono text-xs shrink-0 ${
                        active ? "text-[#0B1220]/70" : "text-[#8A97B2]"
                      }`}
                    >
                      {opt.id}
                    </span>
                  </div>
                  {opt.sub && (
                    <div
                      className={`text-xs truncate ${
                        active ? "text-[#0B1220]/70" : "text-[#8A97B2]"
                      }`}
                    >
                      {opt.sub}
                    </div>
                  )}
                </li>
              );
            })}
        </ul>
      )}
    </div>
  );
}
