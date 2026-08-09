"use client";

/**
 * A listbox that can show more than text.
 *
 * A native `<select>` cannot render a colour swatch or set a per-option
 * typeface — browsers style option lists themselves. Both matter here: the
 * filament list is 25 colours where the name alone ("Caramel", "Pumpkin
 * Orange") is a poor substitute for seeing it, and the lettering list is asking
 * the customer to choose a typeface, which they can only do by looking at it.
 *
 * So this is hand-rolled, and it carries the keyboard and ARIA behaviour a
 * native select gives away free: roving focus with arrows, Home/End, Escape to
 * close, type-ahead, and `aria-activedescendant` so a screen reader follows.
 */

import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";

export type DropdownItem = {
  id: string;
  label: string;
  /** Second line, when there is something worth saying. */
  description?: string;
  disabled?: boolean;
  /** Colour chip drawn before the label. */
  swatch?: string;
  /** Render this item's label in a specific face — see fontFaces() in spec.ts. */
  fontFamily?: string;
  fontWeight?: number;
  fontItalic?: boolean;
};

type Props = {
  items: DropdownItem[];
  value: string;
  onChange: (id: string) => void;
  ariaLabel: string;
  /** Sample text drawn in each item's own typeface, when one is given. */
  sample?: string;
};

export default function Dropdown({ items, value, onChange, ariaLabel, sample }: Props) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const typed = useRef({ buffer: "", at: 0 });
  const listId = useId();

  const selectedIndex = useMemo(
    () => Math.max(0, items.findIndex((i) => i.id === value)),
    [items, value],
  );
  const selected = items[selectedIndex];

  const close = useCallback(() => setOpen(false), []);

  useEffect(() => {
    if (!open) return;
    setActive(selectedIndex);
    const onDocDown = (e: MouseEvent) => {
      if (!root.current?.contains(e.target as Node)) close();
    };
    document.addEventListener("mousedown", onDocDown);
    return () => document.removeEventListener("mousedown", onDocDown);
  }, [open, selectedIndex, close]);

  // Keep the active option in view when arrowing through a long palette.
  useEffect(() => {
    if (!open || !listRef.current) return;
    listRef.current.children[active]?.scrollIntoView({ block: "nearest" });
  }, [open, active]);

  const commit = (index: number) => {
    const item = items[index];
    if (!item || item.disabled) return;
    onChange(item.id);
    close();
  };

  const step = (delta: number) => {
    setActive((current) => {
      let next = current;
      for (let i = 0; i < items.length; i++) {
        next = (next + delta + items.length) % items.length;
        if (!items[next].disabled) return next;
      }
      return current;
    });
  };

  function onKeyDown(e: React.KeyboardEvent) {
    switch (e.key) {
      case "ArrowDown":
      case "ArrowUp":
        e.preventDefault();
        if (!open) { setOpen(true); return; }
        step(e.key === "ArrowDown" ? 1 : -1);
        return;
      case "Home":
      case "End":
        if (!open) return;
        e.preventDefault();
        setActive(e.key === "Home" ? 0 : items.length - 1);
        return;
      case "Enter":
      case " ":
        e.preventDefault();
        if (open) commit(active);
        else setOpen(true);
        return;
      case "Escape":
        if (open) { e.preventDefault(); close(); }
        return;
      case "Tab":
        close();
        return;
    }

    // Type-ahead. Resets after a pause, so "ca" finds Caramel but a later "c"
    // starts again rather than searching for "cac".
    if (e.key.length === 1 && !e.metaKey && !e.ctrlKey && !e.altKey) {
      const now = performance.now();
      typed.current.buffer = now - typed.current.at > 600 ? e.key : typed.current.buffer + e.key;
      typed.current.at = now;
      const q = typed.current.buffer.toLowerCase();
      const hit = items.findIndex((i) => !i.disabled && i.label.toLowerCase().startsWith(q));
      if (hit >= 0) {
        if (open) setActive(hit);
        else onChange(items[hit].id);
      }
    }
  }

  const styleFor = (item: DropdownItem): React.CSSProperties =>
    item.fontFamily
      ? {
          fontFamily: `"${item.fontFamily}", var(--font-body), sans-serif`,
          fontWeight: item.fontWeight ?? 400,
          fontStyle: item.fontItalic ? "italic" : "normal",
        }
      : {};

  return (
    <div className={`dd${open ? " open" : ""}`} ref={root}>
      <button
        type="button"
        className="dd-trigger"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={ariaLabel}
        onClick={() => setOpen((o) => !o)}
        onKeyDown={onKeyDown}
      >
        {selected?.swatch ? (
          <span className="dd-chip" style={{ background: selected.swatch }} aria-hidden />
        ) : null}
        <span className="dd-value" style={styleFor(selected ?? { id: "", label: "" })}>
          {sample && selected?.fontFamily ? sample : selected?.label}
        </span>
        {sample && selected?.fontFamily ? (
          <span className="dd-sub">{selected.label}</span>
        ) : null}
        <span className="dd-caret" aria-hidden />
      </button>

      {open ? (
        <ul
          className="dd-list"
          id={listId}
          role="listbox"
          ref={listRef}
          aria-label={ariaLabel}
          aria-activedescendant={`${listId}-${active}`}
          tabIndex={-1}
        >
          {items.map((item, i) => (
            <li
              key={item.id}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={item.id === value}
              aria-disabled={item.disabled || undefined}
              className={`dd-item${i === active ? " active" : ""}${item.id === value ? " sel" : ""}${item.disabled ? " off" : ""}`}
              onMouseEnter={() => setActive(i)}
              onMouseDown={(e) => e.preventDefault()} // keep focus on the trigger
              onClick={() => commit(i)}
            >
              {item.swatch ? (
                <span className="dd-chip" style={{ background: item.swatch }} aria-hidden />
              ) : null}
              <span className="dd-text">
                <span className="dd-label" style={styleFor(item)}>
                  {sample && item.fontFamily ? sample : item.label}
                </span>
                {item.description || (sample && item.fontFamily) ? (
                  <span className="dd-desc">
                    {sample && item.fontFamily ? `${item.label} · ` : ""}
                    {item.description}
                  </span>
                ) : null}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
