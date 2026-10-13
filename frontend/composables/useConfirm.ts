// In-app confirmation dialog (replaces the browser's confirm(), which can't name
// what will be lost, can't be styled, and looks different on every device).
// Usage: if (!(await confirm({ title, message, confirmLabel: "Delete", danger: true }))) return;
export interface ConfirmRequest {
  title: string;
  message?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
}

interface Pending extends ConfirmRequest { resolve: (ok: boolean) => void }

export const useConfirm = () => {
  const pending = useState<Pending | null>("confirm_pending", () => null);
  const confirm = (req: ConfirmRequest) =>
    new Promise<boolean>((resolve) => {
      // a second request while one is open cancels the first
      pending.value?.resolve(false);
      pending.value = { ...req, resolve };
    });
  const answer = (ok: boolean) => {
    const p = pending.value;
    pending.value = null;
    p?.resolve(ok);
  };
  return { pending, confirm, answer };
};
