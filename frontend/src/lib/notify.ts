import { toast, type ToastOptions } from "react-toastify";

export type NotifyType = "success" | "error" | "info" | "warning";

type FeedbackLike = {
  type?: string | null;
  message?: string | null;
};

const BASE_OPTIONS: ToastOptions = {
  position: "top-right",
  autoClose: 4200,
  closeOnClick: true,
  pauseOnHover: true,
  draggable: true,
};

function normalizeType(value: string | null | undefined): NotifyType {
  const normalized = value?.trim().toLowerCase();
  if (normalized === "success") {
    return "success";
  }
  if (normalized === "error") {
    return "error";
  }
  if (normalized === "warning" || normalized === "warn") {
    return "warning";
  }
  return "info";
}

function cleanMessage(message: string): string {
  return message.trim();
}

export function notify(type: NotifyType, message: string, options?: ToastOptions): void {
  const normalized = cleanMessage(message);
  if (!normalized) {
    return;
  }

  const merged: ToastOptions = {
    ...BASE_OPTIONS,
    ...options,
  };

  if (type === "success") {
    toast.success(normalized, merged);
    return;
  }
  if (type === "error") {
    toast.error(normalized, merged);
    return;
  }
  if (type === "warning") {
    toast.warning(normalized, merged);
    return;
  }
  toast.info(normalized, merged);
}

export function notifyFeedback(feedback: FeedbackLike | null | undefined): void {
  if (!feedback?.message) {
    return;
  }
  notify(normalizeType(feedback.type), feedback.message);
}
