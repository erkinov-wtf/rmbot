import { MinusCircle, PlusCircle, RefreshCcw, Search, Sparkles, UserRound } from "lucide-react";
import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { FeedbackToast } from "@/components/ui/feedback-toast";
import { useI18n } from "@/i18n";
import { adjustUserXp, listUserOptions, type UserOption } from "@/lib/api";
import { cn } from "@/lib/utils";

type XpAdminProps = {
  accessToken: string;
  canManage: boolean;
  roleSlugs: string[];
};

type FeedbackState =
  | {
      type: "success" | "error";
      message: string;
    }
  | null;

type AdjustmentMode = "add" | "remove";

const fieldClassName = "rm-input";

function toErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}

export function XpAdmin({
  accessToken,
  canManage,
  roleSlugs,
}: XpAdminProps) {
  const { t } = useI18n();
  const [users, setUsers] = useState<UserOption[]>([]);
  const [searchInput, setSearchInput] = useState("");
  const [activeQuery, setActiveQuery] = useState("");
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [mode, setMode] = useState<AdjustmentMode>("add");
  const [amountInput, setAmountInput] = useState("");
  const [comment, setComment] = useState("");
  const [isLoadingUsers, setIsLoadingUsers] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<FeedbackState>(null);

  const selectedUser = useMemo(
    () => users.find((user) => user.id === selectedUserId) ?? null,
    [selectedUserId, users],
  );

  const loadUsers = useCallback(
    async (query: string) => {
      if (!canManage) {
        setUsers([]);
        setSelectedUserId(null);
        return;
      }

      setIsLoadingUsers(true);
      try {
        const nextUsers = await listUserOptions(accessToken, {
          q: query,
          per_page: 200,
        });
        setUsers(nextUsers);
        setSelectedUserId((prev) => {
          if (prev && nextUsers.some((user) => user.id === prev)) {
            return prev;
          }
          return nextUsers[0]?.id ?? null;
        });
    } catch (error) {
      setFeedback({
        type: "error",
        message: toErrorMessage(error, t("Failed to load users.")),
      });
    } finally {
      setIsLoadingUsers(false);
    }
  },
    [accessToken, canManage, t],
  );

  useEffect(() => {
    void loadUsers(activeQuery);
  }, [activeQuery, loadUsers]);

  const handleSearchSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFeedback(null);
    setActiveQuery(searchInput.trim());
  };

  const handleAdjustSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canManage) {
      setFeedback({
        type: "error",
        message: t("Only admin roles can adjust XP."),
      });
      return;
    }

    if (!selectedUser) {
      setFeedback({
        type: "error",
        message: t("Select a user first."),
      });
      return;
    }

    const parsedAmount = Number.parseInt(amountInput, 10);
    if (!Number.isInteger(parsedAmount) || parsedAmount <= 0) {
      setFeedback({
        type: "error",
        message: t("Amount must be an integer greater than 0."),
      });
      return;
    }

    const normalizedComment = comment.trim();
    if (!normalizedComment) {
      setFeedback({
        type: "error",
        message: t("Comment is required."),
      });
      return;
    }

    const signedAmount = mode === "add" ? parsedAmount : -parsedAmount;
    setIsSubmitting(true);
    setFeedback(null);
    try {
      await adjustUserXp(accessToken, {
        user_id: selectedUser.id,
        amount: signedAmount,
        comment: normalizedComment,
      });
      const signedLabel = signedAmount > 0 ? `+${signedAmount}` : `${signedAmount}`;
      setFeedback({
        type: "success",
        message: t("XP updated ({{amount}}) for {{name}}.", {
          amount: signedLabel,
          name: selectedUser.display_name,
        }),
      });
      setAmountInput("");
      setComment("");
    } catch (error) {
      setFeedback({
        type: "error",
        message: toErrorMessage(error, t("Failed to adjust XP.")),
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section className="rm-panel rm-animate-enter-delayed p-4 sm:p-5">
      <div
        className="flex flex-col gap-3 border-b border-slate-200/70 pb-4 sm:flex-row sm:items-start sm:justify-between"
      >
        <div>
          <h2 className="text-lg font-semibold text-slate-900">{t("XP Control")}</h2>
          <p className="mt-1 text-sm text-slate-600">
            {t("Admin-only XP adjustments with required comment and Telegram notification.")}
          </p>
          {!canManage ? (
            <p className="mt-2 text-xs text-amber-700">
              {t("Roles ({{roles}}) cannot manage XP.", {
                roles: roleSlugs.join(", ") || t("none"),
              })}
            </p>
          ) : null}
        </div>

        <Button
          type="button"
          variant="outline"
          className="h-10 w-full sm:w-auto"
          onClick={() => {
            void loadUsers(activeQuery);
          }}
          disabled={isLoadingUsers || isSubmitting || !canManage}
        >
          <RefreshCcw className="mr-2 h-4 w-4" />
          {t("Refresh users")}
        </Button>
      </div>

      <FeedbackToast feedback={feedback} />

      {!canManage ? (
        <p
          className="mt-4 rounded-md border border-dashed border-slate-300 px-3 py-6 text-center text-sm text-slate-600"
        >
          {t("XP management is available only for Super Admin and Ops Manager.")}
        </p>
      ) : (
        <>
          <form
            className="mt-4 grid gap-3 md:grid-cols-[1fr_auto]"
            onSubmit={handleSearchSubmit}
          >
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                {t("Find user")}
              </label>
              <div className="relative mt-1">
                <Search
                  className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
                />
                <input
                  className={cn(fieldClassName, "pl-9")}
                  value={searchInput}
                  onChange={(event) => setSearchInput(event.target.value)}
                  placeholder={t("Name, username, phone")}
                  disabled={isLoadingUsers || isSubmitting}
                />
              </div>
            </div>

            <Button
              type="submit"
              className="h-10 self-end"
              disabled={isLoadingUsers || isSubmitting}
            >
              <Search className="mr-2 h-4 w-4" />
              {t("Search")}
            </Button>
          </form>

          <div className="mt-4 space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                {t("Target user")}
              </label>
              <select
                className={cn(fieldClassName, "mt-1")}
                value={selectedUserId ?? ""}
                onChange={(event) => {
                  const rawValue = event.target.value;
                  if (!rawValue) {
                    setSelectedUserId(null);
                    return;
                  }
                  const value = Number(rawValue);
                  setSelectedUserId(Number.isInteger(value) && value > 0 ? value : null);
                }}
                disabled={isLoadingUsers || isSubmitting || users.length === 0}
              >
                {users.length === 0 ? (
                  <option value="">{t("No users found")}</option>
                ) : null}
                {users.map((user) => (
                  <option key={user.id} value={user.id}>
                    {user.display_name} (@{user.username})
                  </option>
                ))}
              </select>
            </div>

            {selectedUser ? (
              <div className="rm-subpanel p-3">
                <p className="inline-flex items-center gap-2 text-sm font-semibold text-slate-900">
                  <UserRound className="h-4 w-4" />
                  {selectedUser.display_name}
                </p>
                <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-600">
                  <span>@{selectedUser.username}</span>
                  <span>{t("Level")} {selectedUser.level}</span>
                  {selectedUser.phone ? <span>{selectedUser.phone}</span> : null}
                </div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {selectedUser.roles.length ? (
                    selectedUser.roles.map((roleTitle) => (
                      <span key={roleTitle} className="rm-role-pill">
                        {roleTitle}
                      </span>
                    ))
                  ) : (
                    <span className="text-xs text-slate-500">{t("No roles")}</span>
                  )}
                </div>
              </div>
            ) : null}
          </div>

          <form className="mt-4 space-y-4" onSubmit={handleAdjustSubmit}>
            <div className="grid gap-3 sm:grid-cols-[220px_1fr]">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                  {t("Action")}
                </label>
                <div className="mt-1 grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    className={cn(
                      "rm-menu-btn",
                      mode === "add" ? "rm-menu-btn-active" : "rm-menu-btn-idle",
                    )}
                    onClick={() => setMode("add")}
                    disabled={isSubmitting}
                    >
                      <span className="inline-flex items-center gap-1">
                        <PlusCircle className="h-4 w-4" />
                        {t("Add")}
                      </span>
                    </button>
                  <button
                    type="button"
                    className={cn(
                      "rm-menu-btn",
                      mode === "remove" ? "rm-menu-btn-active" : "rm-menu-btn-idle",
                    )}
                    onClick={() => setMode("remove")}
                    disabled={isSubmitting}
                    >
                      <span className="inline-flex items-center gap-1">
                        <MinusCircle className="h-4 w-4" />
                        {t("Remove")}
                      </span>
                    </button>
                  </div>
                </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                  {t("Amount")}
                </label>
                <input
                  className={cn(fieldClassName, "mt-1")}
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  value={amountInput}
                  onChange={(event) =>
                    setAmountInput(event.target.value.replace(/[^0-9]/g, ""))
                  }
                  placeholder={t("Enter positive integer")}
                  disabled={isSubmitting}
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                {t("Comment (required)")}
              </label>
              <textarea
                className={cn(fieldClassName, "mt-1 min-h-[108px] resize-y py-2")}
                value={comment}
                onChange={(event) => setComment(event.target.value)}
                placeholder={t("Reason for this XP change. This message is sent to Telegram.")}
                disabled={isSubmitting}
              />
            </div>

            <div className="flex flex-wrap gap-2">
              <Button
                type="submit"
                className="h-10"
                disabled={isSubmitting || isLoadingUsers || users.length === 0}
              >
                <Sparkles className="mr-2 h-4 w-4" />
                {isSubmitting ? t("Saving...") : t("Apply XP change")}
              </Button>
            </div>
          </form>
        </>
      )}
    </section>
  );
}
