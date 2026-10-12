// SPDX-License-Identifier: AGPL-3.0-or-later
// Column resizer: drag with the pointer or focus it and use the arrow keys (WAI-ARIA window splitter).
import { useRef, type KeyboardEvent, type PointerEvent } from "react";

/** Limits of the side columns in px; the upper limit depends on the window width. */
export const COL_MIN = { catalog: 192, details: 256 } as const;
export const colMax = (): number => Math.max(320, Math.round(window.innerWidth * 0.4));
export const clampCol = (v: number, min: number, max: number): number => Math.round(Math.min(max, Math.max(min, v)));

export function Resizer({ label, value, min, max, onChange, invert = false }: {
  label: string; value: number; min: number; max: number; onChange: (px: number) => void;
  /** true for a column on the right side: dragging left makes it wider. */
  invert?: boolean;
}) {
  const drag = useRef<{ pointer: number; x0: number; v0: number } | null>(null);
  const sign = invert ? -1 : 1;
  const down = (e: PointerEvent<HTMLDivElement>) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    drag.current = { pointer: e.pointerId, x0: e.clientX, v0: value };
  };
  const move = (e: PointerEvent<HTMLDivElement>) => {
    const d = drag.current;
    if (d && d.pointer === e.pointerId) onChange(clampCol(d.v0 + sign * (e.clientX - d.x0), min, max));
  };
  const end = () => { drag.current = null; }; // pointerup, pointercancel, lostpointercapture
  const key = (e: KeyboardEvent<HTMLDivElement>) => {
    const step = e.shiftKey ? 64 : 16;
    const delta = e.key === "ArrowLeft" ? -step : e.key === "ArrowRight" ? step : 0;
    if (delta) onChange(clampCol(value + sign * delta, min, max));
    else if (e.key === "Home") onChange(min);
    else if (e.key === "End") onChange(max);
    else return;
    e.preventDefault();
  };
  return (
    <div className="resizer" role="separator" aria-orientation="vertical" aria-label={label} title={label} tabIndex={0}
      aria-valuenow={value} aria-valuemin={min} aria-valuemax={max}
      onPointerDown={down} onPointerMove={move} onPointerUp={end} onPointerCancel={end} onLostPointerCapture={end} onKeyDown={key} />
  );
}
