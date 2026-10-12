// SPDX-License-Identifier: AGPL-3.0-or-later
// Column resizer: drag with the pointer or focus it and use the arrow keys (WAI-ARIA window splitter).
import type { KeyboardEvent, PointerEvent } from "react";

export function Resizer({ label, value, min, max, onChange, invert = false }: {
  label: string; value: number; min: number; max: number; onChange: (px: number) => void;
  /** true for a column on the right side: dragging left makes it wider. */
  invert?: boolean;
}) {
  const clamp = (v: number) => Math.round(Math.min(max, Math.max(min, v)));
  const sign = invert ? -1 : 1;
  const down = (e: PointerEvent<HTMLDivElement>) => {
    const el = e.currentTarget;
    const x0 = e.clientX;
    el.setPointerCapture(e.pointerId);
    const move = (ev: globalThis.PointerEvent) => onChange(clamp(value + sign * (ev.clientX - x0)));
    const up = () => { el.removeEventListener("pointermove", move); el.removeEventListener("pointerup", up); };
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up);
  };
  const key = (e: KeyboardEvent<HTMLDivElement>) => {
    const step = e.shiftKey ? 64 : 16;
    const delta = e.key === "ArrowLeft" ? -step : e.key === "ArrowRight" ? step : 0;
    if (delta) onChange(clamp(value + sign * delta));
    else if (e.key === "Home") onChange(min);
    else if (e.key === "End") onChange(max);
    else return;
    e.preventDefault();
  };
  return (
    <div className="resizer" role="separator" aria-orientation="vertical" aria-label={label} title={label} tabIndex={0}
      aria-valuenow={value} aria-valuemin={min} aria-valuemax={max} onPointerDown={down} onKeyDown={key} />
  );
}
