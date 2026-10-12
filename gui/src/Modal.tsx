// SPDX-License-Identifier: AGPL-3.0-or-later
import { useEffect, useRef, type ReactNode } from "react";

/** Native modal <dialog>: focus trap and focus restore by the browser, Escape calls onCancel. */
export function Modal({ open, title, onCancel, children }: { open: boolean; title: string; onCancel: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog ref={ref} aria-label={title} onCancel={(e) => { e.preventDefault(); onCancel(); }}>
      {open && (
        <div className="modal-body">
          <h2>{title}</h2>
          {children}
        </div>
      )}
    </dialog>
  );
}
