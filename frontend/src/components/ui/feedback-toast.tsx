import { useEffect } from "react";

import { notifyFeedback } from "@/lib/notify";

type FeedbackToastState =
  | {
      type?: string | null;
      message?: string | null;
    }
  | null
  | undefined;

type FeedbackToastProps = {
  feedback: FeedbackToastState;
};

export function FeedbackToast({ feedback }: FeedbackToastProps) {
  useEffect(() => {
    notifyFeedback(feedback);
  }, [feedback]);

  return null;
}
