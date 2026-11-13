"use client";

import { useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Field, Textarea } from "@/components/ui/field";
import { useToast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api";

/** Confirmation for consequential actions. Optionally collects a note that is kept in the audit trail. */
export function ConfirmDialog({
  open, onClose, onConfirm, title, description, confirmLabel = "Confirm", tone = "primary", withNote = false, noteRequired = false,
  noteLabel = "Note (kept in the audit trail)", children,
}: {
  open: boolean; onClose: () => void; onConfirm: (note: string) => Promise<void> | void; title: string; description?: ReactNode;
  confirmLabel?: string; tone?: "primary" | "danger"; withNote?: boolean; noteRequired?: boolean; noteLabel?: string; children?: ReactNode;
}) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try {
      await onConfirm(note);
      setNote("");
      onClose();
    } catch {
      /* the caller surfaces the error (toast / inline); keep the dialog open so the user can retry */
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open={open} onClose={onClose} title={title} description={description}>
      <div className="space-y-4">
        {children}
        {withNote && (
          <Field label={noteLabel} htmlFor="confirm-note">
            <Textarea id="confirm-note" rows={3} value={note} onChange={(e) => setNote(e.target.value)} />
          </Field>
        )}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant={tone === "danger" ? "danger" : "primary"} onClick={() => void run()} loading={busy}
            disabled={noteRequired && !note.trim()} data-testid="confirm-action">{confirmLabel}</Button>
        </div>
      </div>
    </Dialog>
  );
}

interface ConfirmRequest {
  title: string;
  description?: ReactNode;
  confirmLabel: string;
  success: string;
  action: () => Promise<unknown>;
}

/**
 * The standard pattern for destructive actions: confirm → run → success toast, or error toast with the dialog kept
 * open. `ask({...})` opens the dialog; render `dialog` once in the page.
 */
export function useConfirm(): { ask: (r: ConfirmRequest) => void; dialog: ReactNode } {
  const [req, setReq] = useState<ConfirmRequest | null>(null);
  const toast = useToast();
  const dialog = req ? (
    <ConfirmDialog open onClose={() => setReq(null)} title={req.title} description={req.description} confirmLabel={req.confirmLabel} tone="danger"
      onConfirm={async () => {
        try {
          await req.action();
          toast({ tone: "success", title: req.success });
        } catch (e) {
          toast({ tone: "error", title: e instanceof ApiError ? e.message : "Something went wrong. Please try again." });
          throw e;
        }
      }} />
  ) : null;
  return { ask: setReq, dialog };
}
